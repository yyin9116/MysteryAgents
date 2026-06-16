"""Database engine and session utilities."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from config.settings import settings


def create_db_engine(database_url: Optional[str] = None):
    """Create a SQLAlchemy engine with SQLite-friendly defaults."""
    url = database_url or settings.USAGE_DATABASE_URL or settings.DATABASE_URL
    connect_args = {}
    pool_class = QueuePool
    pool_kwargs = {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
    }

    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if ":memory:" in url:
            pool_class = StaticPool
            pool_kwargs = {}

    return create_engine(
        url,
        connect_args=connect_args,
        poolclass=pool_class,
        pool_pre_ping=True,
        future=True,
        **pool_kwargs,
    )


def create_session_factory(engine):
    """Create a session factory bound to the provided engine."""
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, autocommit=False)
