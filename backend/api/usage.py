"""
Usage statistics API endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.models import MODEL_CATALOG
from models.usage import UsageAggregate, UsageSummary
from services.usage_store import UsageStore

router = APIRouter(prefix="/api/usage", tags=["usage"])

TIME_GROUPS = {"hour", "day", "week", "month"}


class UsageStatsResponse(BaseModel):
    """Usage statistics response payload."""

    summary: UsageSummary
    by_model: list[UsageAggregate]
    by_time: list[UsageAggregate]
    group_by: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    model: Optional[str] = None


def _parse_datetime(value: Optional[str], field_name: str) -> Optional[datetime]:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail=f"{field_name} cannot be empty")
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} format. Use ISO 8601.",
        ) from exc


def get_usage_store() -> UsageStore:
    store = UsageStore()
    try:
        yield store
    finally:
        store.dispose()


def _validate_model(model: Optional[str], store: UsageStore) -> Optional[str]:
    if model is None:
        return None
    cleaned = model.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="model cannot be empty")
    if cleaned in MODEL_CATALOG:
        return cleaned
    if store.model_exists(cleaned):
        return cleaned
    raise HTTPException(status_code=400, detail=f"Unknown model: {cleaned}")


@router.get("/stats", response_model=UsageStatsResponse)
def get_usage_stats(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    group_by: str = Query("day"),
    store: UsageStore = Depends(get_usage_store),
):
    start_time = _parse_datetime(start_date, "start_date")
    end_time = _parse_datetime(end_date, "end_date")
    if start_time and end_time and start_time > end_time:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    normalized_group_by = group_by.strip().lower()
    if normalized_group_by not in TIME_GROUPS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid group_by. Expected one of: {', '.join(sorted(TIME_GROUPS))}",
        )

    cleaned_model = _validate_model(model, store)

    summary = store.get_usage_summary(
        start_time=start_time,
        end_time=end_time,
        model=cleaned_model,
    )
    by_model = store.get_usage_aggregates(
        "model",
        start_time=start_time,
        end_time=end_time,
        model=cleaned_model,
    )
    by_time = store.get_usage_aggregates(
        normalized_group_by,
        start_time=start_time,
        end_time=end_time,
        model=cleaned_model,
    )

    return UsageStatsResponse(
        summary=summary,
        by_model=by_model,
        by_time=by_time,
        group_by=normalized_group_by,
        start_date=start_time,
        end_date=end_time,
        model=cleaned_model,
    )
