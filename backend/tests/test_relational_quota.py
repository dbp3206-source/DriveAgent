from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine

from app.services.relational_quota import RelationalQuotaGuard
from app.tools.contracts import ToolError


@pytest.fixture
def engine(tmp_path):
    value = create_engine(f"sqlite:///{tmp_path / 'quota.db'}")
    RelationalQuotaGuard.create_schema(value)
    yield value
    value.dispose()


def test_atomic_minute_limit_and_namespace_isolation(engine):
    guard = RelationalQuotaGuard(engine, credential="synthetic-key-one")

    def reserve(_):
        try:
            guard.reserve("flash", 10, now=100)
            return "reserved"
        except ToolError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(reserve, range(12)))
    assert results.count("reserved") == 5
    assert results.count("quota_minute_exhausted") == 7
    assert guard.snapshot("flash", now=100)["daily_used"] == 5
    assert RelationalQuotaGuard(engine, credential="synthetic-key-two").daily_count(
        "flash", now=100
    ) == 0
    assert RelationalQuotaGuard(engine, credential="synthetic-key-one").daily_count(
        "flash", now=100
    ) == 5


def test_daily_budget_switching_does_not_reset_ledger(engine):
    guard = RelationalQuotaGuard(engine, credential="synthetic-key")
    for index in range(16):
        guard.reserve("flash", 10, now=100 + index * 61)
    with pytest.raises(ToolError) as exhausted:
        RelationalQuotaGuard(engine, credential="synthetic-key").reserve("flash", 10, now=1200)
    assert exhausted.value.code == "quota_daily_exhausted"
    snapshot = guard.snapshot("flash", now=1200)
    assert snapshot["daily_remaining"] == 0
    assert snapshot["scope"] == "veridra_safety_budget"
    assert snapshot["resets_at"].endswith("+00:00")
    assert guard.daily_count("flash", now=100 + 86400) == 0


def test_token_budget_and_invalid_reservations(engine):
    guard = RelationalQuotaGuard(engine)
    with pytest.raises(ToolError) as excess:
        guard.reserve("flash", 250001, now=100)
    assert excess.value.code == "quota_minute_exhausted"
    assert guard.daily_count("flash", now=100) == 0
    with pytest.raises(ValueError):
        guard.reserve("unknown", 10)
    with pytest.raises(ValueError):
        guard.reserve("flash", 0)
