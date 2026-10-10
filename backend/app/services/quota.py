"""Conservative, durable reservations; no API key or prompt is stored."""

import asyncio
import hashlib
import os
import sqlite3
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from typing import Any, Literal
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


LIMITS = DEFAULT_LIMITS

_request_deadline: ContextVar[float | None] = ContextVar("quota_request_deadline", default=None)
_reservation_cancelled: ContextVar[Event | None] = ContextVar(
    "quota_reservation_cancelled", default=None,
)


@contextmanager
def request_quota_deadline(timeout_seconds: float):
    """Share the existing request deadline without extending it on nested calls."""
    deadline = time.monotonic() + timeout_seconds
    existing = _request_deadline.get()
    token = _request_deadline.set(min(existing, deadline) if existing is not None else deadline)
    try:
        yield
    finally:
        _request_deadline.reset(token)


def check_reservation_active() -> None:
    """An in-flight atomic DB check must not reserve after its waiter is cancelled."""
    cancelled = _reservation_cancelled.get()
    if cancelled is not None and cancelled.is_set():
        raise asyncio.CancelledError
    deadline = _request_deadline.get()
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("Request deadline elapsed before quota admission")


async def reserve_generation_quota(
    guard: Any,
    tokens: int,
    *,
    reserve_call: bool = False,
    max_wait_seconds: float = 15.0,
    generation_runway_seconds: float = 20.0,
) -> dict[str, int]:
    """Admit one real generation attempt, with a short cancellable minute wait.

    Only rolling-minute exhaustion can recover by waiting. Daily exhaustion,
    invalid/context-sized requests and all other errors are returned immediately.
    The atomic reservation remains durable; cancellation never refunds a call.
    Polling sleeps live in the coroutine, not an abandoned worker thread.
    """
    if tokens < 1:
        raise ValueError("Invalid quota reservation")
    if tokens > quota_limits()["flash"].tpm:
        raise ToolError(
            "Request vượt ngân sách API trong phút; hãy giảm ngữ cảnh hoặc thử sau.",
            code="quota_minute_exhausted",
        )
    started = time.monotonic()
    wait_budget = min(15.0, max(0.0, max_wait_seconds))
    request_deadline = _request_deadline.get()
    if request_deadline is not None:
        wait_budget = min(
            wait_budget,
            max(0.0, request_deadline - started - max(0.0, generation_runway_seconds)),
        )
    wait_deadline = started + wait_budget
    cancelled = Event()
    token = _reservation_cancelled.set(cancelled)
    try:
        while True:
            check_reservation_active()
            try:
                kwargs = {"reserve_call": True} if reserve_call else {}
                return await asyncio.to_thread(guard.reserve, "flash", tokens, **kwargs)
            except ToolError as exc:
                remaining = wait_deadline - time.monotonic()
                if exc.code != "quota_minute_exhausted" or remaining <= 0:
                    raise
                await asyncio.sleep(min(1.0, remaining))
    finally:
        cancelled.set()
        _reservation_cancelled.reset(token)


def quota_limits() -> dict[str, QuotaLimits]:
    """Return one explicit quota profile for both tests and production.

    Earlier code silently changed semantics when pytest happened to set
    ``PYTEST_CURRENT_TEST``.  That made a green test suite exercise a different
    product from the local runner.  A relaxed profile is still available for a
    deliberately configured development machine, but it must be selected through
    an explicit application setting/environment variable.
    """

    profile = os.environ.get("DRIVE_AGENT_QUOTA_PROFILE", "conservative").strip().lower()
    if profile == "relaxed":
        return RELAXED_LIMITS
    return DEFAULT_LIMITS


