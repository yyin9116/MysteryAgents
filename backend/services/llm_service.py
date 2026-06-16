"""
LLM Service using LiteLLM for unified model access.

Supports multiple providers: OpenAI, Alibaba Qwen, Anthropic, Ollama
"""

import json
from typing import Dict, Any, Optional
import httpx
from litellm import acompletion, completion_cost
from pydantic import BaseModel, Field, ConfigDict, field_validator
import logging
logger = logging.getLogger(__name__)

from config.settings import settings
from services.usage_store import UsageStore


class AgentResponse(BaseModel):
    """Validated agent response schema."""
    model_config = ConfigDict(extra="allow")

    thought: str = Field(..., max_length=500)
    speech: str = Field(..., max_length=220)
    suspicion: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('suspicion', mode='before')
    @classmethod
    def validate_suspicion_scores(cls, v: Dict[str, Any]) -> Dict[str, int]:
        normalized: Dict[str, int] = {}
        for agent_id, score in v.items():
            try:
                numeric_score = float(score)
                normalized[agent_id] = max(0, min(10, int(round(numeric_score))))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Suspicion score must be int-like, got {type(score)}") from exc
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


class LLMService:
    """Service for LLM interactions using LiteLLM."""
    
    def __init__(self, usage_store: Optional[UsageStore] = None):
        self.timeout = settings.LLM_TIMEOUT
        self.max_retries = settings.LLM_MAX_RETRIES
        self.usage_store = usage_store or UsageStore()
        
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
        if provider.lower() in {"alibaba", "zhipu"}:
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
        """Use direct HTTP for local OpenAI-compatible endpoints that LiteLLM may mis-decode."""
        if not model_config:
            return False
        provider = (model_config.get("provider") or "").lower()
        base_url = (model_config.get("base_url") or "").strip()
        return provider == "openai" and bool(base_url)

    async def _acompletion_openai_compatible(
        self,
        *,
        model_config: Dict[str, Any],
        messages: list[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        **extra_params: Any,
    ) -> Dict[str, Any]:
        """Call an OpenAI-compatible chat completions endpoint without LiteLLM."""
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
        api_key = model_config.get("api_key") or "local-dev-key"
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

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
                    response = await self._acompletion_openai_compatible(
                        model_config=model_config or {},
                        messages=messages,
                        temperature=temperature,
                        response_format=response_format,
                        timeout=self.timeout,
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
                
                logger.info(f"Successfully generated agent response: {validated.speech[:50]}...")
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
    ) -> str:
        """
        Generate a personalized name for an agent based on their characteristics.
        
        Args:
            mbti_type: MBTI personality type (e.g., "ENTJ", "INFP")
            iq_level: IQ level (High/Mid/Low)
            
        Returns:
            Generated name string (e.g., "一意孤行的小笨仙女")
        """
        # Use a simple model for name generation (Mid IQ model is usually cheaper)
        model = self._get_model_for_iq("Mid")
        llm_params = self._get_llm_params(model)
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
        
        prompt = f"""请为这个角色生成一个个性化的中文昵称。

角色特征：
- MBTI 类型：{mbti_type} ({mbti_desc})
- 智商水平：{iq_level} ({iq_desc})

要求：
1. 昵称应该体现角色的性格特征和智商水平
2. 格式类似："一意孤行的小笨仙女"、"理性果断的小王子"、"温柔体贴的小甜心"
3. 昵称应该有趣、有个性，符合角色的性格
4. 只返回昵称，不要其他解释
5. 昵称长度在 6-12 个汉字之间

请直接返回昵称，不要加引号或其他符号："""

        try:
            response = await acompletion(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一个擅长为角色起名的创意助手。请根据角色特征生成有趣、个性化的中文昵称。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=20,
                timeout=self.timeout,
                **llm_params
            )
            
            name = response.choices[0].message.content.strip()
            self._log_usage(response, model, session_id)
            # 清理可能的引号或多余字符
            name = name.strip('"\'，。！？\n')
            
            # 验证长度
            if len(name) < 4 or len(name) > 15:
                logger.warning(f"Generated name '{name}' length invalid, using fallback")
                return self._generate_fallback_name(mbti_type, iq_level)
            
            logger.info(f"Generated agent name: {name} for {mbti_type} {iq_level}")
            return name
            
        except Exception as e:
            logger.error(f"Failed to generate agent name: {e}, using fallback")
            return self._generate_fallback_name(mbti_type, iq_level)
    
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
