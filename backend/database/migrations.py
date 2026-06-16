"""Database initialization and migration helpers."""

from __future__ import annotations

from sqlalchemy import Column, Integer, MetaData, Table, select, insert, update

from .base import Base
from . import usage  # noqa: F401 - ensure models are registered

SCHEMA_VERSION = 1


def _schema_table(metadata: MetaData) -> Table:
    return Table(
        "schema_migrations",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("version", Integer, nullable=False),
    )


def get_schema_version(engine) -> int:
    """Fetch the current schema version, creating the version table if needed."""
    metadata = MetaData()
    table = _schema_table(metadata)
    metadata.create_all(engine, tables=[table])

    with engine.begin() as connection:
        result = connection.execute(select(table.c.version).where(table.c.id == 1)).scalar()
    return int(result or 0)


def set_schema_version(engine, version: int) -> None:
    """Persist the schema version."""
    metadata = MetaData()
    table = _schema_table(metadata)
    metadata.create_all(engine, tables=[table])

    with engine.begin() as connection:
        existing = connection.execute(select(table.c.id).where(table.c.id == 1)).scalar()
        if existing is None:
            connection.execute(insert(table).values(id=1, version=version))
        else:
            connection.execute(update(table).where(table.c.id == 1).values(version=version))


def run_migrations(engine) -> int:
    """Apply migrations in sequence and return the resulting schema version."""
    current_version = get_schema_version(engine)
    if current_version < 1:
        Base.metadata.create_all(engine)
        set_schema_version(engine, 1)
    return get_schema_version(engine)


def initialize_database(engine) -> None:
    """Initialize the database schema if needed."""
    run_migrations(engine)
