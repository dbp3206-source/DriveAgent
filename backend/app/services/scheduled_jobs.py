"""Durable scheduler queue for cold-start-safe, read-only briefings."""

import asyncio
import json
import logging
from datetime import UTC, datetime
from time import time
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.db.models import ScheduledJob, User
from app.services.morning_briefing import MorningBriefingService
from app.services.premeeting_briefing import PreMeetingBriefingService
from app.services.user_inference import user_runtime_settings
from app.tools.contracts import ToolError

KINDS = {"morning", "pre_meeting"}


async def enqueue_for_invited_users(
    db, settings, *, kind: str, dedupe_key: str, registry=None
) -> dict:
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
    failed_users = 0
    for user in eligible:
        jobs = [(dedupe_key, {})]
        if kind == "pre_meeting":
            if registry is None:
                raise ValueError("Pre-meeting scheduling requires Calendar registry")
            try:
                runtime = await user_runtime_settings(db, user.id, settings)
                service = PreMeetingBriefingService(runtime, registry)
                events = await service.due_events(user, db, request_id=f"schedule-{uuid4()}")
            except SQLAlchemyError:
                # A broken shared transaction cannot safely be called an
                # isolated Calendar failure or continued for another owner.
                raise
            except Exception:
                failed_users += 1
                continue
            jobs = []
            for event in events:
                identity = service.event_identity(event)
                jobs.append((f"pre_meeting:{identity['version']}", {"event": identity}))
        for job_key, payload in jobs:
            try:
                async with db.begin_nested():
                    db.add(
                        ScheduledJob(
                            user_id=user.id,
                            kind=kind,
                            dedupe_key=job_key,
                            payload_json=json.dumps(payload),
                        )
                    )
                    await db.flush()
                created += 1
            except IntegrityError:
                existing += 1
    await db.commit()
    result = {"eligible_users": len(eligible), "created": created, "existing": existing}
    if kind == "pre_meeting":
        result.update(
            failed_users=failed_users,
            status="partial_failure" if failed_users else "accepted",
            failures=[{"code": "calendar_read_failed", "count": failed_users}]
            if failed_users
            else [],
        )
    return result


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
            "payload_json": row.payload_json,
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
        try:
            payload = json.loads(claimed["payload_json"])
            if not isinstance(payload, dict):
                raise ValueError("Expected payload object")
        except (TypeError, ValueError) as exc:
            raise ToolError(
                "Tác vụ có dữ liệu không hợp lệ; không thể thực thi.",
                code="scheduled_payload_invalid",
            ) from exc
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
                expected_event = payload.get("event")
                if not isinstance(expected_event, dict) or set(expected_event) != {"id", "version"}:
                    raise ToolError(
                        "Tác vụ trước hẹn thiếu phiên bản sự kiện; cần tạo lại từ lịch hiện tại.",
                        code="scheduled_event_identity_missing",
                    )
                result = await PreMeetingBriefingService(runtime, registry).generate(
                    user, db, request_id=request_id, expected_event=expected_event
                )
        await _finish(session_factory, claimed, result=result, error=None)
    except Exception as exc:
        code = getattr(exc, "code", None) or type(exc).__name__
        await _finish(
            session_factory, claimed, result={"error_code": str(code)[:64]}, error=str(code)[:64]
        )
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
