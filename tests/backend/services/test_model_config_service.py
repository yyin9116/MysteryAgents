"""
Tests for ModelConfigService CRUD operations.
"""

import pytest

from database import init_db, reset_engine
from database import session as db_session_module
from services.model_config_service import ModelConfigConflictError, ModelConfigService
from database.model_config import ModelConfigORM
from models.model_config import (
    ModelConfigCreate,
    ModelConfigImport,
    ModelConfigImportItem,
    ModelConfigUpdate,
)


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "model_config_service.db"
    reset_engine(f"sqlite:///{db_path}")
    init_db()
    session = db_session_module.SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _sample_config(name: str) -> ModelConfigCreate:
    return ModelConfigCreate(
        name=name,
        description="Test config",
        provider="openai",
        model="gpt-4o-mini",
        temperature=0.5,
        max_tokens=256,
        top_p=0.9,
        frequency_penalty=0.1,
        presence_penalty=0.2,
        api_key="test-key",
        base_url="https://api.test",
        extra_params={"seed": 42},
    )


def test_create_and_get_config(db_session):
    service = ModelConfigService(db_session)
    created = service.create_config(_sample_config("Config A"))

    assert created.id
    assert created.name == "Config A"

    fetched = service.get_config(created.id)
    assert fetched.id == created.id
    assert fetched.provider == "openai"


def test_duplicate_name_conflict(db_session):
    service = ModelConfigService(db_session)
    service.create_config(_sample_config("Config A"))

    with pytest.raises(ModelConfigConflictError):
        service.create_config(_sample_config("Config A"))


def test_update_with_version_conflict(db_session):
    service = ModelConfigService(db_session)
    created = service.create_config(_sample_config("Config A"))

    update = ModelConfigUpdate(name="Config B", version=created.version)
    updated = service.update_config(created.id, update)

    assert updated.name == "Config B"
    assert updated.version == created.version + 1

    stale_update = ModelConfigUpdate(name="Config C", version=created.version)
    with pytest.raises(ModelConfigConflictError):
        service.update_config(created.id, stale_update)


def test_export_import_roundtrip(db_session):
    service = ModelConfigService(db_session)
    service.create_config(_sample_config("Config A"))

    exported = service.export_configs()

    db_session.query(ModelConfigORM).delete()
    db_session.commit()

    payload = ModelConfigImport(
        version=exported.version,
        configs=[ModelConfigImportItem(**config.dict()) for config in exported.configs],
        overwrite=False,
    )

    result = service.import_configs(payload)
    assert result["created"] == 1
    assert result["skipped"] == 0
    assert len(service.list_configs()) == 1
