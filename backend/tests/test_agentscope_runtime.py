"""AgentScope 运行时（1.x：ReActAgent + MsgHub）单元测试（不触网：stub Agent）。"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.agentscope_runtime import (  # noqa: E402
    AgentscopeRuntime,
    _content_hash,
    _parse_json_payload,
    build_agentscope_model,
    is_agentscope_available,
)

require_agentscope = pytest.mark.skipif(
    not is_agentscope_available(), reason="agentscope not installed"
)


# ---------------------------------------------------------------------- #
# JSON 解析
# ---------------------------------------------------------------------- #

def test_parse_plain_json():
    data = _parse_json_payload('{"thought":"t","speech":"s","suspicion":{"a":3}}')
    assert data["speech"] == "s"
    assert data["suspicion"] == {"a": 3}


def test_parse_fenced_json_with_prefix_text():
    raw = '好的，我的发言如下：```json\n{"thought":"x","messages":["a","b"]}\n```'
    data = _parse_json_payload(raw)
    assert data["messages"] == ["a", "b"]


def test_parse_garbage_returns_empty():
    assert _parse_json_payload("这不是JSON输出") == {}
    assert _parse_json_payload("") == {}


# ---------------------------------------------------------------------- #
# 模型构造（1.x 返回 (model, formatter, context_size) 三组）
# ---------------------------------------------------------------------- #

@require_agentscope
def test_build_model_zhipu_uses_openai_compatible():
    model, formatter, ctx = build_agentscope_model(
        {"provider": "zhipu", "model": "glm-4-flash", "api_key": "k"}
    )
    assert type(model).__name__ == "OpenAIChatModel"
    # OpenAI 兼容 Formatter 子类（剥离 name 字段以适配 OpenCode Go 等端点）
    from agentscope.formatter import OpenAIChatFormatter

    assert isinstance(formatter, OpenAIChatFormatter)
    assert ctx == 128000


@require_agentscope
def test_build_model_custom_base_url():
    model, _, _ = build_agentscope_model(
        {"provider": "openai", "model": "gpt-x", "api_key": "k", "base_url": "http://localhost:1234/v1"}
    )
    assert type(model).__name__ == "OpenAIChatModel"
    # base_url 落在底层 AsyncOpenAI client 上
    assert str(model.client.base_url).rstrip("/") == "http://localhost:1234/v1"


@require_agentscope
def test_build_model_reasoning_effort_passthrough():
    model, _, _ = build_agentscope_model(
        {
            "provider": "zhipu", "model": "glm-4.6", "api_key": "k",
            "extra_params": {"reasoning_effort": "high"},
        }
    )
    assert model.reasoning_effort == "high"


@require_agentscope
def test_build_model_ollama_via_openai_compat():
    model, _, ctx = build_agentscope_model({"provider": "ollama", "model": "qwen3"})
    assert type(model).__name__ == "OpenAIChatModel"
    assert ctx == 32768


@require_agentscope
def test_build_model_anthropic():
    model, formatter, _ = build_agentscope_model(
        {"provider": "anthropic", "model": "claude-x", "api_key": "k"}
    )
    assert type(model).__name__ == "AnthropicChatModel"
    assert type(formatter).__name__ == "AnthropicChatFormatter"


@require_agentscope
@pytest.mark.parametrize("model_id", ["gpt-5.6-luna", "grok-4.7", "muse-spark-1.3-contributor"])
def test_build_model_responses_only_models_use_response_model(model_id):
    """OpenCode 网关上仅 Responses 协议的模型自动切 OpenAIResponseModel，不报错。"""
    model, formatter, ctx = build_agentscope_model(
        {
            "provider": "openai",
            "model": model_id,
            "api_key": "k",
            "base_url": "https://opencode.ai/zen/go/v1",
        }
    )
    assert type(model).__name__ == "OpenAIResponseModel"
    from agentscope.formatter import OpenAIResponseChatFormatter

    assert isinstance(formatter, OpenAIResponseChatFormatter)
    assert ctx == 128000


@require_agentscope
def test_build_model_non_responses_opencode_model_keeps_chat_model():
    model, _, _ = build_agentscope_model(
        {
            "provider": "openai",
            "model": "glm-5.3-flash",
            "api_key": "k",
            "base_url": "https://opencode.ai/zen/go/v1",
        }
    )
    assert type(model).__name__ == "OpenAIChatModel"


@require_agentscope
def test_response_formatter_strips_message_name():
    """Response Formatter 剥离消息项的 name（OpenCode 网关拒绝该字段）。"""
    import asyncio

    from agentscope.message import Msg

    _, formatter, _ = build_agentscope_model(
        {
            "provider": "openai",
            "model": "gpt-5.6-luna",
            "api_key": "k",
            "base_url": "https://opencode.ai/zen/go/v1",
        }
    )
    formatted = asyncio.run(formatter._format([Msg(name="张三", content="你好", role="user")]))
    assert formatted, "formatter returned empty output"
    assert "name" not in formatted[0]


# ---------------------------------------------------------------------- #
# 生成接口（stub AgentScope Agent）
# ---------------------------------------------------------------------- #

class _FakeAgent:
    """替身 Agent：记录 observe 的内容，reply 返回预置文本。"""

    reply_text = '{"thought":"推理","speech":"我认为管家有嫌疑。","suspicion":{"butler":7}}'

    def __init__(self, *args, **kwargs):
        self.observed: list = []
        self.reply_inputs: list = []
        self.kwargs = kwargs

    async def observe(self, msg):
        self.observed.append(msg)

    async def reply(self, inputs=None, **kwargs):
        self.reply_inputs.append(inputs)
        from agentscope.message import Msg, TextBlock

        return Msg(
            name="fake",
            content=[TextBlock(type="text", text=_FakeAgent.reply_text)],
            role="assistant",
        )


def _msg_text(msg) -> str:
    from agentscope.message import Msg

    text = Msg.get_text_content(msg)
    return text if isinstance(text, str) else str(msg.content)


def _make_runtime() -> AgentscopeRuntime:
    return AgentscopeRuntime(
        model_config={"provider": "zhipu", "model": "glm-4-flash", "api_key": "k"}
    )


def _run(coro):
    return asyncio.run(coro)


@require_agentscope
def test_stateless_generate_agent_response():
    rt = _make_runtime()
    with patch("services.agentscope_runtime._AsAgent", _FakeAgent):
        resp = _run(
            rt.generate_agent_response(
                system_prompt="你是角色A",
                conversation_history=[
                    {"role": "user", "content": "案情简报"},
                    {"role": "assistant", "content": "他人发言"},
                    {"role": "user", "content": "请发言"},
                ],
                iq_level="Mid",
            )
        )
    assert resp.speech == "我认为管家有嫌疑。"
    assert resp.thought == "推理"
    assert resp.suspicion == {"butler": 7}


@require_agentscope
def test_stateful_session_observes_only_unseen():
    rt = _make_runtime()
    history = [
        {"role": "user", "content": "案情简报"},
        {"role": "assistant", "content": "他人发言"},
        {"role": "user", "content": "请发言"},
    ]
    with patch("services.agentscope_runtime._AsAgent", _FakeAgent):
        _run(rt.generate_agent_response("系统提示", history, "Mid", session_id="agent_1"))
        # 第二轮：历史追加了一条他人发言 + 新的当前轮输入（滑动窗口语义）
        history2 = history[:-1] + [
            {"role": "assistant", "content": "新增发言"},
            {"role": "user", "content": "第二轮请发言"},
        ]
        _run(rt.generate_agent_response("系统提示", history2, "Mid", session_id="agent_1"))

    session = rt._sessions["agent_1"]
    observed_texts = [_msg_text(m) for m in session.agent.observed]
    # 案情简报/他人发言 只应观测一次；新增发言观测一次（非末轮输入）
    assert observed_texts.count("案情简报") == 1
    assert observed_texts.count("他人发言") == 1
    assert observed_texts.count("新增发言") == 1
    # 末轮输入走 reply，不进 observe
    assert observed_texts.count("请发言") == 0
    assert observed_texts.count("第二轮请发言") == 0


@require_agentscope
def test_phase_switch_keeps_session_and_prepends_instruction():
    """阶段切换：会话不重建，新阶段指令并入本轮输入（MsgHub 参与者保持稳定）。"""
    rt = _make_runtime()
    with patch("services.agentscope_runtime._AsAgent", _FakeAgent):
        _run(rt.generate_agent_response("读本人格提示", [], "Mid", session_id="s"))
        session_before = rt._sessions["s"].agent
        _run(rt.generate_agent_response("讨论阶段提示", [{"role": "user", "content": "局势简报"}], "Mid", session_id="s"))
        # 同一阶段提示重复出现时不再重复注入
        _run(rt.generate_agent_response("讨论阶段提示", [{"role": "user", "content": "第二轮简报"}], "Mid", session_id="s"))

    session = rt._sessions["s"]
    assert session.agent is session_before  # 会话稳定，未重建
    assert session.system_prompt == "读本人格提示"  # 人格 sys_prompt 不被覆盖
    first_instruction_input = session.agent.reply_inputs[1]
    assert "讨论阶段提示" in _msg_text(first_instruction_input)
    assert "局势简报" in _msg_text(first_instruction_input)
    second_instruction_input = session.agent.reply_inputs[2]
    assert "讨论阶段提示" not in _msg_text(second_instruction_input)
    assert "第二轮简报" in _msg_text(second_instruction_input)


@require_agentscope
def test_observe_broadcast_idempotent_with_history_feed():
    """MsgHub 广播与历史喂送同内容/同哈希时只入记忆一次。"""
    rt = _make_runtime()
    speech = "char_1: 我昨晚在书房。"
    digest = _content_hash("user", speech)
    with patch("services.agentscope_runtime._AsAgent", _FakeAgent):
        # 预创建会话（读本阶段语义）
        _run(rt.generate_agent_response("人格提示", [], "Mid", session_id="char_2"))
        # 1) MsgHub 广播先到
        delivered = _run(rt.observe_broadcast("char_2", speech, speaker="角色甲", digest=digest))
        assert delivered is True
        # 2) 历史喂送后到：同内容应被哈希去重
        _run(
            rt.generate_agent_response(
                "讨论阶段提示",
                [{"role": "user", "content": speech}, {"role": "user", "content": "请继续"}],
                "Mid",
                session_id="char_2",
            )
        )
    session = rt._sessions["char_2"]
    observed_texts = [_msg_text(m) for m in session.agent.observed]
    assert observed_texts.count(speech) == 1
    # 重复广播同内容也是 no-op
    _run(rt.observe_broadcast("char_2", speech, speaker="角色甲", digest=digest))
    assert observed_texts.count(speech) == 1


@require_agentscope
def test_vote_fallback_to_first_valid_target():
    rt = _make_runtime()
    with patch("services.agentscope_runtime._AsAgent", _FakeAgent):
        _FakeAgent.reply_text = "我不会按格式回答"
        resp = _run(
            rt.generate_vote_response(
                system_prompt="投票",
                conversation_history=[{"role": "user", "content": "请投票"}],
                iq_level="Mid",
                valid_agent_ids=["mg_a", "mg_b"],
            )
        )
    assert resp.vote == "mg_a"
    assert 0.0 <= resp.confidence <= 1.0


@require_agentscope
def test_chat_response_from_messages_payload():
    rt = _make_runtime()
    with patch("services.agentscope_runtime._AsAgent", _FakeAgent):
        _FakeAgent.reply_text = '{"thought":"t","messages":["第一句","第二句"]}'
        resp = _run(
            rt.generate_chat_response(
                system_prompt="群聊",
                conversation_history=[{"role": "user", "content": "继续"}],
                iq_level="Mid",
            )
        )
    assert resp.messages == ["第一句", "第二句"]
