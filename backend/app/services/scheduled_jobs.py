"""Durable scheduler queue for cold-start-safe, read-only briefings."""

import asyncio
import json
import logging
from datetime import UTC, datetime
from time import time
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.db.models import ScheduledJob, User
from app.services.morning_briefing import MorningBriefingService
from app.services.premeeting_briefing import PreMeetingBriefingService
from app.services.user_inference import user_runtime_settings

KINDS = {"morning", "pre_meeting"}


async def enqueue_for_invited_users(db, settings, *, kind: str, dedupe_key: str) -> dict:
    if kind not in KINDS:
        raise ValueError("Unsupported scheduled job kind")
    users = (await db.scalars(select(User).where(User.is_active.is_(True)))).all()
    eligible = [
        user
        for user in users
        if user.encrypted_google_credentials and settings.beta_email_allowed(user.email)
    ][:4]
    created = 0
    existing = 0
    for user in eligible:
        try:
            async with db.begin_nested():
                db.add(
                    ScheduledJob(
                        user_id=user.id,
                        kind=kind,
                        dedupe_key=dedupe_key,
                        payload_json="{}",
                    )
                )
                await db.flush()
            created += 1
        except IntegrityError:
            existing += 1
    await db.commit()
    return {"eligible_users": len(eligible), "created": created, "existing": existing}


async def _claim(session_factory, *, now: float) -> dict | None:
    async with session_factory() as db:
        dialect = db.bind.dialect.name
        eligible = or_(
            ScheduledJob.status == "queued",
            and_(
                ScheduledJob.status == "running",
                ScheduledJob.lease_until < now,
                ScheduledJob.attempts < 3,
            ),
        )
        await db.execute(
            update(ScheduledJob)
            .where(
                ScheduledJob.status == "running",
                ScheduledJob.lease_until < now,
                ScheduledJob.attempts >= 3,
            )
            .values(status="failed", error_code="attempts_exhausted", lease_until=None)
        )
        query = select(ScheduledJob).where(eligible).order_by(ScheduledJob.created_at).limit(1)
        if dialect == "postgresql":
            query = query.with_for_update(skip_locked=True)
        row = await db.scalar(query)
        if row is None:
            await db.commit()
            return None
        token = str(uuid4())
        next_attempt = row.attempts + 1
        changed = await db.execute(
            update(ScheduledJob)
            .where(ScheduledJob.id == row.id, ScheduledJob.attempts == row.attempts, eligible)
            .values(
                status="running",
                attempts=next_attempt,
                lease_until=now + 300,
                lease_token=token,
                error_code=None,
            )
        )
        if changed.rowcount != 1:
            await db.rollback()
            return None
        await db.commit()
        return {
            "id": row.id,
            "user_id": row.user_id,
            "kind": row.kind,
            "attempt": next_attempt,
            "lease_token": token,
        }


async def _finish(session_factory, claimed: dict, *, result: dict | None, error: str | None):
    async with session_factory() as db:
        values = {
            "status": "completed" if error is None else "failed",
            "checkpoint_json": json.dumps(result or {}, ensure_ascii=False),
            "error_code": error,
            "lease_until": None,
            "lease_token": None,
            "updated_at": datetime.now(UTC),
        }
        changed = await db.execute(
            update(ScheduledJob)
            .where(
                ScheduledJob.id == claimed["id"],
                ScheduledJob.status == "running",
                ScheduledJob.attempts == claimed["attempt"],
                ScheduledJob.lease_token == claimed["lease_token"],
                ScheduledJob.lease_until > time(),
            )
            .values(**values)
        )
        if changed.rowcount == 1:
            await db.commit()
        else:
            await db.rollback()


async def execute_one(session_factory, settings, registry) -> bool:
    claimed = await _claim(session_factory, now=time())
    if claimed is None:
        return False
    try:
        async with session_factory() as db:
            user = await db.get(User, claimed["user_id"])
            if user is None or not user.is_active or not settings.beta_email_allowed(user.email):
                raise ValueError("scheduled_user_unavailable")
            runtime = await user_runtime_settings(db, user.id, settings)
            request_id = f"scheduled-{claimed['id']}"
            if claimed["kind"] == "morning":
                result = await MorningBriefingService(runtime, registry).generate_brief(
                    user, db, request_id=request_id
                )
            else:
                result = await PreMeetingBriefingService(runtime, registry).generate(
                    user, db, request_id=request_id
                )
        await _finish(session_factory, claimed, result=result, error=None)
    except Exception as exc:
        code = getattr(exc, "code", None) or type(exc).__name__
        await _finish(session_factory, claimed, result=None, error=str(code)[:64])
        logging.getLogger(__name__).warning(
            "Scheduled briefing failed; kind=%s code=%s", claimed["kind"], str(code)[:64]
        )
    return True


async def worker(session_factory, settings, registry):
    while True:
        try:
            worked = await execute_one(session_factory, settings, registry)
        except Exception:
            worked = False
            logging.getLogger(__name__).warning("Scheduled worker will retry")
        await asyncio.sleep(2 if worked else 10)
