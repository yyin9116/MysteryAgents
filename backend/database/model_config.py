"""
SQLAlchemy model for stored LLM model configurations.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text

from database.base import Base


class ModelConfigORM(Base):
    """Database model for LLM configuration settings."""

    __tablename__ = "model_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    temperature = Column(Float, nullable=False, default=0.7)
    max_tokens = Column(Integer, nullable=True)
    top_p = Column(Float, nullable=True)
    frequency_penalty = Column(Float, nullable=True)
    presence_penalty = Column(Float, nullable=True)
    api_key = Column(String(255), nullable=True)
    base_url = Column(String(255), nullable=True)
    extra_params = Column(JSON, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

