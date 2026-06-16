"""
Smoke tests for model config API endpoints.
"""

import importlib

import pytest
from fastapi.testclient import TestClient

from database import init_db, reset_engine


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "model_config_api.db"
    reset_engine(f"sqlite:///{db_path}")
    init_db()

    import main

    importlib.reload(main)

    with TestClient(main.app) as test_client:
        yield test_client


def _payload(name: str):
    return {
        "name": name,
        "description": "Test config",
        "provider": "mock",
        "model": "mock",
        "temperature": 0.7,
        "max_tokens": 64,
        "top_p": 0.8,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "api_key": "test-key",
        "base_url": "https://api.test",
        "extra_params": {"seed": 123},
    }


def test_crud_flow(client):
    response = client.post("/api/model-configs/", json=_payload("Config A"))
    assert response.status_code == 201
    created = response.json()

    config_id = created["id"]
    assert created["name"] == "Config A"

    response = client.get(f"/api/model-configs/{config_id}")
    assert response.status_code == 200
    assert response.json()["id"] == config_id

    response = client.put(
        f"/api/model-configs/{config_id}",
        json={"name": "Config B", "version": created["version"]},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Config B"

    response = client.get("/api/model-configs/")
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.delete(f"/api/model-configs/{config_id}")
    assert response.status_code == 200


def test_duplicate_name_conflict(client):
    response = client.post("/api/model-configs/", json=_payload("Config A"))
    assert response.status_code == 201

    response = client.post("/api/model-configs/", json=_payload("Config A"))
    assert response.status_code == 409


def test_version_conflict(client):
    response = client.post("/api/model-configs/", json=_payload("Config A"))
    created = response.json()

    response = client.put(
        f"/api/model-configs/{created['id']}",
        json={"name": "Config B", "version": created["version"]},
    )
    assert response.status_code == 200

    response = client.put(
        f"/api/model-configs/{created['id']}",
        json={"name": "Config C", "version": created["version"]},
    )
    assert response.status_code == 409


def test_test_endpoint(client):
    response = client.post("/api/model-configs/", json=_payload("Config A"))
    config_id = response.json()["id"]

    response = client.post(f"/api/model-configs/{config_id}/test", json={"prompt": "ping"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_import_export_roundtrip(client):
    response = client.post("/api/model-configs/", json=_payload("Config A"))
    assert response.status_code == 201

    export_response = client.get("/api/model-configs/export")
    assert export_response.status_code == 200
    payload = export_response.json()

    response = client.get("/api/model-configs/")
    config_id = response.json()[0]["id"]
    client.delete(f"/api/model-configs/{config_id}")

    import_response = client.post("/api/model-configs/import", json=payload)
    assert import_response.status_code == 200
    assert import_response.json()["created"] == 1

    response = client.get("/api/model-configs/")
    assert response.status_code == 200
    assert len(response.json()) == 1

