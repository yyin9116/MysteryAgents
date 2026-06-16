"""
Database session and engine management.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import settings

engine = None
SessionLocal = None


def _build_engine(database_url: str):
    connect_args = {}
    engine_kwargs = {"future": True}

    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if database_url == "sqlite:///:memory:":
            engine_kwargs["poolclass"] = StaticPool

    return create_engine(database_url, connect_args=connect_args, **engine_kwargs)


def init_engine(database_url: Optional[str] = None):
    """Initialize the global engine and session factory."""
    global engine, SessionLocal

    url = database_url or settings.DATABASE_URL
    engine = _build_engine(url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return engine


def reset_engine(database_url: str):
    """Reset the global engine (useful for tests)."""
    return init_engine(database_url)


def get_db():
    """Yield a database session."""
    if SessionLocal is None:
        init_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Initialize engine on import
init_engine()

