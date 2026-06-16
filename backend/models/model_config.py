"""
Pydantic models for LLM model configuration.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


class ModelConfigBase(BaseModel):
    """Shared fields for model configuration."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    provider: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=100)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    api_key: Optional[str] = Field(default=None, min_length=1, max_length=255)
    base_url: Optional[str] = Field(default=None, min_length=1, max_length=255)
    extra_params: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "provider", "model", mode="before")
    @classmethod
    def strip_required_strings(cls, value):
        if not isinstance(value, str):
            raise ValueError("Must be a string")
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned

    @field_validator("description", "api_key", "base_url", mode="before")
    @classmethod
    def strip_optional_strings(cls, value):
        return _clean_optional(value)


class ModelConfigCreate(ModelConfigBase):
    """Create request for model configuration."""


class ModelConfigUpdate(BaseModel):
    """Update request for model configuration."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    provider: Optional[str] = Field(default=None, min_length=1, max_length=50)
    model: Optional[str] = Field(default=None, min_length=1, max_length=100)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    api_key: Optional[str] = Field(default=None, min_length=1, max_length=255)
    base_url: Optional[str] = Field(default=None, min_length=1, max_length=255)
    extra_params: Optional[Dict[str, Any]] = None
    version: Optional[int] = Field(default=None, ge=1)

    @field_validator("name", "provider", "model", mode="before")
    @classmethod
    def strip_optional_required_strings(cls, value):
        if value is None:
            return value
        if not isinstance(value, str):
            raise ValueError("Must be a string")
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned

    @field_validator("description", "api_key", "base_url", mode="before")
    @classmethod
    def strip_optional_strings(cls, value):
        return _clean_optional(value)


class ModelConfigRead(ModelConfigBase):
    """Response model for model configuration."""

    id: str
    version: int
    created_at: str
    updated_at: str


class ModelConfigImportItem(ModelConfigBase):
    """Item for import payload."""

    id: Optional[str] = None
    version: Optional[int] = Field(default=None, ge=1)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ModelConfigExport(BaseModel):
    """Export payload for model configs."""

    version: str = "1.0.0"
    exported_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    configs: List[ModelConfigRead]


class ModelConfigImport(BaseModel):
    """Import payload for model configs."""

    version: str = "1.0.0"
    configs: List[ModelConfigImportItem]
    overwrite: bool = False

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if value != "1.0.0":
            raise ValueError("Unsupported version. Expected 1.0.0")
        return value


class ModelConfigTestRequest(BaseModel):
    """Request body for testing a model configuration."""

    prompt: str = Field(default="Respond with the word 'pong'.", min_length=1, max_length=500)


class ModelConfigTestResponse(BaseModel):
    """Response for model configuration test."""

    success: bool
    message: str
    response: Optional[str] = None
    duration_ms: Optional[int] = None
