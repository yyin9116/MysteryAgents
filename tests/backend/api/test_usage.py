"""
Smoke tests for usage stats API endpoints.
"""

from datetime import datetime, timedelta
import importlib

import pytest
from fastapi.testclient import TestClient

from services.usage_store import UsageStore


@pytest.fixture()
def client_and_store(tmp_path):
    db_path = tmp_path / "usage_api.db"
    store = UsageStore(database_url=f"sqlite:///{db_path}", cache_enabled=False)

    import main

    importlib.reload(main)
    from api import usage as usage_api

    main.app.dependency_overrides[usage_api.get_usage_store] = lambda: store

    with TestClient(main.app) as test_client:
        yield test_client, store

    main.app.dependency_overrides.clear()
    store.dispose()


def _seed_usage(store: UsageStore) -> datetime:
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    store.record_usage(
        model="openai/gpt-4",
        tokens=100,
        cost=0.02,
        session_id="session-1",
        timestamp=base_time,
    )
    store.record_usage(
        model="anthropic/claude-3-opus",
        tokens=200,
        cost=0.05,
        session_id="session-2",
        timestamp=base_time + timedelta(hours=1),
    )
    store.record_usage(
        model="openai/gpt-4",
        tokens=50,
        cost=0.01,
        session_id="session-3",
        timestamp=base_time + timedelta(days=1),
    )
    return base_time


def test_usage_stats_summary_and_grouping(client_and_store):
    client, store = client_and_store
    _seed_usage(store)

    response = client.get("/api/usage/stats?group_by=day")
    assert response.status_code == 200

    data = response.json()
    assert data["group_by"] == "day"
    assert data["summary"]["total_tokens"] == 350
    assert data["summary"]["call_count"] == 3
    assert data["summary"]["total_cost"] == pytest.approx(0.08)

    by_model = {item["group_value"]: item for item in data["by_model"]}
    assert by_model["openai/gpt-4"]["total_tokens"] == 150
    assert by_model["anthropic/claude-3-opus"]["total_tokens"] == 200

    by_time = {item["group_value"]: item for item in data["by_time"]}
    assert by_time["2024-01-01"]["call_count"] == 2
    assert by_time["2024-01-02"]["call_count"] == 1


def test_usage_stats_filters_and_empty(client_and_store):
    client, store = client_and_store
    base_time = _seed_usage(store)

    response = client.get(
        "/api/usage/stats?model=openai/gpt-4"
        f"&start_date={base_time.isoformat()}&end_date={base_time.isoformat()}"
    )
    assert response.status_code == 200

    data = response.json()
    by_model = {item["group_value"]: item for item in data["by_model"]}
    assert list(by_model.keys()) == ["openai/gpt-4"]
    assert data["summary"]["total_tokens"] == 100

    response = client.get("/api/usage/stats?model=openai/gpt-4&start_date=2099-01-01")
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_tokens"] == 0
    assert data["by_model"] == []
    assert data["by_time"] == []


def test_usage_stats_validation(client_and_store):
    client, _store = client_and_store

    response = client.get("/api/usage/stats?group_by=year")
    assert response.status_code == 400

    response = client.get("/api/usage/stats?start_date=2024-01-02&end_date=2024-01-01")
    assert response.status_code == 400

    response = client.get("/api/usage/stats?model=unknown/model")
    assert response.status_code == 400
