"""Smoke tests for usage store operations."""

from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.pool import QueuePool

from services.usage_store import UsageStore


def _make_store(tmp_path):
    db_path = tmp_path / "usage.db"
    return UsageStore(database_url=f"sqlite:///{db_path}", cache_enabled=False)


def test_record_and_list_usage(tmp_path):
    store = _make_store(tmp_path)
    record = store.record_usage(
        model="openai/gpt-4",
        tokens=120,
        cost=0.03,
        session_id="session-1",
    )

    assert record.id is not None
    records = store.list_usage()
    assert len(records) == 1
    assert records[0].model == "openai/gpt-4"
    assert records[0].tokens == 120
    assert records[0].cost == 0.03
    assert records[0].session_id == "session-1"
    store.dispose()


def test_usage_aggregation(tmp_path):
    store = _make_store(tmp_path)
    base_time = datetime(2024, 1, 1, 12, 0, 0)

    store.record_usage(
        model="openai/gpt-4",
        tokens=100,
        cost=0.02,
        session_id="session-1",
        timestamp=base_time,
    )
    store.record_usage(
        model="openai/gpt-4",
        tokens=50,
        cost=0.01,
        session_id="session-1",
        timestamp=base_time + timedelta(hours=1),
    )
    store.record_usage(
        model="anthropic/claude",
        tokens=200,
        cost=0.05,
        session_id="session-2",
        timestamp=base_time,
    )

    summary = store.get_usage_summary()
    assert summary.total_tokens == 350
    assert summary.call_count == 3

    by_model = {item.group_value: item for item in store.get_usage_aggregates("model")}
    assert by_model["openai/gpt-4"].total_tokens == 150
    assert by_model["anthropic/claude"].total_tokens == 200

    by_session = {item.group_value: item for item in store.get_usage_aggregates("session")}
    assert by_session["session-1"].call_count == 2
    assert by_session["session-2"].call_count == 1

    by_day = store.get_usage_aggregates("day")
    assert len(by_day) == 1
    assert by_day[0].group_value == "2024-01-01"
    store.dispose()


def test_concurrent_writes(tmp_path):
    store = _make_store(tmp_path)

    def worker(idx: int) -> None:
        store.record_usage(
            model="openai/gpt-4",
            tokens=10 + idx,
            cost=0.001,
            session_id=f"session-{idx % 3}",
        )

    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(worker, range(10))

    summary = store.get_usage_summary()
    assert summary.call_count == 10
    store.dispose()


def test_engine_pool_and_cleanup(tmp_path):
    store = _make_store(tmp_path)
    assert isinstance(store.engine.pool, QueuePool)
    store.dispose()
