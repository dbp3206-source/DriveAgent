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
