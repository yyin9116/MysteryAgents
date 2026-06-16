"""
Database module exports.
"""

from database.base import Base
from database.model_config import ModelConfigORM
from database.session import get_db, init_engine, reset_engine


def init_db():
    """Create database tables."""
    from database import model_config  # noqa: F401 - ensure model import
    from database.session import engine as session_engine

    Base.metadata.create_all(bind=session_engine)


__all__ = [
    "Base",
    "ModelConfigORM",
    "get_db",
    "init_engine",
    "reset_engine",
    "init_db",
]
