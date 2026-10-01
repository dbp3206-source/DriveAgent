from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.quota import QuotaGuard
from app.tools.contracts import ToolError


def test_rpm_persists_across_guard_instances(tmp_path):
    path = tmp_path / "quota.db"
    for _ in range(5):
        QuotaGuard(path).reserve("flash", 100, now=1000)
    with pytest.raises(ToolError, match="phút"):
        QuotaGuard(path).reserve("flash", 100, now=1001)
    QuotaGuard(path).reserve("flash", 100, now=1061)


def test_soft_limit_reserve_hard_cap_and_daily_reset(tmp_path):
    guard = QuotaGuard(tmp_path / "quota.db")
    for i in range(16):
        guard.reserve("flash", 1, now=1000 + i * 61)
    with pytest.raises(ToolError) as error:
        guard.reserve("flash", 1, now=3000)
    assert error.value.code == "quota_daily_exhausted"
    for i in range(4):
        guard.reserve("flash", 1, now=4000 + i * 61, reserve_call=True)
    with pytest.raises(ToolError):
        guard.reserve("flash", 1, now=5000, reserve_call=True)
    guard.reserve("flash", 1, now=1000 + 86400)


def test_embedding_tpm_is_reserved_before_request(tmp_path):
    guard = QuotaGuard(tmp_path / "quota.db")
    guard.reserve("embedding", 29999, now=1000)
    with pytest.raises(ToolError):
        guard.reserve("embedding", 2, now=1001)
    guard.reserve("embedding", 2, now=1061)


def test_embedding_waiter_retries_only_the_rolling_minute_limit(tmp_path, monkeypatch):
    guard = QuotaGuard(tmp_path / "quota.db")
    guard.reserve("embedding", 29_999, now=1_000)
    clock = {"value": 1_001.0}

    monkeypatch.setattr("app.services.quota.time.time", lambda: clock["value"])
    monkeypatch.setattr("app.services.quota.time.monotonic", lambda: clock["value"])
    monkeypatch.setattr(
        "app.services.quota.time.sleep",
        lambda seconds: clock.__setitem__("value", clock["value"] + seconds),
    )

    reserved = guard.reserve_with_wait("embedding", 2, max_wait_seconds=61)

    assert reserved["reserved_tokens"] == 2
    assert clock["value"] >= 1_060


def test_parallel_reservations_cannot_overrun_rpm(tmp_path):
    guard = QuotaGuard(tmp_path / "quota.db")

    def attempt(_):
        try:
            guard.reserve("flash", 10, now=1000)
            return True
        except ToolError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(12))) == 5


def test_rotated_credentials_have_independent_daily_budgets(tmp_path):
    path = tmp_path / "quota.db"
    first = QuotaGuard(path, credential="provider-key-one")
    second = QuotaGuard(path, credential="provider-key-two")
    for i in range(16):
        first.reserve("flash", 1, now=1000 + i * 61)

    assert first.daily_count("flash", now=2000) == 16
    assert second.daily_count("flash", now=2000) == 0
    second.reserve("flash", 1, now=2000)
    assert second.daily_count("flash", now=2000) == 1
