"""Durable cleanup progress and fenced leases, with no deletion/provider calls.

Callers must establish either explicit UI approval or the trusted expiry policy,
plus complete inventory and snapshot freshness, before enqueue. This queue cannot
establish those facts. The critical checkpoint commits with content removal.
"""

import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.db.models import CleanupJob
from app.services.retention_policy import (
    APPROVAL_SECONDS,
    CONTENT_RETENTION_DAYS,
    ApprovalSnapshot,
    utc,
)

LEASE_SECONDS = 120
MAX_ATTEMPTS = 3
WORKING = ("running", "purging")
OPEN = ("queued", "running", "purging", "needs_attention")
ERROR_CODES = frozenset({
    "owner_busy", "approval_changed", "storage_unavailable", "vector_unavailable",
    "framework_unavailable", "worker_interrupted", "retry_limit", "checkpoint_invalid",
})


class CleanupStateError(ValueError):
    pass


class CleanupLeaseLost(CleanupStateError):
    pass


class PurgeReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["pdf", "drive_chunks", "agent_memories", "state", "adk_context",
                  "langgraph_context"]
    owner_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9-]+$")
    object_id: str = Field(min_length=1, max_length=200)
    fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    copy_fingerprints: tuple[str, ...] = Field(default=(), max_length=2)

    @model_validator(mode="after")
    def pdf_identity(self):
        if (self.copy_fingerprints and (self.kind != "pdf" or self.fingerprint is None)
                or len(set(self.copy_fingerprints)) != len(self.copy_fingerprints)
                or any(len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
                       for value in self.copy_fingerprints)):
            raise ValueError("invalid_cleanup_pdf_copies")
        if self.kind == "pdf" and (len(self.object_id) > 64 or any(
            not (char.isascii() and (char.isalnum() or char == "-")) for char in self.object_id
        )):
            raise ValueError("invalid_cleanup_pdf_identity")
        return self


class CleanupPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    snapshot: ApprovalSnapshot
    external: tuple[PurgeReference, ...] = Field(default=(), max_length=2000)

    @model_validator(mode="after")
    def fixed_scope(self):
        if self.snapshot.version != 1:
            raise ValueError("invalid_cleanup_version")
        if utc(self.snapshot.cutoff) != utc(self.snapshot.issued_at) - timedelta(
            days=CONTENT_RETENTION_DAYS,
        ):
            raise ValueError("invalid_cleanup_cutoff")
        if any(utc(item.changed_at) > utc(self.snapshot.cutoff) for item in self.snapshot.items):
            raise ValueError("cleanup_content_not_due")
        keys = [(item.kind, item.record_id) for item in self.snapshot.items]
        refs = [(item.kind, item.owner_id, item.object_id) for item in self.external]
        if len(keys) != len(set(keys)) or len(refs) != len(set(refs)):
            raise ValueError("duplicate_cleanup_scope")
        if any(item.owner_id != self.snapshot.owner_id for item in self.external):
            raise ValueError("cleanup_owner_mismatch")
        if len({item.name for item in self.snapshot.bindings}) != len(self.snapshot.bindings):
            raise ValueError("duplicate_cleanup_binding")
        return self


