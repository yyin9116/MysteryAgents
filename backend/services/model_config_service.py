"""
Service for managing LLM model configurations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import time

from sqlalchemy.orm import Session
from litellm import completion

from config.settings import settings
from database.model_config import ModelConfigORM
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


class ModelConfigService:
    """Service for CRUD operations on model configs."""

    def __init__(self, db: Session):
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

        if config.provider.lower() == "mock" or config.model.lower() == "mock":
            return {
                "success": True,
                "message": "Mock test succeeded.",
                "response": "pong",
                "duration_ms": 0,
            }

        model_name = self._build_model_name(config.provider, config.model)
        api_key = config.api_key or self._get_api_key(config.provider)
        api_base = config.base_url or self._get_api_base(config.provider)

        params = self._build_completion_params(config)

        start_time = time.monotonic()
        response = completion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            api_key=api_key,
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
    def _build_completion_params(config: ModelConfigORM) -> Dict[str, Any]:
        params: Dict[str, Any] = {"temperature": config.temperature}

        if config.max_tokens is not None:
            params["max_tokens"] = config.max_tokens
        if config.top_p is not None:
            params["top_p"] = config.top_p
        if config.frequency_penalty is not None:
            params["frequency_penalty"] = config.frequency_penalty
        if config.presence_penalty is not None:
            params["presence_penalty"] = config.presence_penalty
        if config.extra_params:
            params.update(config.extra_params)

        return params

    @staticmethod
    def _build_model_name(provider: str, model: str) -> str:
        if "/" in model:
            return model
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
