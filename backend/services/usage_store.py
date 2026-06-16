"""Usage persistence and aggregation service."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import func, select

from config.settings import settings
from database.engine import create_db_engine, create_session_factory
from database.migrations import initialize_database
from database.usage import UsageRecord as UsageRecordModel
from models.usage import UsageAggregate, UsageRecord, UsageRecordCreate, UsageSummary

logger = logging.getLogger(__name__)


class UsageStore:
    """Store usage records and provide aggregation queries."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        redis_url: Optional[str] = None,
        cache_enabled: Optional[bool] = None,
        cache_ttl_seconds: Optional[int] = None,
        engine=None,
    ) -> None:
        self._engine = engine or create_db_engine(database_url)
        initialize_database(self._engine)
        self._SessionLocal = create_session_factory(self._engine)

        self._cache_enabled = (
            cache_enabled if cache_enabled is not None else settings.USAGE_CACHE_ENABLED
        )
        self._cache_ttl_seconds = (
            cache_ttl_seconds
            if cache_ttl_seconds is not None
            else settings.USAGE_CACHE_TTL_SECONDS
        )
        self._cache_prefix = settings.USAGE_CACHE_PREFIX
        self._cache = None
        self._init_cache(redis_url or settings.REDIS_URL)

    @property
    def engine(self):
        return self._engine

    def _init_cache(self, redis_url: Optional[str]) -> None:
        if not self._cache_enabled or not redis_url:
            return
        try:
            import redis  # type: ignore

            self._cache = redis.Redis.from_url(redis_url, decode_responses=True)
            self._cache.ping()
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Redis cache disabled: %s", exc)
            self._cache = None

    def _cache_key(self, suffix: str, params: dict) -> str:
        payload = json.dumps(params, sort_keys=True, default=str)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{self._cache_prefix}:{suffix}:{digest}"

    def _cache_get(self, key: str):
        if not self._cache:
            return None
        try:
            cached = self._cache.get(key)
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Cache get failed: %s", exc)
            return None
        if not cached:
            return None
        return json.loads(cached)

    def _cache_set(self, key: str, value: dict) -> None:
        if not self._cache:
            return
        try:
            payload = json.dumps(value, default=str)
            self._cache.setex(key, self._cache_ttl_seconds, payload)
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Cache set failed: %s", exc)

    def _invalidate_cache(self) -> None:
        if not self._cache:
            return
        try:
            keys = list(self._cache.scan_iter(f"{self._cache_prefix}:*"))
            if keys:
                self._cache.delete(*keys)
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Cache invalidate failed: %s", exc)

    def record_usage(
        self,
        model: str,
        tokens: int,
        cost: float,
        session_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> UsageRecord:
        """Insert a usage record."""
        payload = UsageRecordCreate(
            timestamp=timestamp or datetime.utcnow(),
            model=model,
            tokens=tokens,
            cost=cost,
            session_id=session_id,
        )

        session = self._SessionLocal()
        try:
            record = UsageRecordModel(
                timestamp=payload.timestamp,
                model=payload.model,
                tokens=payload.tokens,
                cost=payload.cost,
                session_id=payload.session_id,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        self._invalidate_cache()
        return UsageRecord(
            id=record.id,
            timestamp=record.timestamp,
            model=record.model,
            tokens=record.tokens,
            cost=record.cost,
            session_id=record.session_id,
        )

    def record_usage_batch(self, records: Iterable[UsageRecordCreate]) -> int:
        """Insert a batch of usage records."""
        session = self._SessionLocal()
        try:
            entries = [
                UsageRecordModel(
                    timestamp=record.timestamp,
                    model=record.model,
                    tokens=record.tokens,
                    cost=record.cost,
                    session_id=record.session_id,
                )
                for record in records
            ]
            session.add_all(entries)
            session.commit()
            count = len(entries)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        if count:
            self._invalidate_cache()
        return count

    def list_usage(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[UsageRecord]:
        """Fetch usage records with optional filters."""
        query = select(UsageRecordModel)
        if start_time:
            query = query.where(UsageRecordModel.timestamp >= start_time)
        if end_time:
            query = query.where(UsageRecordModel.timestamp <= end_time)
        if model:
            query = query.where(UsageRecordModel.model == model)
        if session_id:
            query = query.where(UsageRecordModel.session_id == session_id)
        query = query.order_by(UsageRecordModel.timestamp.asc())
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

        session = self._SessionLocal()
        try:
            rows = session.execute(query).scalars().all()
        finally:
            session.close()

        return [
            UsageRecord(
                id=row.id,
                timestamp=row.timestamp,
                model=row.model,
                tokens=row.tokens,
                cost=row.cost,
                session_id=row.session_id,
            )
            for row in rows
        ]

    def model_exists(self, model: str) -> bool:
        """Check whether a model appears in usage records."""
        query = select(UsageRecordModel.id).where(UsageRecordModel.model == model).limit(1)
        session = self._SessionLocal()
        try:
            return session.execute(query).scalar() is not None
        finally:
            session.close()

    def get_usage_summary(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> UsageSummary:
        """Return total tokens, cost, and call count for matching records."""
        cache_key = None
        if self._cache:
            cache_key = self._cache_key(
                "summary",
                {
                    "start_time": start_time,
                    "end_time": end_time,
                    "model": model,
                    "session_id": session_id,
                },
            )
            cached = self._cache_get(cache_key)
            if cached:
                return UsageSummary(**cached)

        query = select(
            func.coalesce(func.sum(UsageRecordModel.tokens), 0),
            func.coalesce(func.sum(UsageRecordModel.cost), 0.0),
            func.count(UsageRecordModel.id),
        )
        if start_time:
            query = query.where(UsageRecordModel.timestamp >= start_time)
        if end_time:
            query = query.where(UsageRecordModel.timestamp <= end_time)
        if model:
            query = query.where(UsageRecordModel.model == model)
        if session_id:
            query = query.where(UsageRecordModel.session_id == session_id)

        session = self._SessionLocal()
        try:
            total_tokens, total_cost, call_count = session.execute(query).one()
        finally:
            session.close()

        summary = UsageSummary(
            total_tokens=int(total_tokens or 0),
            total_cost=float(total_cost or 0.0),
            call_count=int(call_count or 0),
        )
        if cache_key:
            self._cache_set(cache_key, summary.model_dump())
        return summary

    def get_usage_aggregates(
        self,
        group_by: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> list[UsageAggregate]:
        """Aggregate usage by model, session, or time buckets."""
        group_by = group_by.lower()
        group_expr = self._group_expression(group_by)

        cache_key = None
        if self._cache:
            cache_key = self._cache_key(
                "aggregate",
                {
                    "group_by": group_by,
                    "start_time": start_time,
                    "end_time": end_time,
                    "model": model,
                    "session_id": session_id,
                },
            )
            cached = self._cache_get(cache_key)
            if cached:
                return [UsageAggregate(**item) for item in cached["items"]]

        query = select(
            group_expr.label("group_value"),
            func.coalesce(func.sum(UsageRecordModel.tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(UsageRecordModel.cost), 0.0).label("total_cost"),
            func.count(UsageRecordModel.id).label("call_count"),
        )
        if start_time:
            query = query.where(UsageRecordModel.timestamp >= start_time)
        if end_time:
            query = query.where(UsageRecordModel.timestamp <= end_time)
        if model:
            query = query.where(UsageRecordModel.model == model)
        if session_id:
            query = query.where(UsageRecordModel.session_id == session_id)
        query = query.group_by(group_expr).order_by(group_expr)

        session = self._SessionLocal()
        try:
            rows = session.execute(query).all()
        finally:
            session.close()

        aggregates = [
            UsageAggregate(
                group_by=group_by,
                group_value=str(row.group_value),
                total_tokens=int(row.total_tokens or 0),
                total_cost=float(row.total_cost or 0.0),
                call_count=int(row.call_count or 0),
            )
            for row in rows
        ]

        if cache_key:
            self._cache_set(cache_key, {"items": [item.model_dump() for item in aggregates]})
        return aggregates

    def _group_expression(self, group_by: str):
        if group_by == "model":
            return UsageRecordModel.model
        if group_by == "session":
            return func.coalesce(UsageRecordModel.session_id, "unknown")
        if group_by == "hour":
            return func.strftime("%Y-%m-%d %H:00:00", UsageRecordModel.timestamp)
        if group_by == "day":
            return func.strftime("%Y-%m-%d", UsageRecordModel.timestamp)
        if group_by == "week":
            return func.strftime("%Y-%W", UsageRecordModel.timestamp)
        if group_by == "month":
            return func.strftime("%Y-%m", UsageRecordModel.timestamp)
        raise ValueError(f"Unsupported group_by: {group_by}")

    def dispose(self) -> None:
        """Dispose of the database engine and cache."""
        if self._cache:
            try:
                self._cache.close()
            except Exception:
                pass
        self._engine.dispose()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.dispose()
        return False
