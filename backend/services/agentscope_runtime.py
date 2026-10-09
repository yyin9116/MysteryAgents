"""AgentScope 运行时（1.x：ReActAgent + MsgHub + 原生上下文压缩）。

平台智能体的默认执行框架（models/agent.Agent 在无显式 llm_service 时构造本运行时）：

- 每个（会话, 角色）一个常驻 ReActAgent（InMemoryMemory + CompressionConfig
  原生自动上下文压缩），会话与 MsgHub 参与者全程稳定、不因阶段切换重建；
- 阶段切换时新的 system prompt 作为「本轮指令」并入输入消息，不覆盖人格设定；
- MsgHub 群聊广播经 observe_broadcast 分发（内容哈希去重，与上层滑动窗口
  历史喂送幂等，两条路径谁先到谁生效）；
- 结构化输出沿用 JSON 协议 + json_repair 宽容解析，返回与 LLMService 相同的
  AgentResponse / ChatResponse / VoteResponse，上层零改动。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from services.llm_service import AgentResponse, ChatResponse, VoteResponse
from utils.opencode_compat import (
    build_opencode_headers,
    is_opencode_go,
    needs_responses_api,
)

logger = logging.getLogger(__name__)

try:  # AgentScope 缺失时回退 litellm 直连，而不是拖垮进程
    from agentscope.agent import ReActAgent as _AsAgent
    from agentscope.formatter import (
        AnthropicChatFormatter,
        OpenAIChatFormatter as _OpenAIChatFormatter,
        OpenAIResponseChatFormatter as _OpenAIResponseChatFormatter,
    )
    from agentscope.memory import InMemoryMemory
    from agentscope.message import Msg
    from agentscope.model import (
        AnthropicChatModel,
        ChatModelBase,
        OpenAIChatModel,
        OpenAIResponseModel as _OpenAIResponseModel,
    )
    from agentscope.pipeline import MsgHub  # noqa: F401  服务层按需引用
    from agentscope.token import CharTokenCounter, OpenAITokenCounter

    _AGENTSCOPE_AVAILABLE = True
    _IMPORT_ERROR = ""
except Exception as _exc:  # pragma: no cover - 仅在未安装依赖时触发
    _AGENTSCOPE_AVAILABLE = False
    _IMPORT_ERROR = str(_exc)
    _AsAgent = Any  # type: ignore[assignment,misc]
    InMemoryMemory = Any  # type: ignore[assignment,misc]
    Msg = Any  # type: ignore[assignment,misc]

CALL_TIMEOUT_SECONDS = 150.0

# 压缩触发阈值：记忆 token 超过上下文窗口的 70% 时压缩，保留最近 6 条原文
_COMPRESSION_TRIGGER_RATIO = 0.70
_COMPRESSION_KEEP_RECENT = 6

_DEFAULT_OPENAI_COMPAT_BASE_URLS = {
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "deepseek": "https://api.deepseek.com/v1",
    "moonshot": "https://api.moonshot.cn/v1",
}


class AgentScopeUnavailableError(RuntimeError):
    """AgentScope 未安装或初始化失败。"""


def is_agentscope_available() -> bool:
    return _AGENTSCOPE_AVAILABLE


def _extract_text(msg: Any) -> str:
    """从 AgentScope Msg 提取纯文本（content 可能是 str 或 block 列表）。"""
    if msg is None:
        return ""
    try:
        text = Msg.get_text_content(msg)
        if isinstance(text, str):
            return text
    except Exception:
        pass
    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            text = getattr(block, "text", None) or (
                block.get("text") if isinstance(block, dict) else None
            )
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(parts)
    return ""


def _parse_json_payload(text: str) -> Dict[str, Any]:
    """宽容解析模型 JSON 输出：json → json_repair → 空对象。"""
    if not text:
        return {}
    cleaned = text.strip()
    # 剥掉 ```json 代码围栏
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass
    try:
        import json_repair

        data = json_repair.repair_json(cleaned, return_objects=True)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _content_hash(role: str, content: str) -> str:
    return hashlib.sha1(f"{role}::{content}".encode("utf-8")).hexdigest()


def build_agentscope_model(
    model_config: Optional[Dict[str, Any]],
) -> Tuple[Any, Any, int]:
    """按平台 ModelConfigData 构造 AgentScope (ChatModel, Formatter, context_size)。

    provider 映射（1.x 的模型是 kwargs 风格，formatter 独立传入）：
    - openai / zhipu / deepseek / moonshot 及任何带 base_url 的兼容端点 → OpenAIChatModel
    - anthropic → AnthropicChatModel
    - ollama → OpenAI 兼容端点（避免引入可选的 ollama SDK）
    """
    if not _AGENTSCOPE_AVAILABLE:
        raise AgentScopeUnavailableError(f"AgentScope 未安装：{_IMPORT_ERROR}")
    cfg = model_config or {}
    provider = (cfg.get("provider") or "openai").lower()
    model_name = cfg.get("model") or "gpt-4o-mini"
    api_key = cfg.get("api_key")
    base_url = cfg.get("base_url")
    extra = cfg.get("extra_params") or {}
    reasoning_effort = extra.get("reasoning_effort")

    # OpenCode Go 网关：默认端点 + 必需的会话头/UA（前端保存的 provider 通常是 openai）
    opencode_gateway = provider == "opencode" or is_opencode_go(base_url)
    if opencode_gateway:
        base_url = base_url or "https://opencode.ai/zen/go/v1"

    if provider == "anthropic":
        model = AnthropicChatModel(
            model_name=model_name,
            api_key=api_key or "empty",
            stream=False,
            max_tokens=4096,
        )
        return model, AnthropicChatFormatter(), 200000

    if provider == "ollama":
        base_url = base_url or "http://localhost:11434/v1"
        model = OpenAIChatModel(
            model_name=model_name,
            api_key=api_key or "ollama",
            stream=False,
            client_kwargs={"base_url": base_url},
        )
        return model, _OpenAICompatFormatter(), 32768

    # OpenAI 兼容族（含 zhipu/deepseek/moonshot 等自定义 base_url）
    if not base_url and provider in _DEFAULT_OPENAI_COMPAT_BASE_URLS:
        base_url = _DEFAULT_OPENAI_COMPAT_BASE_URLS[provider]
    client_kwargs: Dict[str, Any] = {}
    if base_url:
        client_kwargs = {"base_url": base_url}
        if opencode_gateway:
            # 会话头按模型实例稳定（每个角色/运行时一个独立会话）
            client_kwargs["default_headers"] = build_opencode_headers()

    # 仅 Responses 协议的模型（OpenCode 网关的 luna/grok/muse 系）：自动切换协议适配
    if opencode_gateway and needs_responses_api(model_name):
        response_kwargs: Dict[str, Any] = {
            "model_name": model_name,
            "api_key": api_key or "empty",
            "stream": False,
        }
        if client_kwargs:
            response_kwargs["client_kwargs"] = client_kwargs
        if reasoning_effort in ("minimal", "low", "medium", "high"):
            response_kwargs["reasoning_effort"] = reasoning_effort
        model = _OpenAIResponseModel(
            **response_kwargs,
        )
        return model, _OpenAIResponseCompatFormatter(), 128000

    kwargs: Dict[str, Any] = {}
    if client_kwargs:
        kwargs["client_kwargs"] = client_kwargs
    if reasoning_effort in ("none", "minimal", "low", "medium", "high", "xhigh"):
        kwargs["reasoning_effort"] = reasoning_effort
    model = OpenAIChatModel(
        # 凭据校验要求非空字符串：无密钥端点（本地网关/ollama）用占位符
        model_name=model_name,
        api_key=api_key or "empty",
        stream=False,
        **kwargs,
    )
    return model, _OpenAICompatFormatter(), 128000


def _build_compression_config(context_size: int, prefer_char_counter: bool = False):
    """构造原生压缩配置；token 计数器构造失败时返回 None（跳过压缩）。

    prefer_char_counter：Responses 协议消息的内容块是 input_text 等类型，
    OpenAITokenCounter 不识别（只支持 text/image_url），此类模型改用字符计数。
    """
    try:
        counter = None
        if prefer_char_counter:
            counter = CharTokenCounter()
        else:
            try:
                counter = OpenAITokenCounter(model_name="gpt-4o")
            except Exception:
                counter = CharTokenCounter()
        return _AsAgent.CompressionConfig(
            enable=True,
            agent_token_counter=counter,
            trigger_threshold=int(context_size * _COMPRESSION_TRIGGER_RATIO),
            keep_recent=_COMPRESSION_KEEP_RECENT,
        )
    except Exception:
        logger.debug("CompressionConfig build failed; compression disabled", exc_info=True)
        return None


class _OpenAICompatFormatter(_OpenAIChatFormatter):
    """剥离 name 字段的 OpenAI 兼容 Formatter。

    AgentScope 的 OpenAIChatFormatter 会在每条消息上携带 ``name`` 标识多智能体
    说话人，但 OpenCode Go 网关等部分兼容端点不接受该参数
    （400: "name" is not supported by this endpoint）。说话人身份改由消息
    正文前缀（"char_x: ..."）承载，与历史喂送格式一致。
    """

    async def _format(self, msgs: list) -> list:
        formatted = await super()._format(msgs)
        for message in formatted:
            if isinstance(message, dict):
                message.pop("name", None)
        return formatted


class _OpenAIResponseCompatFormatter(_OpenAIResponseChatFormatter):
    """剥离 name 字段的 Responses 协议 Formatter。

    与 _OpenAICompatFormatter 同理：OpenCode Go 网关不接受消息项上的 ``name``。
    仅剥离消息项（type 缺省或 "message"）的 name，function_call 项的 name 是
    函数名，必须保留。
    """

    async def _format(self, msgs: list) -> list:
        formatted = await super()._format(msgs)
        for message in formatted:
            if not isinstance(message, dict):
                continue
            if message.get("type") in (None, "message"):
                message.pop("name", None)
        return formatted


class _SessionState:
    """一个（对局, 角色）的常驻 AgentScope 会话。"""

    __slots__ = ("agent", "system_prompt", "seen_hashes", "seen_static")

    def __init__(self, agent: Any, system_prompt: str) -> None:
        self.agent = agent
        self.system_prompt = system_prompt
        self.seen_hashes: set = set()
        self.seen_static = system_prompt


class AgentscopeRuntime:
    """实现 LLMService 生成接口的 AgentScope 后端。

    与 LLMService 的差异：
    - model/model_config/iq_level/temperature 参数被忽略（模型在构造时已绑定），
      保留签名是为了与 models/agent.Agent 的调用点完全兼容；
    - 同一 session_id 的多次调用共享一个常驻 ReActAgent，其记忆由原生
      CompressionConfig 自动压缩；
    - prefers_unmerged_history=True：上层历史不再合并连续 user 消息，
      保证逐条喂送 + 哈希去重与 MsgHub 广播路径幂等。
    """

    prefers_unmerged_history = True

    def __init__(
        self,
        model_config: Optional[Dict[str, Any]] = None,
        enable_compression: bool = True,
        max_sessions: int = 64,
    ) -> None:
        self._model_config = model_config or {}
        self._enable_compression = enable_compression
        self._max_sessions = max_sessions
        self._sessions: Dict[str, _SessionState] = {}
        self._model_cache: Optional[Tuple[Any, Any, int]] = None
        # 构造时即校验模型配置（不触网）：模型构造失败在建局时立刻暴露
        self._build_model()

    # ------------------------------------------------------------------
    # 会话管理
    # ------------------------------------------------------------------

    def _build_model(self) -> Tuple[Any, Any, int]:
        if self._model_cache is None:
            self._model_cache = build_agentscope_model(self._model_config)
        return self._model_cache

    def _get_session(self, session_id: str, system_prompt: str) -> _SessionState:
        session = self._sessions.get(session_id)
        if session is None:
            model, formatter, context_size = self._build_model()
            compression = None
            if self._enable_compression:
                # Responses 协议模型的消息格式 OpenAITokenCounter 不识别，改用字符计数
                prefer_char_counter = type(model).__name__ == "OpenAIResponseModel"
                compression = _build_compression_config(context_size, prefer_char_counter)
            agent = _AsAgent(
                name=str(session_id),
                sys_prompt=system_prompt,
                model=model,
                formatter=formatter,
                memory=InMemoryMemory(),
                compression_config=compression,
                max_iters=1,
            )
            session = _SessionState(agent=agent, system_prompt=system_prompt)
            if len(self._sessions) >= self._max_sessions:
                # 简单 LRU：清掉最早的会话
                oldest = next(iter(self._sessions))
                self._sessions.pop(oldest, None)
            self._sessions[session_id] = session
        return session

    def get_agent(self, session_id: str) -> Optional[Any]:
        """返回常驻 AgentScope Agent（MsgHub 参与者）；会话不存在时为 None。"""
        session = self._sessions.get(session_id)
        return session.agent if session else None

    # ------------------------------------------------------------------
    # 观测（历史喂送 + MsgHub 广播共用一套哈希去重）
    # ------------------------------------------------------------------

    async def _observe_history(self, session: _SessionState, history: List[Dict[str, Any]]) -> None:
        """把上层传入历史中未观测过的消息喂给常驻 Agent（按内容哈希去重）。"""
        for item in history:
            if not isinstance(item, dict):
                continue
            role = item.get("role") or "user"
            content = item.get("content")
            if not isinstance(content, str) or not content:
                continue
            if role == "system":
                continue  # system prompt 已内置于 Agent
            digest = _content_hash(role, content)
            if digest in session.seen_hashes:
                continue
            session.seen_hashes.add(digest)
            as_role = "assistant" if role == "assistant" else "user"
            msg = Msg(
                name="opponent" if as_role == "assistant" else "host",
                content=content,
                role=as_role,
            )
            try:
                await session.agent.observe(msg)
            except Exception:
                logger.debug("observe failed (ignored)", exc_info=True)

    async def observe_broadcast(
        self,
        session_id: str,
        content: str,
        *,
        speaker: str = "player",
        digest: Optional[str] = None,
    ) -> bool:
        """MsgHub 广播入口：把其他角色的公开发言写入本会话记忆。

        digest 需与历史喂送路径对同一内容计算出的哈希一致（服务层用
        _content_hash("user", formatted_content)），保证两条路径幂等。
        """
        session = self._sessions.get(session_id)
        if session is None or not content:
            return False
        digest = digest or _content_hash("user", content)
        if digest in session.seen_hashes:
            return False
        session.seen_hashes.add(digest)
        try:
            await session.agent.observe(Msg(name=speaker, content=content, role="user"))
            return True
        except Exception:
            logger.debug("hub observe failed (ignored)", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # 生成
    # ------------------------------------------------------------------

    async def _complete(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, Any]],
        session_id: Optional[str],
    ) -> str:
        """执行一次生成，返回模型纯文本输出。"""
        history = [m for m in (conversation_history or []) if isinstance(m, dict)]

        if not session_id:
            # 无状态：一次性 Agent（指令进 sys_prompt，历史逐条观测，不落压缩）
            model, formatter, _ = self._build_model()
            agent = _AsAgent(
                name="stateless",
                sys_prompt=system_prompt,
                model=model,
                formatter=formatter,
                memory=InMemoryMemory(),
                max_iters=1,
            )
            for item in history[:-1]:
                role = item.get("role") or "user"
                content = item.get("content")
                if role == "system" or not isinstance(content, str) or not content:
                    continue
                as_role = "assistant" if role == "assistant" else "user"
                await agent.observe(
                    Msg(
                        name="opponent" if as_role == "assistant" else "host",
                        content=content,
                        role=as_role,
                    )
                )
            reply_msg = await agent.reply(self._current_input_msg(history, None))
            return _extract_text(reply_msg)

        session = self._get_session(session_id, system_prompt)
        # 阶段切换：新的阶段指令并入本轮输入（会话保持稳定，人格 sys_prompt 不变）
        instruction = None
        if system_prompt != session.system_prompt and system_prompt != session.seen_static:
            instruction = system_prompt
            session.seen_static = system_prompt
        if history:
            await self._observe_history(session, history[:-1])
        reply_msg = await asyncio.wait_for(
            session.agent.reply(self._current_input_msg(history, instruction)),
            timeout=CALL_TIMEOUT_SECONDS,
        )
        text = _extract_text(reply_msg)
        await self._polish_memory(session, text)
        return text

    @staticmethod
    def _current_input_msg(history: List[Dict[str, Any]], instruction: Optional[str]) -> Any:
        """取最后一条 user 消息作为本轮输入；阶段指令并入输入头部。"""
        input_text = None
        for item in reversed(history):
            content = item.get("content")
            if item.get("role") != "system" and isinstance(content, str) and content:
                input_text = content
                break
        if input_text is None:
            input_text = "请根据以上情境继续。"
        if instruction:
            input_text = f"{instruction}\n\n---\n\n{input_text}"
        return Msg(
            name="host",
            content=input_text,
            role="user",
        )

    async def _polish_memory(self, session: _SessionState, raw_text: str) -> None:
        """把记忆里刚生成的原始 JSON 回复替换为净化后的发言（best effort）。

        模型按协议输出 JSON，直接留在记忆里既浪费 token 又会带偏后续发言风格；
        解析成功时用 speech / messages 的纯文本替换最后一条 assistant 消息。
        """
        try:
            payload = _parse_json_payload(raw_text)
            clean = ""
            messages = payload.get("messages")
            if isinstance(messages, list) and messages:
                clean = " / ".join(str(b) for b in messages if b)
            clean = clean or str(payload.get("speech") or payload.get("message") or "")
            if not clean:
                return
            memory = session.agent.memory
            mem_items = await memory.get_memory()
            if not mem_items:
                return
            last = mem_items[-1]
            if getattr(last, "role", "") != "assistant":
                return
            if _extract_text(last) != raw_text:
                return  # 结构与预期不符时不动记忆，避免误删
            await memory.delete([last.id])
            await memory.add(
                Msg(name=getattr(session.agent, "name", "assistant"), content=clean, role="assistant")
            )
        except Exception:
            logger.debug("polish memory failed (ignored)", exc_info=True)

    # ------------------------------------------------------------------
    # LLMService 兼容接口（签名与 LLMService 完全一致）
    # ------------------------------------------------------------------

    async def generate_agent_response(
        self,
        system_prompt: str,
        conversation_history: list,
        iq_level: str,
        temperature: float = 0.7,
        model: Optional[str] = None,
        model_config: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> AgentResponse:
        text = await self._complete(system_prompt, conversation_history, session_id)
        payload = _parse_json_payload(text)
        return AgentResponse(
            thought=payload.get("thought") or "",
            speech=payload.get("speech") or payload.get("message") or text[:600],
            suspicion=payload.get("suspicion") or {},
        )

    async def generate_chat_response(
        self,
        system_prompt: str,
        conversation_history: list,
        iq_level: str,
        temperature: float = 0.9,
        model: Optional[str] = None,
        model_config: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> ChatResponse:
        text = await self._complete(system_prompt, conversation_history, session_id)
        payload = _parse_json_payload(text)
        return ChatResponse(
            thought=payload.get("thought") or "",
            messages=payload.get("messages") or [],
            suspicion=payload.get("suspicion") or {},
        )

    async def generate_vote_response(
        self,
        system_prompt: str,
        conversation_history: list,
        iq_level: str,
        valid_agent_ids: list,
        temperature: float = 0.7,
        model: Optional[str] = None,
        model_config: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> VoteResponse:
        text = await self._complete(system_prompt, conversation_history, session_id)
        payload = _parse_json_payload(text)
        vote = str(payload.get("vote") or payload.get("target") or "").strip()
        if not vote and valid_agent_ids:
            vote = valid_agent_ids[0]  # 兜底：投第一个合法目标，绝不挂死
        try:
            confidence = float(payload.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        return VoteResponse(
            thought=payload.get("thought") or "",
            vote=vote,
            confidence=max(0.0, min(1.0, confidence)),
        )

    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        self._sessions.clear()