def _serialize(plan: CleanupPlan) -> tuple[str, str]:
    body = json.dumps(plan.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return body, hashlib.sha256(body.encode()).hexdigest()


def _check_time(now: float) -> None:
    if type(now) not in {float, int} or not math.isfinite(now) or now < 0:
        raise CleanupStateError("invalid_cleanup_time")


def _progress(row):
    try:
        plan = CleanupPlan.model_validate_json(row.plan_json)
        if hashlib.sha256(row.plan_json.encode()).hexdigest() != row.plan_hash:
            raise ValueError
        if plan.snapshot.owner_id != row.user_id or plan.snapshot.approval_id != row.approval_id:
            raise ValueError
        pending_data, done_data = json.loads(row.remaining_json), json.loads(row.completed_json)
        if type(pending_data) is not list or type(done_data) is not list:
            raise ValueError
        pending = [PurgeReference.model_validate(item) for item in pending_data]
        done = [PurgeReference.model_validate(item) for item in done_data]
        def key(item):
            return item.kind, item.owner_id, item.object_id

        expected, waiting, completed = set(map(key, plan.external)), set(map(key, pending)), set(
            map(key, done))
        approved_refs = {key(item): item for item in plan.external}
        if (len(waiting) != len(pending) or len(completed) != len(done)
                or waiting & completed or waiting | completed != expected
                or any(item != approved_refs.get(key(item)) for item in (*pending, *done))):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise CleanupStateError("cleanup_checkpoint_invalid") from None
    return plan, pending, done


async def enqueue(factory, owner_id: str, plan: CleanupPlan, *, now: float,
                  automatic: bool = False) -> str:
    """Metadata only; caller must be a trusted UI approval or internal policy runner."""
    _check_time(now)
    if plan.snapshot.owner_id != owner_id:
        raise CleanupStateError("cleanup_owner_mismatch")
    body, digest = _serialize(plan)
    async with factory() as db:
        old = await db.scalar(select(CleanupJob).where(
            CleanupJob.user_id == owner_id, CleanupJob.approval_id == plan.snapshot.approval_id,
        ))
        if old is not None:
            if old.plan_hash != digest:
                raise CleanupStateError("cleanup_approval_conflict")
            return old.id
        if await db.scalar(select(CleanupJob.id).where(
            CleanupJob.user_id == owner_id, CleanupJob.status.in_(OPEN),
        )) is not None:
            raise CleanupStateError("cleanup_already_open")
        issued = utc(plan.snapshot.issued_at).timestamp()
        if not issued <= now < issued + APPROVAL_SECONDS:
            raise CleanupStateError("cleanup_approval_expired")
        job_id = str(uuid4())
        row = CleanupJob(
            id=job_id,
            user_id=owner_id, approval_id=plan.snapshot.approval_id, plan_hash=digest,
            plan_json=body,
            automatic=automatic,
            remaining_json=json.dumps([item.model_dump() for item in plan.external]),
            created_at=datetime.fromtimestamp(now, UTC),
        )
        db.add(row)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            old = await db.scalar(select(CleanupJob).where(
                CleanupJob.user_id == owner_id, CleanupJob.approval_id == plan.snapshot.approval_id,
            ))
            if old is None:
                if await db.scalar(select(CleanupJob.id).where(
                    CleanupJob.user_id == owner_id, CleanupJob.status.in_(OPEN),
                )) is not None:
                    raise CleanupStateError("cleanup_already_open") from None
            if old is None or old.plan_hash != digest:
                raise CleanupStateError("cleanup_approval_conflict") from None
            return old.id
        return job_id


async def claim(factory, *, now: float) -> dict | None:
    _check_time(now)
    async with factory() as db:
        expired = and_(CleanupJob.status.in_(WORKING), CleanupJob.lease_until <= now)
        await db.execute(update(CleanupJob).where(
            expired, CleanupJob.attempts >= MAX_ATTEMPTS,
        ).values(status="needs_attention", lease_token=None, lease_until=None,
                 error_code="retry_limit"))
        eligible = or_(CleanupJob.status == "queued", and_(
            expired, CleanupJob.attempts < MAX_ATTEMPTS,
        ))
        query = select(CleanupJob).where(eligible).order_by(CleanupJob.created_at).limit(1)
        if db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        row = await db.scalar(query)
        if row is None:
            await db.commit()
            return None
        try:
            _progress(row)
        except CleanupStateError:
            # A damaged job must not starve every other owner's cleanup queue.
            await db.execute(update(CleanupJob).where(
                CleanupJob.id == row.id, CleanupJob.attempts == row.attempts, eligible,
            ).values(status="needs_attention", error_code="checkpoint_invalid",
                     lease_token=None, lease_until=None))
            await db.commit()
            return None
        token, attempt = str(uuid4()), row.attempts + 1
        phase = "running" if row.sql_completed_at is None else "purging"
        result = await db.execute(update(CleanupJob).where(
            CleanupJob.id == row.id, CleanupJob.attempts == row.attempts, eligible,
        ).values(status=phase, attempts=attempt, lease_token=token,
                 lease_until=now + LEASE_SECONDS, error_code=None))
        if result.rowcount != 1:
            await db.rollback()
            return None
        claimed = {"id": row.id, "owner": row.user_id, "token": token, "attempt": attempt,
                   "phase": phase, "plan_json": row.plan_json, "remaining_json": row.remaining_json}
        await db.commit()
        return claimed


async def leased_row(db, job_id: str, token: str, attempt: int, *, now: float):
    _check_time(now)
    query = select(CleanupJob).where(
        CleanupJob.id == job_id, CleanupJob.lease_token == token,
        CleanupJob.attempts == attempt, CleanupJob.status.in_(WORKING),
        CleanupJob.lease_until > now,
    ).execution_options(populate_existing=True)
    if db.bind.dialect.name == "postgresql":
        query = query.with_for_update()
    row = await db.scalar(query)
    if row is None:
        raise CleanupLeaseLost("cleanup_lease_lost")
    return row


async def _checkpoint(db, job_id: str, token: str, attempt: int, *, now: float,
                      values: dict, expected_remaining: str | None = None,
                      expected_completed: str | None = None) -> None:
    # SELECT alone is not a write fence on SQLite's legacy transaction mode.
    statement = update(CleanupJob).where(
        CleanupJob.id == job_id, CleanupJob.lease_token == token,
        CleanupJob.attempts == attempt, CleanupJob.status.in_(WORKING),
        CleanupJob.lease_until > now,
    )
    if expected_remaining is not None:
        statement = statement.where(CleanupJob.remaining_json == expected_remaining)
    if expected_completed is not None:
        statement = statement.where(CleanupJob.completed_json == expected_completed)
    result = await db.execute(statement.values(**values).execution_options(
        synchronize_session=False,
    ))
    if result.rowcount != 1:
        raise CleanupLeaseLost("cleanup_lease_lost")


async def mark_started(db, job_id: str, token: str, attempt: int, *, now: float) -> None:
    row = await leased_row(db, job_id, token, attempt, now=now)
    _progress(row)
    await _checkpoint(db, job_id, token, attempt, now=now, values={
        "critical_started_at": row.critical_started_at or datetime.fromtimestamp(now, UTC),
    })


async def mark_sql_done(db, job_id: str, token: str, attempt: int, *, now: float) -> None:
    """Caller commits this in the SAME transaction as the critical SQL purge."""
    row = await leased_row(db, job_id, token, attempt, now=now)
    _plan, remaining, _done = _progress(row)
    if any(item.kind in {"state", "adk_context", "langgraph_context"} for item in remaining):
        raise CleanupStateError("cleanup_critical_steps_pending")
    await _checkpoint(db, job_id, token, attempt, now=now, values={
        "sql_completed_at": row.sql_completed_at or datetime.fromtimestamp(now, UTC),
        "critical_started_at": row.critical_started_at or datetime.fromtimestamp(now, UTC),
        "status": "purging", "lease_until": now + LEASE_SECONDS,
    })


async def renew(db, job_id: str, token: str, attempt: int, *, now: float) -> None:
    await leased_row(db, job_id, token, attempt, now=now)
    await _checkpoint(db, job_id, token, attempt, now=now,
                      values={"lease_until": now + LEASE_SECONDS})


async def record_critical_step(db, job_id: str, token: str, attempt: int, ref: PurgeReference,
                               *, now: float) -> None:
    """After the store commit/readback, BEFORE final application SQL checkpoint.

    Only exact pre-approved auxiliary SQL/cache steps, never file/vector receipts.
    A crash between that store commit and this receipt is resumed idempotently.
    """
    row = await leased_row(db, job_id, token, attempt, now=now)
    if (ref.kind not in {"state", "adk_context", "langgraph_context"}
            or ref.owner_id != row.user_id or row.critical_started_at is None
            or row.sql_completed_at is not None):
        raise CleanupStateError("cleanup_critical_state_conflict")
    _plan, remaining, completed = _progress(row)
    if ref not in remaining:
        raise CleanupStateError("cleanup_reference_not_pending")
    await _checkpoint(db, job_id, token, attempt, now=now,
                      expected_remaining=row.remaining_json, expected_completed=row.completed_json,
                      values={
                          "remaining_json": json.dumps([item.model_dump() for item in remaining
                                                        if item != ref]),
                          "completed_json": json.dumps([item.model_dump() for item in
                                                        (*completed, ref)]),
                          "lease_until": now + LEASE_SECONDS,
                      })


async def record_purge(db, job_id: str, token: str, attempt: int, ref: PurgeReference,
                       *, now: float) -> None:
    """The runner must verify absence first; this method does not delete a file."""
    row = await leased_row(db, job_id, token, attempt, now=now)
    if (row.sql_completed_at is None or ref.owner_id != row.user_id
            or ref.kind not in {"pdf", "drive_chunks", "agent_memories"}):
        raise CleanupStateError("cleanup_purge_state_conflict")
    _plan, remaining, completed = _progress(row)
    if ref not in remaining:
        raise CleanupStateError("cleanup_reference_not_pending")
    await _checkpoint(db, job_id, token, attempt, now=now,
                      expected_remaining=row.remaining_json, expected_completed=row.completed_json,
                      values={
                          "remaining_json": json.dumps([item.model_dump() for item in remaining
                                                        if item != ref]),
                          "completed_json": json.dumps([item.model_dump() for item in
                                                        (*completed, ref)]),
                          "lease_until": now + LEASE_SECONDS,
                      })


async def finish(db, job_id: str, token: str, attempt: int, *, now: float) -> None:
    row = await leased_row(db, job_id, token, attempt, now=now)
    _plan, remaining, _completed = _progress(row)
    if row.sql_completed_at is None or remaining:
        raise CleanupStateError("cleanup_not_finished")
    await _checkpoint(db, job_id, token, attempt, now=now,
                      expected_remaining=row.remaining_json, expected_completed=row.completed_json,
                      values={"status": "succeeded", "lease_token": None, "lease_until": None})


async def fail(db, job_id: str, token: str, attempt: int, code: str, *, now: float) -> None:
    if code not in ERROR_CODES:
        raise CleanupStateError("unsafe_cleanup_error_code")
    await leased_row(db, job_id, token, attempt, now=now)
    await _checkpoint(db, job_id, token, attempt, now=now, values={
        "status": "needs_attention", "error_code": code,
        "lease_token": None, "lease_until": None,
    })


async def retry(factory, owner_id: str, job_id: str) -> None:
    async with factory() as db:
        result = await db.execute(update(CleanupJob).where(
            CleanupJob.id == job_id, CleanupJob.user_id == owner_id,
            CleanupJob.status == "needs_attention",
        ).values(status="queued", attempts=0, error_code=None))
        if result.rowcount != 1:
            raise CleanupStateError("cleanup_retry_state_conflict")
        await db.commit()


async def retry_automatic(factory, owner_id: str, job_id: str, *, before: datetime) -> bool:
    """Requeue only an automatic job after its bounded retry backoff elapsed."""
    async with factory() as db:
        result = await db.execute(update(CleanupJob).where(
            CleanupJob.id == job_id, CleanupJob.user_id == owner_id,
            CleanupJob.automatic.is_(True), CleanupJob.status == "needs_attention",
            CleanupJob.updated_at <= before,
        ).values(status="queued", attempts=0, error_code=None))
        await db.commit()
        return result.rowcount == 1


async def cancel(factory, owner_id: str, job_id: str) -> None:
    async with factory() as db:
        result = await db.execute(update(CleanupJob).where(
            CleanupJob.id == job_id, CleanupJob.user_id == owner_id,
            CleanupJob.automatic.is_(False),
            CleanupJob.status.in_(("queued", "needs_attention")),
            CleanupJob.critical_started_at.is_(None), CleanupJob.sql_completed_at.is_(None),
        ).values(status="cancelled", lease_token=None, lease_until=None))
        if result.rowcount != 1:
            raise CleanupStateError("cleanup_cancel_state_conflict")
        await db.commit()


async def status(factory, owner_id: str, job_id: str) -> dict | None:
    async with factory() as db:
        row = await db.scalar(select(CleanupJob).where(
            CleanupJob.id == job_id, CleanupJob.user_id == owner_id,
        ))
        if row is None:
            return None
        plan, remaining, completed = _progress(row)
        return {"id": row.id, "status": row.status, "attempts": row.attempts,
                "automatic": row.automatic,
                "selected_count": len(plan.snapshot.items),
                "remaining_count": len(remaining), "completed_count": len(completed),
                "sql_completed": row.sql_completed_at is not None,
                "error_code": row.error_code,
                "can_cancel": (not row.automatic and row.status in {"queued", "needs_attention"}
                               and row.critical_started_at is None
                               and row.sql_completed_at is None)}
