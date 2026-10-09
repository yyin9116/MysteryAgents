"""
LLM Service using LiteLLM for unified model access.

Supports multiple providers: OpenAI, Alibaba Qwen, Anthropic, Ollama
"""

import json
import re
from typing import Dict, Any, List, Optional
import httpx
from litellm import acompletion, completion_cost
from pydantic import BaseModel, Field, ConfigDict, field_validator
import logging
logger = logging.getLogger(__name__)

from config.settings import settings
from services.usage_store import UsageStore
from services import prompt_registry
from utils import opencode_compat


class AgentResponse(BaseModel):
    """Validated agent response schema."""
    model_config = ConfigDict(extra="allow")

    thought: str = Field(..., max_length=500)
    speech: str = Field(..., max_length=600)
    suspicion: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('thought', mode='before')
    @classmethod
    def clip_thought(cls, v: Any) -> Any:
        # LLM 无法精确控制长度：超长截断而不是让整次调用作废
        return v[:500] if isinstance(v, str) else v

    @field_validator('speech', mode='before')
    @classmethod
    def clip_speech(cls, v: Any) -> Any:
        return v[:600] if isinstance(v, str) else v

    @field_validator('suspicion', mode='before')
    @classmethod
    def validate_suspicion_scores(cls, v: Dict[str, Any]) -> Dict[str, int]:
        """宽容解析怀疑度：LLM 偶尔返回 {'char_id': x, 'score': n} 之类对象或字符串数字，
        尽力提取数值；无法解析的条目直接跳过，绝不让整次模型调用作废重试。"""
        normalized: Dict[str, int] = {}
        for agent_id, score in (v or {}).items():
            value = score
            if isinstance(value, dict):
                # 形如 {'char_id': ..., 'score': 5} 的对象：取其中数值字段
                for key in ('score', 'suspicion', 'value', 'level'):
                    if isinstance(value.get(key), (int, float, str)):
                        value = value[key]
                        break
                else:
                    continue  # 提不出数值：跳过该条
            if isinstance(value, bool) or value is None:
                continue
            try:
                numeric_score = float(value)
                normalized[agent_id] = max(0, min(10, int(round(numeric_score))))
            except (TypeError, ValueError):
                continue  # 解析失败：跳过该条而不是作废整次调用
        return normalized

    @field_validator('speech')
    @classmethod
    def validate_speech_length(cls, v: str) -> str:
        if len(v) > 220:
            return v[:220]
        return v


class VoteResponse(BaseModel):
    """Validated vote response schema."""
    thought: str = Field(..., max_length=500)
    vote: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    """Validated group-chat style response schema（QQ/微信群聊多条短消息）."""
    model_config = ConfigDict(extra="allow")

    thought: str = Field(..., max_length=500)
    messages: List[str] = Field(default_factory=list)
    suspicion: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('thought', mode='before')
    @classmethod
    def clip_thought(cls, v: Any) -> Any:
        return v[:500] if isinstance(v, str) else v

    @field_validator('messages', mode='before')
    @classmethod
    def coerce_messages(cls, v: Any) -> Any:
        # 兼容模型只回一条字符串的情况
        if isinstance(v, str):
            v = [v]
        if not isinstance(v, list):
            return []
        cleaned = [str(item).strip() for item in v if str(item).strip()]
        return cleaned[:4]

    @field_validator('messages')
    @classmethod
    def clamp_messages(cls, v: List[str]) -> List[str]:
        # 单条气泡过长说明模型没按群聊风格输出，截断保持观感
        return [item[:80] for item in v]

    @field_validator('suspicion', mode='before')
    @classmethod
    def validate_suspicion_scores(cls, v: Dict[str, Any]) -> Dict[str, int]:
        normalized: Dict[str, int] = {}
        for agent_id, score in (v or {}).items():
            try:
                normalized[agent_id] = max(0, min(10, int(round(float(score)))))
            except (TypeError, ValueError):
                continue
        return normalized


