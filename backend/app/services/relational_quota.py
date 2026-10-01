"""Durable conservative reservations, shared across workers on PostgreSQL."""

import hashlib
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    delete,
    func,
    insert,
    select,
    text,
)
from sqlalchemy.engine import Engine

from app.core.config import Settings
from app.services.quota import QuotaGuard, quota_limits, quota_namespace
from app.services.relational_state import state_engine, state_transaction
from app.tools.contracts import ToolError

metadata = MetaData()
reservations = Table(
    "quota_reservations", metadata,
    Column("id", String(36), primary_key=True),
    Column("namespace", Text, nullable=False, index=True),
    Column("bucket", Text, nullable=False),
    Column("timestamp", Float, nullable=False),
    Column("day", String(10), nullable=False),
    Column("tokens", Integer, nullable=False),
)


def quota_guard(settings: Settings, *, credential: str | None = None) -> QuotaGuard:
    if settings.relational_state_url is None:
        return QuotaGuard(settings.data_dir / "quota.db", credential=credential)
    return RelationalQuotaGuard(
        state_engine(settings.relational_state_url.get_secret_value()), credential=credential
    )


def initialize_quota_store(settings: Settings):
    if settings.relational_state_url is not None:
        RelationalQuotaGuard.create_schema(
            state_engine(settings.relational_state_url.get_secret_value())
        )


class RelationalQuotaGuard(QuotaGuard):
    def __init__(self, engine: Engine, *, credential: str | None = None):
        self.engine = engine
        self.namespace = quota_namespace(credential)

    @staticmethod
    def create_schema(engine: Engine):
        metadata.create_all(engine)

    def _usage(self, db, bucket: str, stamp: float, day: str) -> tuple[int, int, int]:
        scope = (reservations.c.namespace == self.namespace, reservations.c.bucket == bucket)
        count, tokens = db.execute(select(
            func.count(), func.coalesce(func.sum(reservations.c.tokens), 0),
        ).where(*scope, reservations.c.timestamp > stamp - 60)).one()
        daily = db.execute(select(func.count()).select_from(reservations).where(
            *scope, reservations.c.day == day,
        )).scalar_one()
        return int(count), int(tokens), int(daily)

    def reserve(self, bucket, tokens: int, *, reserve_call: bool = False,
                now: float | None = None) -> dict[str, int]:
        limits_by_bucket = quota_limits()
        if bucket not in limits_by_bucket or tokens < 1:
            raise ValueError("Invalid quota reservation")
        stamp = time.time() if now is None else now
        day = datetime.fromtimestamp(stamp, ZoneInfo("America/Los_Angeles")).date().isoformat()
        limits = limits_by_bucket[bucket]
        with state_transaction(self.engine) as db:
            if self.engine.dialect.name == "postgresql":
                scope = int.from_bytes(hashlib.sha256(
                    ("quota:" + self.namespace + ":" + bucket).encode()
                ).digest()[:8], "big", signed=True)
                db.execute(text("SELECT pg_advisory_xact_lock(:scope)"), {"scope": scope})
            count, minute_tokens, daily = self._usage(db, bucket, stamp, day)
            cap = limits.rpd if reserve_call else limits.soft_daily
            if daily >= cap:
                raise ToolError(
                    "Đã hết ngân sách API hôm nay; quota ngày đặt lại theo giờ Pacific.",
                    code="quota_daily_exhausted",
                )
            if count >= limits.rpm or minute_tokens + tokens > limits.tpm:
                raise ToolError(
                    "Request vượt ngân sách API trong phút; hãy giảm ngữ cảnh hoặc thử sau.",
                    code="quota_minute_exhausted",
                )
            db.execute(delete(reservations).where(
                reservations.c.namespace == self.namespace,
                reservations.c.timestamp < stamp - 30 * 86400,
            ))
            db.execute(insert(reservations).values(
                id=str(uuid4()), namespace=self.namespace, bucket=bucket,
                timestamp=stamp, day=day, tokens=tokens,
            ))
        return {"daily_remaining": cap - daily - 1, "reserved_tokens": tokens}

    def daily_count(self, bucket, *, now: float | None = None) -> int:
        stamp = time.time() if now is None else now
        day = datetime.fromtimestamp(stamp, ZoneInfo("America/Los_Angeles")).date().isoformat()
        with self.engine.connect() as db:
            return self._usage(db, bucket, stamp, day)[2]

    def snapshot(self, bucket, *, now: float | None = None) -> dict:
        stamp = time.time() if now is None else now
        pacific = ZoneInfo("America/Los_Angeles")
        local_now = datetime.fromtimestamp(stamp, pacific)
        limits = quota_limits()[bucket]
        reset = datetime.combine(local_now.date() + timedelta(days=1),
                                 datetime.min.time(), tzinfo=pacific).astimezone(UTC)
        with self.engine.connect() as db:
            count, tokens, daily = self._usage(db, bucket, stamp, local_now.date().isoformat())
        return {
            "bucket": bucket, "minute_used": count, "minute_limit": limits.rpm,
            "minute_tokens_used": tokens, "minute_tokens_limit": limits.tpm,
            "daily_used": daily, "daily_limit": limits.soft_daily,
            "daily_remaining": max(0, limits.soft_daily - daily),
            "resets_at": reset.isoformat(), "scope": "veridra_safety_budget",
        }
