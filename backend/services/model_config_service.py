"""
Service for managing LLM model configurations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import time

import httpx
from sqlalchemy.orm import Session
from litellm import completion

from config.settings import settings
from database.model_config import ModelConfigORM
from utils import opencode_compat
from models.model_config import (
    ModelConfigCreate,
    ModelConfigExport,
    ModelConfigImport,
    ModelConfigImportItem,
    ModelConfigRead,
    ModelConfigUpdate,
)


class ModelConfigNotFoundError(Exception):
    """Raised when a model config is not found."""


class ModelConfigConflictError(Exception):
    """Raised when a model config conflicts with existing data."""


# 前端保存的配置可能 base_url 为空（走协议默认值），拉取模型列表时需要一个兜底映射
_PROVIDER_DEFAULT_BASE_URL: Dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "opencode": "https://opencode.ai/zen/go/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta",
    "deepseek": "https://api.deepseek.com/v1",
    "alibaba": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "ollama": "http://localhost:11434/v1",
}


class ModelConfigService:
    """Service for CRUD operations on model configs."""

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def create_config(self, config_in: ModelConfigCreate) -> ModelConfigRead:
        existing = self.db.query(ModelConfigORM).filter(ModelConfigORM.name == config_in.name).first()
        if existing:
            raise ModelConfigConflictError("Model config name already exists.")

        config = ModelConfigORM(
            name=config_in.name,
            description=config_in.description,
            provider=config_in.provider,
            model=config_in.model,
            temperature=config_in.temperature,
            max_tokens=config_in.max_tokens,
            top_p=config_in.top_p,
            frequency_penalty=config_in.frequency_penalty,
            presence_penalty=config_in.presence_penalty,
            api_key=config_in.api_key,
            base_url=config_in.base_url,
            extra_params=config_in.extra_params or {},
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return self._to_read_model(config)

    def get_config(self, config_id: str) -> ModelConfigRead:
        config = self.db.get(ModelConfigORM, config_id)
        if not config:
            raise ModelConfigNotFoundError("Model config not found.")
        return self._to_read_model(config)

    def list_configs(self, skip: int = 0, limit: int = 100) -> List[ModelConfigRead]:
        configs = (
            self.db.query(ModelConfigORM)
            .order_by(ModelConfigORM.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [self._to_read_model(config) for config in configs]

    def update_config(self, config_id: str, config_in: ModelConfigUpdate) -> ModelConfigRead:
        config = self.db.get(ModelConfigORM, config_id)
        if not config:
            raise ModelConfigNotFoundError("Model config not found.")

        if config_in.version is not None and config.version != config_in.version:
            raise ModelConfigConflictError("Model config version mismatch.")

        if config_in.name and config_in.name != config.name:
            existing = self.db.query(ModelConfigORM).filter(ModelConfigORM.name == config_in.name).first()
            if existing:
                raise ModelConfigConflictError("Model config name already exists.")

        update_data = config_in.dict(exclude_unset=True)
        update_data.pop("version", None)

        for field, value in update_data.items():
            setattr(config, field, value)

        config.version += 1
        config.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(config)
        return self._to_read_model(config)

    def delete_config(self, config_id: str) -> ModelConfigRead:
        config = self.db.get(ModelConfigORM, config_id)
        if not config:
            raise ModelConfigNotFoundError("Model config not found.")

        result = self._to_read_model(config)
        self.db.delete(config)
        self.db.commit()
        return result

    def export_configs(self) -> ModelConfigExport:
        configs = self.list_configs(skip=0, limit=1000)
        return ModelConfigExport(configs=configs)

    def import_configs(self, payload: ModelConfigImport) -> Dict[str, int]:
        created = 0
        updated = 0
        skipped = 0

        for item in payload.configs:
            existing = self._find_existing_config(item)
            if existing and not payload.overwrite:
                skipped += 1
                continue

            if existing:
                self._apply_import_item(existing, item)
                if item.version is not None:
                    existing.version = item.version
                else:
                    existing.version += 1
                if item.created_at:
                    existing.created_at = self._parse_datetime(item.created_at) or existing.created_at
                existing.updated_at = self._parse_datetime(item.updated_at) or datetime.utcnow()
                updated += 1
            else:
                config = ModelConfigORM(
                    id=item.id,
                    name=item.name,
                    description=item.description,
                    provider=item.provider,
                    model=item.model,
                    temperature=item.temperature,
                    max_tokens=item.max_tokens,
                    top_p=item.top_p,
                    frequency_penalty=item.frequency_penalty,
                    presence_penalty=item.presence_penalty,
                    api_key=item.api_key,
                    base_url=item.base_url,
                    extra_params=item.extra_params or {},
                    version=item.version or 1,
                    created_at=self._parse_datetime(item.created_at) or datetime.utcnow(),
                    updated_at=self._parse_datetime(item.updated_at) or datetime.utcnow(),
                )
                self.db.add(config)
                created += 1

        self.db.commit()
        return {"created": created, "updated": updated, "skipped": skipped}

    def test_config(self, config_id: str, prompt: str) -> Dict[str, Any]:
        config = self.db.get(ModelConfigORM, config_id)
        if not config:
            raise ModelConfigNotFoundError("Model config not found.")

        return self._run_completion_test(
            provider=config.provider,
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            frequency_penalty=config.frequency_penalty,
            presence_penalty=config.presence_penalty,
            extra_params=config.extra_params or {},
            prompt=prompt,
        )

    def test_draft(
        self,
        provider: str,
        model: str,
        prompt: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Test an unsaved configuration draft directly from request fields."""
        return self._run_completion_test(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            extra_params=extra_params or {},
            prompt=prompt,
        )

    def list_models_for_config(self, config_id: str) -> Dict[str, Any]:
        """Fetch the live model list from the provider of a saved config."""
        config = self.db.get(ModelConfigORM, config_id)
        if not config:
            raise ModelConfigNotFoundError("Model config not found.")
        return self._list_models(
            provider=config.provider,
            api_key=config.api_key,
            base_url=config.base_url,
        )

    def list_models_draft(
        self,
        *,
        provider: str,
        api_key: Optional[str],
        base_url: Optional[str],
    ) -> Dict[str, Any]:
        """Fetch the live model list for an unsaved draft (form current values)."""
        return self._list_models(provider=provider, api_key=api_key, base_url=base_url)

    @classmethod
    def _list_models(
        cls,
        *,
        provider: str,
        api_key: Optional[str],
        base_url: Optional[str],
    ) -> Dict[str, Any]:
        """GET {base_url}/models on an OpenAI-compatible endpoint.

        Reuses the same credential/header rules as the completion test path,
        so a successful fetch here means the credentials work in-game too.
        """
        provider_key = (provider or "").strip().lower()
        resolved_key = api_key or cls._get_api_key(provider_key)
        api_base = (
            base_url
            or cls._get_api_base(provider_key)
            or _PROVIDER_DEFAULT_BASE_URL.get(provider_key)
        )
        if not api_base:
            raise RuntimeError(
                "无法确定服务端点：请先在配置中填写 Base URL。"
            )

        headers = {"Accept-Encoding": "identity"}
        if provider_key == "anthropic":
            # Anthropic 的 /v1/models 使用 x-api-key + anthropic-version
            headers["x-api-key"] = resolved_key or ""
            headers["anthropic-version"] = "2023-06-01"
        elif resolved_key:
            headers["Authorization"] = f"Bearer {resolved_key}"
        if opencode_compat.is_opencode_go(api_base):
            headers.update(opencode_compat.build_opencode_headers())

        base = api_base.rstrip("/")
        candidate_urls = [f"{base}/models"]
        # Google 的 OpenAI 兼容层在 /v1beta/openai/models，先试标准路径再补一次
        if "generativelanguage" in base and "/openai" not in base:
            candidate_urls.append(f"{base}/openai/models")

        last_error: Optional[str] = None
        for url in candidate_urls:
            try:
                with httpx.Client(timeout=15.0, trust_env=False) as client:
                    response = client.get(url, headers=headers)
                    response.raise_for_status()
                    data = response.json()
            except httpx.HTTPStatusError as exc:
                body = (exc.response.text or "")[:200]
                last_error = f"HTTP {exc.response.status_code} from {url}: {body}"
                continue
            except httpx.HTTPError as exc:
                last_error = f"请求失败 {url}: {exc}"
                continue

            models = cls._parse_models_payload(data)
            if models:
                return {"models": models, "source": "remote", "count": len(models)}
            last_error = f"端点 {url} 返回了无法解析的模型列表。"

        raise RuntimeError(last_error or "模型列表获取失败。")

    @staticmethod
    def _parse_models_payload(data: Any) -> List[str]:
        """Accept both {"data": [{"id": ...}]} (OpenAI) and bare list payloads."""
        items: Any = data
        if isinstance(data, dict):
            items = data.get("data") or data.get("models") or []
        if not isinstance(items, list):
            return []
        ids: List[str] = []
        for item in items:
            if isinstance(item, dict):
                model_id = item.get("id") or item.get("name")
            else:
                model_id = item
            if isinstance(model_id, str) and model_id.strip():
                ids.append(model_id.strip())
        # Gemini 的 OpenAI 兼容层会返回 "models/gemini-xxx" 前缀形式
        ids = [m.split("/", 1)[1] if m.startswith("models/") else m for m in ids]
        return sorted(set(ids))

    def _run_completion_test(
        self,
        *,
        provider: str,
        model: str,
        prompt: str,
        api_key: Optional[str],
        base_url: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        top_p: Optional[float],
        frequency_penalty: Optional[float],
        presence_penalty: Optional[float],
        extra_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        if provider.lower() == "mock" or model.lower() == "mock":
            return {
                "success": True,
                "message": "Mock test succeeded.",
                "response": "pong",
                "duration_ms": 0,
            }

        model_name = self._build_model_name(provider, model)
        resolved_key = api_key or self._get_api_key(provider)
        api_base = base_url or self._get_api_base(provider)

        params = self._build_completion_params(
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            extra_params=extra_params,
        )

        # OpenAI-compatible endpoints with an explicit base_url are tested
        # through the same direct-HTTP path the game runtime uses, so the
        # test result reflects real in-game behaviour (including OpenCode Go).
        if provider.lower() in {"openai", "opencode"} and api_base:
            content, elapsed_ms = self._direct_http_completion(
                model=model,
                api_key=resolved_key,
                api_base=api_base,
                prompt=prompt,
                params=params,
            )
            return {
                "success": True,
                "message": "Model test succeeded.",
                "response": content,
                "duration_ms": elapsed_ms,
            }

        start_time = time.monotonic()
        response = completion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            api_key=resolved_key,
            api_base=api_base,
            **params,
        )
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        content = None
        try:
            content = response["choices"][0]["message"]["content"]
        except Exception:
            content = str(response)

        return {
            "success": True,
            "message": "Model test succeeded.",
            "response": content,
            "duration_ms": elapsed_ms,
        }

    @staticmethod
    def _to_read_model(config: ModelConfigORM) -> ModelConfigRead:
        return ModelConfigRead(
            id=config.id,
            name=config.name,
            description=config.description,
            provider=config.provider,
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            frequency_penalty=config.frequency_penalty,
            presence_penalty=config.presence_penalty,
            api_key=config.api_key,
            base_url=config.base_url,
            extra_params=config.extra_params or {},
            version=config.version,
            created_at=config.created_at.isoformat(),
            updated_at=config.updated_at.isoformat(),
        )

    def _find_existing_config(self, item: ModelConfigImportItem) -> Optional[ModelConfigORM]:
        if item.id:
            existing = self.db.get(ModelConfigORM, item.id)
            if existing:
                return existing
        return self.db.query(ModelConfigORM).filter(ModelConfigORM.name == item.name).first()

    @staticmethod
    def _apply_import_item(config: ModelConfigORM, item: ModelConfigImportItem) -> None:
        config.name = item.name
        config.description = item.description
        config.provider = item.provider
        config.model = item.model
        config.temperature = item.temperature
        config.max_tokens = item.max_tokens
        config.top_p = item.top_p
        config.frequency_penalty = item.frequency_penalty
        config.presence_penalty = item.presence_penalty
        config.api_key = item.api_key
        config.base_url = item.base_url
        config.extra_params = item.extra_params or {}

    @staticmethod
    def _build_completion_params(
        *,
        temperature: Optional[float],
        max_tokens: Optional[int],
        top_p: Optional[float],
        frequency_penalty: Optional[float],
        presence_penalty: Optional[float],
        extra_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"temperature": temperature if temperature is not None else 0.7}

        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if top_p is not None:
            params["top_p"] = top_p
        if frequency_penalty is not None:
            params["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            params["presence_penalty"] = presence_penalty
        if extra_params:
            params.update(extra_params)

        return params

    @staticmethod
    def _direct_http_completion(
        *,
        model: str,
        api_key: Optional[str],
        api_base: str,
        prompt: str,
        params: Dict[str, Any],
    ) -> Tuple[str, int]:
        """Call an OpenAI-compatible endpoint over plain HTTP.

        Mirrors LLMService._acompletion_openai_compatible so a successful test
        means the same request shape works during games (OpenCode Go session
        headers and Responses-API models are handled identically).
        """
        headers = {"Content-Type": "application/json", "Accept-Encoding": "identity"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if opencode_compat.is_opencode_go(api_base):
            headers.update(opencode_compat.build_opencode_headers())

        messages = [{"role": "user", "content": prompt}]
        base = api_base.rstrip("/")
        use_responses = opencode_compat.needs_responses_api(model)
        if use_responses:
            url = f"{base}/responses"
            payload = opencode_compat.build_responses_payload(
                model=model,
                messages=messages,
                temperature=params.get("temperature"),
                max_tokens=params.get("max_tokens"),
                top_p=params.get("top_p"),
            )
        else:
            url = f"{base}/chat/completions"
            payload = {"model": model, "messages": messages}
            payload.update(params)

        start_time = time.monotonic()
        try:
            # trust_env=False 与运行时直连路径保持一致，绕过系统代理
            with httpx.Client(timeout=60.0, trust_env=False) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            body = (exc.response.text or "")[:300]
            raise RuntimeError(
                f"HTTP {exc.response.status_code} from {url}: {body}"
            ) from exc
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        if use_responses:
            data = opencode_compat.normalize_responses_payload(data)
        choices = data.get("choices") or []
        content = None
        if choices:
            content = (choices[0].get("message") or {}).get("content")
        return (content if content is not None else str(data)), elapsed_ms

    @staticmethod
    def _build_model_name(provider: str, model: str) -> str:
        if "/" in model:
            return model
        if provider.lower() == "opencode":
            # LiteLLM has no native opencode provider; it is OpenAI-compatible.
            return f"openai/{model}"
        return f"{provider}/{model}"

    @staticmethod
    def _get_api_key(provider: str) -> Optional[str]:
        provider = provider.lower()
        if provider == "openai":
            return settings.OPENAI_API_KEY
        if provider == "alibaba":
            return settings.ALIBABA_API_KEY
        if provider == "anthropic":
            return settings.ANTHROPIC_API_KEY
        if provider == "zhipu":
            return settings.ZHIPU_API_KEY
        return None

    @staticmethod
    def _get_api_base(provider: str) -> Optional[str]:
        provider = provider.lower()
        if provider == "alibaba":
            return settings.ALIBABA_BASE_URL
        if provider == "zhipu":
            return settings.ZHIPU_BASE_URL
        if provider == "ollama":
            return settings.OLLAMA_BASE_URL
        return None

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
