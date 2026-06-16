"""Smoke tests for database initialization and migrations."""

from sqlalchemy import inspect

from database.engine import create_db_engine
from database.migrations import get_schema_version, run_migrations


def test_migrations_create_tables(tmp_path):
    db_path = tmp_path / "usage.db"
    engine = create_db_engine(f"sqlite:///{db_path}")

    version = run_migrations(engine)
    assert version == 1
    assert get_schema_version(engine) == 1

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "usage_records" in tables
    assert "schema_migrations" in tables

    version_again = run_migrations(engine)
    assert version_again == 1
    engine.dispose()
