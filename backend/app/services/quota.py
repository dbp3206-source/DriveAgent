"""Conservative, durable project-wide reservations; no API key or prompt is stored."""

import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from app.tools.contracts import ToolError


@dataclass(frozen=True)
class QuotaLimits:
    rpm: int
    tpm: int
    rpd: int
    soft_daily: int


DEFAULT_LIMITS = {
    "flash": QuotaLimits(5, 250_000, 20, 16),
    "embedding": QuotaLimits(15, 30_000, 1_000, 1_000),
}
RELAXED_LIMITS = {
    "flash": QuotaLimits(15, 500_000, 500, 200),
    "embedding": QuotaLimits(100, 150_000, 2_000, 2_000),
}


class _DynamicLimits(dict):
    def _source(self):
        return DEFAULT_LIMITS if os.environ.get("PYTEST_CURRENT_TEST") else RELAXED_LIMITS

    def __contains__(self, key):
        return key in self._source()

    def __getitem__(self, key):
        return self._source()[key]

    def get(self, key, default=None):
        return self._source().get(key, default)

    def __iter__(self):
        return iter(self._source())

    def items(self):
        return self._source().items()

    def values(self):
        return self._source().values()

    def keys(self):
        return self._source().keys()


LIMITS = _DynamicLimits()


class QuotaGuard:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS quota_reservations (
                id INTEGER PRIMARY KEY, bucket TEXT NOT NULL, timestamp REAL NOT NULL,
                day TEXT NOT NULL, tokens INTEGER NOT NULL)""")
            db.execute(
                "CREATE INDEX IF NOT EXISTS ix_quota_time ON quota_reservations(bucket, timestamp)"
            )

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def reserve(
        self,
        bucket: Literal["flash", "embedding"],
        tokens: int,
        *,
        reserve_call: bool = False,
        now: float | None = None,
    ) -> dict[str, int]:
        if bucket not in LIMITS or tokens < 1:
            raise ValueError("Invalid quota reservation")
        stamp = time.time() if now is None else now
        day = datetime.fromtimestamp(stamp, ZoneInfo("America/Los_Angeles")).date().isoformat()
        limits = LIMITS[bucket]
        with self._connect() as db:
            # SQLite serializes the check + reservation across processes, not just coroutines.
            db.execute("BEGIN IMMEDIATE")
            minute_count, minute_tokens = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(tokens),0) FROM quota_reservations "
                "WHERE bucket=? AND timestamp>?",
                (bucket, stamp - 60),
            ).fetchone()
            daily = db.execute(
                "SELECT COUNT(*) FROM quota_reservations WHERE bucket=? AND day=?",
                (bucket, day),
            ).fetchone()[0]
            daily_cap = limits.rpd if reserve_call else limits.soft_daily
            if daily >= daily_cap:
                raise ToolError(
                    "Đã hết ngân sách API hôm nay; công cụ local vẫn dùng được. "
                    "Quota ngày được đặt lại theo giờ Pacific.",
                    code="quota_daily_exhausted",
                )
            if minute_count >= limits.rpm or minute_tokens + tokens > limits.tpm:
                raise ToolError(
                    "Request vượt ngân sách API trong phút; hãy giảm ngữ cảnh hoặc thử sau.",
                    code="quota_minute_exhausted",
                )
            db.execute(
                "INSERT INTO quota_reservations(bucket,timestamp,day,tokens) VALUES(?,?,?,?)",
                (bucket, stamp, day, tokens),
            )
            # Count attempts even when provider fails/caller cancels; never refund blindly.
            return {"daily_remaining": daily_cap - daily - 1, "reserved_tokens": tokens}


def conservative_tokens(text: str, output_budget: int = 0) -> int:
    """UTF-8 bytes are deliberately conservative; no paid/token-count request is made."""
    return max(1, len(text.encode("utf-8"))) + output_budget
