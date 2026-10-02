import asyncio
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api import system
from app.core.config import Settings


async def test_readiness_refreshes_storage_failure_and_recovery(monkeypatch):
    settings = Settings(_env_file=None)
    monkeypatch.setattr(system, "get_settings", lambda: settings)
    probe = AsyncMock(side_effect=[False, True])
    monkeypatch.setattr(system, "probe_object_storage", probe)
    times = iter([100.0, 110.0, 131.0])
    monkeypatch.setattr(system, "monotonic", lambda: next(times))
    state = SimpleNamespace(
        vector_store=SimpleNamespace(backend_name="qdrant-embedded"),
        object_storage_healthy=True,
    )
    request = SimpleNamespace(app=SimpleNamespace(state=state))
    db = SimpleNamespace(execute=AsyncMock())
    first = await system.health(request, db)
    assert first.status == "degraded" and not first.object_storage
    cached = await system.health(request, db)
    assert cached.status == "degraded" and probe.await_count == 1
    recovered = await system.health(request, db)
    assert recovered.status == "ok" and recovered.object_storage
    assert probe.await_count == 2


@pytest.mark.parametrize("failure", [TimeoutError(), RuntimeError("unavailable")])
async def test_readiness_probe_failure_does_not_fail_endpoint(monkeypatch, failure):
    monkeypatch.setattr(system, "get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(system, "probe_object_storage", AsyncMock(side_effect=failure))
    state = SimpleNamespace(vector_store=SimpleNamespace(backend_name="qdrant-embedded"))
    result = await system.health(
        SimpleNamespace(app=SimpleNamespace(state=state)),
        SimpleNamespace(execute=AsyncMock()),
    )
    assert result.status == "degraded"
    assert result.database and not result.object_storage


async def test_readiness_bounds_stalled_database_query(monkeypatch):
    monkeypatch.setattr(system, "get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(system, "probe_object_storage", AsyncMock(return_value=True))
    cancelled = asyncio.Event()

    async def stalled_query(_statement):
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.set()

    state = SimpleNamespace(vector_store=SimpleNamespace(backend_name="qdrant-embedded"))
    started = perf_counter()
    result = await system.health(
        SimpleNamespace(app=SimpleNamespace(state=state)),
        SimpleNamespace(execute=stalled_query),
    )
    assert 4.9 <= perf_counter() - started < 10
    assert cancelled.is_set()
    assert result.status == "degraded"
    assert not result.database and result.object_storage
