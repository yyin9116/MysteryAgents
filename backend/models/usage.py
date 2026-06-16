"""Pydantic models for usage tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UsageRecordCreate(BaseModel):
    """Payload for creating a usage record."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    model: str
    tokens: int = Field(..., ge=0)
    cost: float = Field(..., ge=0.0)
    session_id: Optional[str] = None


class UsageRecord(UsageRecordCreate):
    """Stored usage record with identifier."""

    id: int


class UsageSummary(BaseModel):
    """Summary totals for a set of usage records."""

    total_tokens: int
    total_cost: float
    call_count: int


class UsageAggregate(UsageSummary):
    """Aggregated usage grouped by a dimension."""

    group_by: str
    group_value: str