class LLMService:
    """Service for LLM interactions using LiteLLM."""
    
    def __init__(self, usage_store: Optional[UsageStore] = None):
        self.timeout = settings.LLM_TIMEOUT
        self.max_retries = settings.LLM_MAX_RETRIES
        self.usage_store = usage_store or UsageStore()
        # Stable session id used for OpenCode Go routing when callers don't
        # provide a per-conversation session id.
        import uuid
        self._opencode_session_id = f"killer-{uuid.uuid4()}"
        
    def _get_model_for_iq(self, iq_level: str) -> str:
        """Get the appropriate model for the given IQ level."""
        model_map = {
            "High": settings.MODEL_HIGH_IQ,
            "Mid": settings.MODEL_MID_IQ,
            "Low": settings.MODEL_LOW_IQ
        }
        return model_map.get(iq_level, settings.MODEL_MID_IQ)

    def _build_model_name(self, provider: Optional[str], model_name: Optional[str]) -> Optional[str]:
        if not model_name:
            return None
        if "/" in model_name:
            return model_name
        if not provider:
            return model_name
        return f"{provider.lower()}/{model_name}"

    def _resolve_model(
        self,
        iq_level: str,
        model: Optional[str] = None,
        model_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        if model:
            return model
        if model_config:
            resolved = self._build_model_name(
                model_config.get("provider"),
                model_config.get("model"),
            )
            if resolved:
                return resolved
        return self._get_model_for_iq(iq_level)

    def _get_completion_model(self, model: str) -> str:
        """Convert project-facing model ids to LiteLLM completion ids."""
        provider, _, model_name = model.partition("/")
        if not model_name:
            return model
        if provider.lower() in {"alibaba", "zhipu", "opencode"}:
            return f"openai/{model_name}"
        return model
    
    def _create_fallback_response(self, error_msg: str = "", iq_level: str = "Mid") -> Dict[str, Any]:
        """Create a fallback response when LLM fails."""
        logger.error(f"LLM call failed, using fallback response. Error: {error_msg}")
        logger.error(f"Model configuration - High: {settings.MODEL_HIGH_IQ}, Mid: {settings.MODEL_MID_IQ}, Low: {settings.MODEL_LOW_IQ}")
        logger.error(f"API Keys - OpenAI: {'Set' if settings.OPENAI_API_KEY else 'Not Set'}, Alibaba: {'Set' if settings.ALIBABA_API_KEY else 'Not Set'}, Anthropic: {'Set' if settings.ANTHROPIC_API_KEY else 'Not Set'}")
        
        # 生成多样化的 fallback 响应，避免重复检测
        import random
        import time
        
        # 使用时间戳和随机数生成唯一的响应
        timestamp = int(time.time() * 1000) % 1000
        random_num = random.randint(1, 100)
        
        # 根据 IQ 级别生成不同风格的响应
        if iq_level == "High":
            thoughts = [
                f"思考中... 需要更深入的分析。[{timestamp}]",
                f"让我整理一下逻辑... [{timestamp}]",
                f"这个问题需要仔细考虑。[{timestamp}]"
            ]
            speeches = [
                f"我需要更多时间思考这个问题。({random_num})",
                f"让我再想想如何表达。({random_num})",
                f"这个描述比较复杂。({random_num})"
            ]
        elif iq_level == "Low":
            thoughts = [
                f"嗯... 让我想想... [{timestamp}]",
                f"有点confused... [{timestamp}]",
                f"不太确定... [{timestamp}]"
            ]
            speeches = [
                f"呃... 我想想... ({random_num})",
                f"这个... 怎么说呢... ({random_num})",
                f"嗯... ({random_num})"
            ]
        else:  # Mid
            thoughts = [
                f"让我整理一下思路... [{timestamp}]",
                f"需要想一想... [{timestamp}]",
                f"稍等，我在思考... [{timestamp}]"
            ]
            speeches = [
                f"我需要更多时间思考。({random_num})",
                f"让我想想怎么说。({random_num})",
                f"稍等一下。({random_num})"
            ]
        
        thought_msg = random.choice(thoughts)
        speech_msg = random.choice(speeches)
        
        return {
            "thought": thought_msg,
            "speech": speech_msg,
            "suspicion": {}
        }
    
    def _extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to extract JSON from text that might contain markdown or other content."""
        # Try to find JSON in code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()
        
        # Try to find JSON object
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1:
            text = text[start_idx:end_idx + 1]
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _coerce_vote_choice(raw_vote: Any, valid_agent_ids: list[str]) -> Optional[str]:
        text = str(raw_vote or "").strip()
        if not text:
            return None
        if text in valid_agent_ids:
            return text
        for agent_id in valid_agent_ids:
            if agent_id and agent_id in text:
                return agent_id
        return None
    
    # 思考强度（reasoning_effort）只对推理系模型注入：非推理模型收到该参数会直接 400
    _REASONING_MODEL_PATTERN = re.compile(
        r"(o[134](-mini|-pro)?|gpt-5|deepseek-r1|grok-[34]|gemini-2\.5|qwen3|glm-4\.[5-9]|magistral|thinking|reasoner)",
        re.IGNORECASE,
    )

    @classmethod
    def _model_supports_reasoning_effort(cls, model: Optional[str]) -> bool:
        """Whether the model id looks like a reasoning-capable family."""
        model_id = (model or "").lower().rpartition("/")[-1]
        return bool(cls._REASONING_MODEL_PATTERN.search(model_id))

    def _get_llm_params(self, model: str, model_config: Optional[Dict[str, Any]] = None) -> dict:
        """Get additional parameters needed for specific LLM providers."""
        params = {}

        if model_config:
            provider = (model_config.get("provider") or "").lower()
            api_key = model_config.get("api_key")
            base_url = model_config.get("base_url")
            if api_key:
                params["api_key"] = api_key
            if base_url:
                params["api_base"] = base_url
            elif provider == "alibaba":
                params["api_base"] = settings.ALIBABA_BASE_URL
            elif provider == "zhipu":
                params["api_base"] = settings.ZHIPU_BASE_URL
            extra_params = model_config.get("extra_params") or {}
            params.update(extra_params)
            # 非推理模型不支持 reasoning_effort，剔除避免 400
            if params.get("reasoning_effort") and not self._model_supports_reasoning_effort(model):
                params.pop("reasoning_effort", None)
            return params
        
        # Alibaba Qwen models use OpenAI-compatible API
        # Model format: openai/qwen-turbo, openai/qwen-plus, etc.
        if model.startswith("openai/qwen") or model.startswith("alibaba/"):
            params["api_key"] = settings.ALIBABA_API_KEY
            params["api_base"] = settings.ALIBABA_BASE_URL
        elif model.startswith("openai/"):
            params["api_key"] = settings.OPENAI_API_KEY
        elif model.startswith("zhipu/"):
            params["api_key"] = settings.ZHIPU_API_KEY
            params["api_base"] = settings.ZHIPU_BASE_URL
        elif model.startswith("anthropic/") or "claude" in model.lower():
            params["api_key"] = settings.ANTHROPIC_API_KEY
        elif model.startswith("ollama/"):
            params["api_base"] = settings.OLLAMA_BASE_URL
        
        return params

    @staticmethod
    def _should_use_openai_compatible_http(model_config: Optional[Dict[str, Any]]) -> bool:
        """Use direct HTTP for OpenAI-compatible endpoints configured with base_url."""
        if not model_config:
            return False
        provider = (model_config.get("provider") or "").lower()
        base_url = (model_config.get("base_url") or "").strip()
        return provider in {"openai", "opencode"} and bool(base_url)

    async def _acompletion_openai_compatible(
        self,
        *,
        model_config: Dict[str, Any],
        messages: list[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        session_id: Optional[str] = None,
        **extra_params: Any,
    ) -> Dict[str, Any]:
        """Call an OpenAI-compatible endpoint without LiteLLM.

        Handles OpenCode Go specifics automatically: session/User-Agent
        headers and models that only speak the Responses API protocol.
        """
        base_url = (model_config.get("base_url") or "").rstrip("/")
        payload: Dict[str, Any] = {
            "model": model_config.get("model"),
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = response_format
        if model_config.get("extra_params"):
            payload.update(model_config["extra_params"])
        payload.update({key: value for key, value in extra_params.items() if value is not None})

        headers = {"Content-Type": "application/json"}
        # Some local OpenAI-compatible gateways advertise JSON support but return
        # non-UTF8 bytes when response_format is present. Keep the wire request
        # simple and enforce JSON in prompts/parsing instead.
        payload.pop("response_format", None)
        headers["Accept-Encoding"] = "identity"
        # 思考强度：仅推理系模型注入；Responses 协议映射到 reasoning.effort
        reasoning_effort = payload.pop("reasoning_effort", None)
        if reasoning_effort and not self._model_supports_reasoning_effort(payload.get("model")):
            reasoning_effort = None
        api_key = model_config.get("api_key") or "local-dev-key"
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        use_responses = opencode_compat.needs_responses_api(payload.get("model"))
        if opencode_compat.is_opencode_go(base_url):
            # Stable per-process session id; callers may pass a finer-grained one.
            headers.update(
                opencode_compat.build_opencode_headers(session_id or self._opencode_session_id)
            )

        if use_responses:
            url = f"{base_url}/responses"
            payload = opencode_compat.build_responses_payload(
                model=payload["model"],
                messages=payload["messages"],
                temperature=payload.get("temperature"),
                max_tokens=payload.get("max_tokens"),
                top_p=payload.get("top_p"),
                reasoning_effort=reasoning_effort,
            )
        else:
            url = f"{base_url}/chat/completions"
            if reasoning_effort:
                payload["reasoning_effort"] = reasoning_effort

        # trust_env=False：绕过系统代理。长补全请求经本地代理会偶发 ReadTimeout，
        # 而直连 OpenAI 兼容网关已验证稳定。
        async with httpx.AsyncClient(timeout=timeout or self.timeout, trust_env=False) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return opencode_compat.normalize_responses_payload(data) if use_responses else data

    @staticmethod
    def _message_content(response: Any) -> str:
        """Extract assistant message content from LiteLLM or raw OpenAI-compatible responses."""
        if isinstance(response, dict):
            choices = response.get("choices") or []
            if not choices:
                return ""
            message = choices[0].get("message") or {}
            return message.get("content") or ""
        return response.choices[0].message.content if response.choices else ""

    def _get_usage_tokens(self, response: Any) -> int:
        usage = getattr(response, "usage", None) or getattr(response, "get", lambda *_: None)("usage")
        if not usage:
            return 0
        total_tokens = None
        if hasattr(usage, "get"):
            total_tokens = usage.get("total_tokens")
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
        else:
            total_tokens = getattr(usage, "total_tokens", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0)
            completion_tokens = getattr(usage, "completion_tokens", 0)
        if total_tokens is None:
            total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
        return int(total_tokens or 0)

    def _get_usage_cost(self, response: Any) -> float:
        try:
            return float(completion_cost(completion_response=response))
        except Exception:
            pass
        try:
            hidden = getattr(response, "_hidden_params", {}) or {}
            return float(hidden.get("response_cost", 0.0) or 0.0)
        except Exception:
            return 0.0

    def _log_usage(
        self,
        response: Any,
        model: str,
        session_id: Optional[str] = None,
    ) -> None:
        try:
            tokens = self._get_usage_tokens(response)
            cost = self._get_usage_cost(response)
            self.usage_store.record_usage(
                model=model,
                tokens=tokens,
                cost=cost,
                session_id=session_id,
            )
        except Exception as exc:
            logger.warning("Usage logging failed: %s", exc)

    def _ensure_api_key(self, model: str, params: Dict[str, Any]) -> None:
        provider = model.split("/", 1)[0].lower() if "/" in model else ""
        if provider == "ollama":
            return
        if params.get("api_key"):
            return
        if provider in {"openai", "alibaba", "zhipu", "anthropic"} or any(
            token in model.lower() for token in ["gpt", "qwen", "glm", "claude"]
        ):
            raise ValueError(f"API key not configured for model '{model}'")
    
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
        """
        Generate agent response using LLM.
        
        Args:
            system_prompt: System prompt with agent personality and rules
            conversation_history: List of previous messages
            iq_level: Agent's IQ level (High/Mid/Low)
            temperature: Sampling temperature
            
        Returns:
            Validated AgentResponse
        """
        model = self._resolve_model(iq_level, model=model, model_config=model_config)
        completion_model = self._get_completion_model(model)
        import time as _time
        _started = _time.perf_counter()

        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        else:
            messages.append({"role": "user", "content": "请根据以上规则开始本轮分析，并只输出 JSON。"})
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Calling LLM (attempt {attempt + 1}/{self.max_retries}): model={model}, iq_level={iq_level}")
                
                # Get provider-specific parameters
                llm_params = self._get_llm_params(model, model_config=model_config)
                self._ensure_api_key(model, llm_params)

                response_format = {"type": "json_object"} if any(token in completion_model.lower() for token in ["gpt", "qwen", "glm"]) else None
                if self._should_use_openai_compatible_http(model_config):
                    # glm/深度思考类模型的推理部分需要预留 token，
                    # 但上限过高会让思考无节制拖慢发言节奏，3000 足够覆盖
                    # thought(500) + speech(220) + 思考开销
                    response = await self._acompletion_openai_compatible(
                        model_config=model_config or {},
                        messages=messages,
                        temperature=temperature,
                        max_tokens=3000,
                        response_format=response_format,
                        timeout=self.timeout,
                        session_id=session_id,
                    )
                else:
                    response = await acompletion(
                        model=completion_model,
                        messages=messages,
                        temperature=temperature,
                        timeout=self.timeout,
                        response_format=response_format,
                        **llm_params
                    )

                self._log_usage(response, model, session_id)

                if not response:
                    raise ValueError("Empty response from LLM")

                content = self._message_content(response)
                if not content:
                    raise ValueError("Empty content in LLM response")

                logger.debug(f"LLM raw response (first 200 chars): {content[:200]}")

                # Try to parse JSON
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parse error: {e}, attempting to extract JSON from text")
                    # Try to extract JSON from text
                    data = self._extract_json_from_text(content)
                    if data is None:
                        raise ValueError(f"Could not extract valid JSON from response. Content: {content[:200]}")

                # Validate with Pydantic
                validated = AgentResponse(**data)

                logger.info(
                    f"Successfully generated agent response in {_time.perf_counter() - _started:.1f}s: {validated.speech[:50]}..."
                )
                return validated
                
            except Exception as e:
                error_detail = f"{type(e).__name__}: {str(e)}"
                logger.error(f"LLM call failed (attempt {attempt + 1}/{self.max_retries}): {error_detail}")
                if attempt == self.max_retries - 1:
                    # Last attempt failed, use fallback
                    fallback_data = self._create_fallback_response(error_detail, iq_level)
                    return AgentResponse(**fallback_data)
                
        # Should not reach here, but just in case
        fallback_data = self._create_fallback_response("Max retries exceeded", iq_level)
        return AgentResponse(**fallback_data)
    
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
        """Generate a group-chat style response (multiple short bubbles)."""
        model = self._resolve_model(iq_level, model=model, model_config=model_config)
        completion_model = self._get_completion_model(model)
        import time as _time
        _started = _time.perf_counter()

        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        else:
            messages.append({"role": "user", "content": "请根据以上规则开始本轮群聊发言，并只输出 JSON。"})

        for attempt in range(self.max_retries):
            try:
                llm_params = self._get_llm_params(model, model_config=model_config)
                self._ensure_api_key(model, llm_params)

                if self._should_use_openai_compatible_http(model_config):
                    response = await self._acompletion_openai_compatible(
                        model_config=model_config or {},
                        messages=messages,
                        temperature=temperature,
                        max_tokens=2000,
                        timeout=self.timeout,
                        session_id=session_id,
                    )
                else:
                    response = await acompletion(
                        model=completion_model,
                        messages=messages,
                        temperature=temperature,
                        timeout=self.timeout,
                        **llm_params
                    )

                self._log_usage(response, model, session_id)

                if not response:
                    raise ValueError("Empty response from LLM")

                content = self._message_content(response)
                if not content:
                    raise ValueError("Empty content in LLM response")

                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    data = self._extract_json_from_text(content)
                    if data is None:
                        raise ValueError(f"Could not extract valid JSON from response. Content: {content[:200]}")

                validated = ChatResponse(**data)
                if not validated.messages:
                    raise ValueError("Chat response contains no messages")
                logger.info(
                    f"Generated chat response in {_time.perf_counter() - _started:.1f}s: {len(validated.messages)} bubbles"
                )
                return validated

            except Exception as e:
                logger.error(f"Chat LLM call failed (attempt {attempt + 1}/{self.max_retries}): {type(e).__name__}: {e}")
                if attempt == self.max_retries - 1:
                    return ChatResponse(thought="思考中...", messages=["……"], suspicion={})

        return ChatResponse(thought="思考中...", messages=["……"], suspicion={})

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
        """
        Generate vote response using LLM.
        
        Args:
            system_prompt: System prompt with voting instructions
            conversation_history: List of previous messages
            iq_level: Agent's IQ level
            valid_agent_ids: List of agent IDs that can be voted for
            temperature: Sampling temperature
            
        Returns:
            Validated VoteResponse
        """
        model = self._resolve_model(iq_level, model=model, model_config=model_config)
        completion_model = self._get_completion_model(model)
        llm_params = self._get_llm_params(model, model_config=model_config)
        self._ensure_api_key(model, llm_params)
        
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        else:
            messages.append({"role": "user", "content": "请根据以上规则做出本轮选择，并只输出 JSON。"})
        
        for attempt in range(self.max_retries):
            try:
                attempt_messages = list(messages)
                if attempt > 0:
                    attempt_messages.append(
                        {
                            "role": "user",
                            "content": (
                                "你上一条回复不符合要求。现在只输出一行合法 JSON，"
                                '字段必须是 "thought"、"vote"、"confidence"，'
                                "vote 只能填写候选 ID，禁止 markdown、禁止解释、禁止额外文本。"
                            ),
                        }
                    )
                response_format = {"type": "json_object"} if any(token in completion_model.lower() for token in ["gpt", "qwen", "glm"]) else None
                if self._should_use_openai_compatible_http(model_config):
                    response = await self._acompletion_openai_compatible(
                        model_config=model_config or {},
                        messages=attempt_messages,
                        temperature=temperature,
                        response_format=response_format,
                        timeout=self.timeout,
                        session_id=session_id,
                    )
                else:
                    response = await acompletion(
                        model=completion_model,
                        messages=attempt_messages,
                        temperature=temperature,
                        timeout=self.timeout,
                        response_format=response_format,
                        **llm_params
                    )

                self._log_usage(response, model, session_id)
                
                content = self._message_content(response)
                
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    data = self._extract_json_from_text(content)
                    if data is None:
                        raise ValueError("Could not extract valid JSON from response")
                
                validated = VoteResponse(**data)
                
                # Validate that vote is for a valid agent
                coerced_vote = self._coerce_vote_choice(validated.vote, valid_agent_ids)
                if coerced_vote is None:
                    logger.warning(f"Invalid vote target: {validated.vote}, choosing random valid agent")
                    import random
                    validated.vote = random.choice(valid_agent_ids)
                else:
                    validated.vote = coerced_vote

                return validated
                
            except Exception as e:
                logger.error(f"Vote generation failed (attempt {attempt + 1}): {e}")
                if attempt == self.max_retries - 1:
                    # Fallback: random vote
                    import random
                    return VoteResponse(
                        thought="【系统错误：无法生成投票】",
                        vote=random.choice(valid_agent_ids),
                        confidence=0.5
                    )
        
        # Fallback
        import random
        return VoteResponse(
            thought="【系统错误：无法生成投票】",
            vote=random.choice(valid_agent_ids),
            confidence=0.5
        )
    
    async def generate_agent_name(
        self,
        mbti_type: str,
        iq_level: str,
        session_id: Optional[str] = None,
        model_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Generate a personalized name for an agent based on their characteristics.

        Args:
            mbti_type: MBTI personality type (e.g., "ENTJ", "INFP")
            iq_level: IQ level (High/Mid/Low)
            model_config: Optional per-agent model configuration dict

        Returns:
            Generated name string (e.g., "一意孤行的小笨仙女")；None 表示生成失败，
            调用方应保留角色库兜底名，而不是退化到旧命名。
        """
        model = self._resolve_model("Mid", model_config=model_config)
        completion_model = self._get_completion_model(model)
        llm_params = self._get_llm_params(model, model_config=model_config)
        self._ensure_api_key(model, llm_params)
        
        # MBTI 性格特征描述
        mbti_descriptions = {
            "ENTJ": "外向、果断、理性、有计划，像指挥官一样",
            "INTJ": "内向、理性、直觉、有计划，像战略家一样",
            "INFP": "内向、感性、直觉、灵活，像理想主义者一样",
            "ENFJ": "外向、感性、直觉、有计划，像导师一样",
            "INTP": "内向、理性、直觉、灵活，像逻辑学家一样",
            "ESTJ": "外向、理性、实际、有计划，像管理者一样",
            "ISFP": "内向、感性、实际、灵活，像艺术家一样",
            "ENTP": "外向、理性、直觉、灵活，像辩论家一样",
            "ISFJ": "内向、感性、实际、有计划，像守护者一样",
            "ESFP": "外向、感性、实际、灵活，像表演者一样",
            "ESFJ": "外向、感性、实际、有计划，像执政官一样",
            "ESTP": "外向、理性、实际、灵活，像企业家一样",
            "INFJ": "内向、感性、直觉、有计划，像提倡者一样",
            "ENFP": "外向、感性、直觉、灵活，像竞选者一样",
            "ISTJ": "内向、理性、实际、有计划，像物流师一样",
            "ISTP": "内向、理性、实际、灵活，像鉴赏家一样",
        }
        
        iq_descriptions = {
            "High": "聪明、睿智、机敏",
            "Mid": "普通、正常、一般",
            "Low": "简单、纯真、直率"
        }
        
        mbti_desc = mbti_descriptions.get(mbti_type, "性格独特")
        iq_desc = iq_descriptions.get(iq_level, "普通")

        prompt = prompt_registry.render("werewolf_naming_prompt", {
            "mbti_type": mbti_type,
            "mbti_desc": mbti_desc,
            "iq_level": iq_level,
            "iq_desc": iq_desc,
        })

        try:
            if self._should_use_openai_compatible_http(model_config):
                response = await self._acompletion_openai_compatible(
                    model_config=model_config or {},
                    messages=[
                        {"role": "system", "content": "你是一个擅长为角色起名的创意助手。请根据角色特征生成有趣、个性化的中文昵称。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.8,
                    max_tokens=20,
                    timeout=self.timeout,
                    session_id=session_id,
                )
            else:
                response = await acompletion(
                    model=completion_model,
                    messages=[
                        {"role": "system", "content": "你是一个擅长为角色起名的创意助手。请根据角色特征生成有趣、个性化的中文昵称。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.8,
                    max_tokens=20,
                    timeout=self.timeout,
                    **llm_params
                )

            name = (self._message_content(response) or "").strip()
            self._log_usage(response, model, session_id)
            # 清理可能的引号或多余字符
            name = name.strip('"\'，。！？\n')

            # 验证长度：2-15 字；不合格时返回 None 让调用方保留角色库兜底名，
            # 而不是退化到「普通的小王子」式的旧命名
            if len(name) < 2 or len(name) > 15:
                logger.warning(f"Generated name '{name}' length invalid, keeping fallback name")
                return None

            logger.info(f"Generated agent name: {name} for {mbti_type} {iq_level}")
            return name

        except Exception as e:
            logger.error(f"Failed to generate agent name: {e}, keeping fallback name")
            return None
    
    async def generate_themed_roster(
        self,
        work: str,
        count: int,
        session_id: Optional[str] = None,
        model_config: Optional[Dict[str, Any]] = None,
    ) -> list[Dict[str, str]]:
        """按指定作品一次性生成一整套角色（name + mbti + gender 绑定）。

        用于狼人杀「主题角色阵容」：一次 LLM 调用产出全部玩家，
        保证同一局内角色名来自同一作品世界观、MBTI 分布分散。
        """
        work = (work or "").strip()
        if not work:
            raise ValueError("作品名不能为空")
        if not 6 <= int(count) <= 12:
            raise ValueError("角色数量需在 6-12 之间")

        prompt = prompt_registry.render("werewolf_roster_prompt", {"work": work, "count": count})

        if self._should_use_openai_compatible_http(model_config):
            response = await self._acompletion_openai_compatible(
                model_config=model_config or {},
                messages=[
                    {"role": "system", "content": "你是狼人杀角色设计师，只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=800,
                timeout=self.timeout,
                session_id=session_id,
            )
        else:
            model = self._resolve_model("Mid", model_config=model_config)
            completion_model = self._get_completion_model(model)
            llm_params = self._get_llm_params(model, model_config=model_config)
            self._ensure_api_key(model, llm_params)
            response = await acompletion(
                model=completion_model,
                messages=[
                    {"role": "system", "content": "你是狼人杀角色设计师，只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=800,
                timeout=self.timeout,
                **llm_params,
            )
        self._log_usage(response, "roster", session_id)

        text = self._message_content(response) or ""
        data = self._extract_roster_json(text)
        if not isinstance(data, list):
            raise ValueError("模型未返回有效的角色数组")

        valid_mbti = {
            "ENTJ", "INFP", "ISTP", "ENFJ", "INTP", "ESTJ", "ISFP", "ENTP",
            "ISFJ", "ESFP", "INTJ", "ESFJ", "ESTP", "INFJ", "ENFP", "ISTJ",
        }
        roster: list[Dict[str, str]] = []
        seen: set[str] = set()
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            mbti = str(item.get("mbti") or "").strip().upper()
            gender = str(item.get("gender") or "").strip()
            if not (2 <= len(name) <= 8) or name in seen:
                continue
            if mbti not in valid_mbti:
                continue
            gender = "女" if "女" in gender else "男"
            seen.add(name)
            roster.append({"name": name, "mbti": mbti, "gender": gender})

        if len(roster) < int(count):
            raise ValueError(f"模型只生成了 {len(roster)} 个有效角色（需要 {count}），请重试")
        return roster[: int(count)]

    def _extract_roster_json(self, text: str) -> Optional[Any]:
        """从模型输出里提取 JSON（兼容数组与 {"roles": [...]} 两种形状）。"""
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        start_idx, end_idx = text.find("["), text.rfind("]")
        if start_idx != -1 and end_idx > start_idx:
            try:
                return json.loads(text[start_idx : end_idx + 1])
            except json.JSONDecodeError:
                pass
        obj = self._extract_json_from_text(text)
        if isinstance(obj, dict) and isinstance(obj.get("roles"), list):
            return obj["roles"]
        return None

    def _generate_fallback_name(self, mbti_type: str, iq_level: str) -> str:
        """Generate a fallback name when LLM fails."""
        # 简单的规则生成
        traits = {
            "High": ["聪明", "睿智", "机敏"],
            "Mid": ["普通", "正常", "一般"],
            "Low": ["简单", "纯真", "直率"]
        }
        
        suffixes = {
            "E": "小王子",
            "I": "小仙女",
            "F": "小甜心",
            "T": "小战士"
        }
        
        import random
        trait = random.choice(traits.get(iq_level, ["普通"]))
        suffix = suffixes.get(mbti_type[0] if mbti_type else "I", "小角色")
        
        return f"{trait}的{suffix}"

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 256,
        model: Optional[str] = None,
        model_config: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        json_mode: bool = True,
        **extra_params: Any,
    ) -> str:
        """Generate a raw text completion from a prompt."""
        resolved_model = self._resolve_model("Mid", model=model, model_config=model_config)
        completion_model = self._get_completion_model(resolved_model)
        llm_params = self._get_llm_params(resolved_model, model_config=model_config)
        self._ensure_api_key(resolved_model, llm_params)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response_format = {"type": "json_object"} if json_mode and any(token in completion_model.lower() for token in ["gpt", "qwen", "glm"]) else None
        if self._should_use_openai_compatible_http(model_config):
            response = await self._acompletion_openai_compatible(
                model_config=model_config or {},
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                timeout=self.timeout,
                session_id=session_id,
                **extra_params,
            )
        else:
            response = await acompletion(
                model=completion_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=self.timeout,
                response_format=response_format,
                **llm_params,
                **extra_params,
            )

        content = self._message_content(response)
        self._log_usage(response, resolved_model, session_id)
        return content or ""
    
    async def health_check(self, model: str) -> Dict[str, Any]:
        """
        Check if a model is accessible.
        
        Args:
            model: Model identifier (e.g., "openai/gpt-4o")
            
        Returns:
            Dict with status and details
        """
        try:
            llm_params = self._get_llm_params(model)
            self._ensure_api_key(model, llm_params)
            completion_model = self._get_completion_model(model)
            response = await acompletion(
                model=completion_model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5,
                timeout=10,
                **llm_params
            )
            self._log_usage(response, model, None)
            return {
                "model": model,
                "status": "healthy",
                "provider": response.model
            }
        except Exception as e:
            return {
                "model": model,
                "status": "unhealthy",
                "error": str(e)
            }
