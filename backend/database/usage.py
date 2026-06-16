"""SQLAlchemy models for usage tracking."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Index, Integer, String

from .base import Base


class UsageRecord(Base):
    """Usage record for a single LLM call."""

    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True, default=datetime.utcnow)
    model = Column(String(128), nullable=False, index=True)
    tokens = Column(Integer, nullable=False)
    cost = Column(Float, nullable=False)
    session_id = Column(String(128), nullable=True, index=True)

    __table_args__ = (
        Index("ix_usage_records_model_timestamp", "model", "timestamp"),
    )