class QuotaGuard:
    def __init__(self, path: Path, *, credential: str | None = None):
        self.path = path
        self.namespace = quota_namespace(credential)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS quota_reservations (
                id INTEGER PRIMARY KEY, bucket TEXT NOT NULL, timestamp REAL NOT NULL,
                day TEXT NOT NULL, tokens INTEGER NOT NULL,
                namespace TEXT NOT NULL DEFAULT 'legacy')""")
            columns = {
                row[1] for row in db.execute("PRAGMA table_info(quota_reservations)").fetchall()
            }
            if "namespace" not in columns:
                db.execute(
                    "ALTER TABLE quota_reservations "
                    "ADD COLUMN namespace TEXT NOT NULL DEFAULT 'legacy'"
                )
            db.execute(
                "CREATE INDEX IF NOT EXISTS ix_quota_scope_time "
                "ON quota_reservations(namespace, bucket, timestamp)"
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
        limits_by_bucket = quota_limits()
        if bucket not in limits_by_bucket or tokens < 1:
            raise ValueError("Invalid quota reservation")
        check_reservation_active()
        stamp = time.time() if now is None else now
        day = datetime.fromtimestamp(stamp, ZoneInfo("America/Los_Angeles")).date().isoformat()
        limits = limits_by_bucket[bucket]
        with self._connect() as db:
            # SQLite serializes the check + reservation across processes, not just coroutines.
            db.execute("BEGIN IMMEDIATE")
            minute_count, minute_tokens = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(tokens),0) FROM quota_reservations "
                "WHERE namespace=? AND bucket=? AND timestamp>?",
                (self.namespace, bucket, stamp - 60),
            ).fetchone()
            daily = db.execute(
                "SELECT COUNT(*) FROM quota_reservations "
                "WHERE namespace=? AND bucket=? AND day=?",
                (self.namespace, bucket, day),
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
            check_reservation_active()
            db.execute(
                "INSERT INTO quota_reservations"
                "(bucket,timestamp,day,tokens,namespace) VALUES(?,?,?,?,?)",
                (bucket, stamp, day, tokens, self.namespace),
            )
            # Count attempts even when provider fails/caller cancels; never refund blindly.
            return {"daily_remaining": daily_cap - daily - 1, "reserved_tokens": tokens}

    def reserve_with_wait(
        self,
        bucket: Literal["flash", "embedding"],
        tokens: int,
        *,
        max_wait_seconds: float,
        reserve_call: bool = False,
    ) -> dict[str, int]:
        """Wait for a rolling-minute slot without weakening daily or TPM limits.

        Large document ingestion may need two embedding batches. Failing the
        second batch wastes the successful first provider call and makes a
        perfectly supported PDF impossible to index. This bounded waiter runs
        inside the embedding worker thread; daily exhaustion and every other
        policy error still fail immediately.
        """

        deadline = time.monotonic() + max_wait_seconds
        while True:
            try:
                return self.reserve(bucket, tokens, reserve_call=reserve_call)
            except ToolError as exc:
                remaining = deadline - time.monotonic()
                if exc.code != "quota_minute_exhausted" or remaining <= 0:
                    raise
                time.sleep(min(1.0, remaining))

    def daily_count(
        self,
        bucket: Literal["flash", "embedding"],
        *,
        now: float | None = None,
    ) -> int:
        """Return usage for this credential namespace without exposing the credential."""

        stamp = time.time() if now is None else now
        day = datetime.fromtimestamp(stamp, ZoneInfo("America/Los_Angeles")).date().isoformat()
        with self._connect() as db:
            return int(
                db.execute(
                    "SELECT COUNT(*) FROM quota_reservations "
                    "WHERE namespace=? AND bucket=? AND day=?",
                    (self.namespace, bucket, day),
                ).fetchone()[0]
            )

    def snapshot(
        self,
        bucket: Literal["flash", "embedding"],
        *,
        now: float | None = None,
    ) -> dict[str, int | str]:
        """Return the exact local ledger and conservative configured limits.

        This deliberately does not claim to be Google's remaining quota. Google
        publishes project limits but does not expose a remaining-balance counter
        for this API path.
        """

        stamp = time.time() if now is None else now
        pacific = ZoneInfo("America/Los_Angeles")
        local_now = datetime.fromtimestamp(stamp, pacific)
        day = local_now.date().isoformat()
        limits = quota_limits()[bucket]
        next_reset = datetime.combine(
            local_now.date() + timedelta(days=1),
            datetime.min.time(),
            tzinfo=pacific,
        ).astimezone(UTC)
        with self._connect() as db:
            minute_count, minute_tokens = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(tokens),0) FROM quota_reservations "
                "WHERE namespace=? AND bucket=? AND timestamp>?",
                (self.namespace, bucket, stamp - 60),
            ).fetchone()
            daily = db.execute(
                "SELECT COUNT(*) FROM quota_reservations "
                "WHERE namespace=? AND bucket=? AND day=?",
                (self.namespace, bucket, day),
            ).fetchone()[0]
        return {
            "bucket": bucket,
            "minute_used": int(minute_count),
            "minute_limit": limits.rpm,
            "minute_tokens_used": int(minute_tokens),
            "minute_tokens_limit": limits.tpm,
            "daily_used": int(daily),
            "daily_limit": limits.soft_daily,
            "daily_remaining": max(0, limits.soft_daily - int(daily)),
            "resets_at": next_reset.isoformat(),
            "scope": "veridra_local_safety_budget",
        }


def quota_namespace(credential: str | None) -> str:
    """Create a stable, non-secret quota scope for a provider credential."""

    normalized = (credential or "").strip()
    if not normalized:
        return "legacy"
    return f"key-{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]}"


def conservative_tokens(text: str, output_budget: int = 0) -> int:
    """UTF-8 bytes are deliberately conservative; no paid/token-count request is made."""
    return max(1, len(text.encode("utf-8"))) + output_budget
