"""Durable whole-turn queue, with owner idempotency and fenced publication.

No Google write is replayed by this worker: autonomous Chat only prepares
proposals. After a process loss the unfinished read-only turn is restarted;
provider calls may consume quota again. A completed answer is never regenerated.
"""

import asyncio
import json
import logging
from contextlib import suppress
from time import time
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, or_, select, update

from app.api.schemas import ChatRequest
from app.db.models import AuditEvent, ChatTask, Message, User
from app.tools.contracts import ToolError

logger = logging.getLogger(__name__)
LEASE_SECONDS = 120


def failure_message(exc: Exception, request_id: str) -> str:
    """Expose only application-owned error text, never arbitrary tool output."""
    if isinstance(exc, HTTPException):
        return str(exc.detail)[:1000]
    messages = {
        "quota_minute_exhausted": (
            "Đã chạm giới hạn xử lý trong một phút của Veridra. "
            "Hãy đợi khoảng một phút rồi thử lại; đây không phải xác nhận hết hạn mức Google."
        ),
        "quota_daily_exhausted": (
            "Đã hết ngân sách sử dụng hôm nay của khóa này trên Veridra. "
            "Xem thời điểm đặt lại hoặc chọn khóa khác trong Cài đặt."
        ),
        "context_budget": "Ngữ cảnh quá dài. Hãy mở cuộc trò chuyện mới và chọn ít tài liệu hơn.",
    }
    message = (messages.get(exc.code) if isinstance(exc, ToolError) else None)
    return f"{message or 'Không thể hoàn tất yêu cầu.'} Mã yêu cầu: {request_id}"


def public_task(task: ChatTask) -> dict:
    return {
        "id": task.id, "session_id": task.session_id, "status": task.status,
        "attempts": task.attempts,
        "result": json.loads(task.result_json) if task.status == "completed" else None,
        "error": task.error_message,
    }


async def claim(factory, *, now: float) -> dict | None:
    async with factory() as db:
        expired = and_(ChatTask.status == "running", ChatTask.lease_until < now)
        # A local memory mutation can have completed before the process died.
        # Do not regenerate potentially different writes from an unfinished
        # model turn. Completed Google actions have a separate approval ledger.
        uncertain = (await db.scalars(select(ChatTask).where(
            expired, ChatTask.id.in_(select(AuditEvent.request_id).where(
                AuditEvent.tool_name == "memory_save",
                AuditEvent.status.in_(["success", "started"]),
            )),
        ))).all()
        for row in uncertain:
            row.status = "failed"
            row.error_message = "Bộ nhớ có thể đã được ghi. Hãy kiểm tra bộ nhớ trước khi thử lại."
            await db.execute(update(Message).where(
                Message.user_id == row.user_id, Message.request_id == row.id,
                Message.role == "user").values(status="failed"))
        exhausted = list((await db.scalars(select(ChatTask).where(
            expired, ChatTask.attempts >= 3))).all())
        for row in exhausted:
            row.status = "failed"
            row.error_message = "Không thể phục hồi sau ba lần xử lý. Yêu cầu vẫn được lưu."
            await db.execute(update(Message).where(
                Message.user_id == row.user_id, Message.request_id == row.id,
                Message.role == "user").values(status="failed"))
        eligible = or_(ChatTask.status == "queued", and_(expired, ChatTask.attempts < 3))
        query = select(ChatTask).where(eligible).order_by(ChatTask.created_at).limit(1)
        if db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        row = await db.scalar(query)
        if row is None:
            await db.commit()
            return None
        token = str(uuid4())
        attempt = row.attempts + 1
        changed = await db.execute(update(ChatTask).where(
            ChatTask.id == row.id, ChatTask.attempts == row.attempts, eligible,
        ).values(status="running", attempts=attempt, lease_token=token,
                 lease_until=now + LEASE_SECONDS, error_message=None))
        if changed.rowcount != 1:
            await db.rollback()
            return None
        data = {"id": row.id, "owner": row.user_id, "payload": row.payload_json,
                "token": token, "attempt": attempt}
        await db.commit()
        return data


async def fence(db, task_id: str, token: str, attempt: int, **values) -> None:
    changed = await db.execute(update(ChatTask).where(
        ChatTask.id == task_id, ChatTask.status == "running",
        ChatTask.lease_token == token, ChatTask.attempts == attempt,
        ChatTask.lease_until > time(),
    ).values(**values))
    if changed.rowcount != 1:
        raise asyncio.CancelledError("Chat task lease lost")


async def execute_one(factory, app) -> bool:
    claimed = await claim(factory, now=time())
    if claimed is None:
        return False
    async with factory() as db:
        user = await db.get(User, claimed["owner"])
        if user is None or not user.is_active:
            await fence(db, claimed["id"], claimed["token"], claimed["attempt"],
                        status="failed", error_message="Tài khoản không còn hoạt động.")
            await db.commit()
            return True
        request = SimpleNamespace(app=app, state=SimpleNamespace(
            request_id=claimed["id"], chat_task=claimed))
        from app.api.chat import chat

        try:
            async def observe_lease():
                while True:
                    await asyncio.sleep(1)
                    async with factory() as observer:
                        alive = await observer.scalar(select(ChatTask.id).where(
                            ChatTask.id == claimed["id"], ChatTask.status == "running",
                            ChatTask.lease_token == claimed["token"],
                            ChatTask.lease_until > time(),
                        ))
                    if alive is None:
                        return

            operation = asyncio.create_task(chat(
                ChatRequest.model_validate_json(claimed["payload"]), request, user, db))
            observation = asyncio.create_task(observe_lease())
            try:
                done, _ = await asyncio.wait(
                    {operation, observation}, return_when=asyncio.FIRST_COMPLETED)
                if operation in done:
                    await operation
                else:
                    await observation
                    operation.cancel()
                    with suppress(asyncio.CancelledError):
                        await operation
            finally:
                observation.cancel()
                operation.cancel()
                with suppress(asyncio.CancelledError):
                    await observation
                with suppress(asyncio.CancelledError):
                    await operation
        except asyncio.CancelledError:
            # Shutdown leaves the lease resumable. Explicit user cancellation
            # is already persisted by the cancel endpoint, not by this worker.
            await db.rollback()
            raise
        except Exception as exc:
            await db.rollback()
            # HTTPException details here are the sanitized application messages.
            detail = failure_message(exc, claimed["id"])
            try:
                await fence(db, claimed["id"], claimed["token"], claimed["attempt"],
                            status="failed", error_message=detail[:1000], lease_until=None)
                await db.execute(update(Message).where(
                    Message.request_id == claimed["id"], Message.user_id == claimed["owner"],
                    Message.role == "user").values(status="failed"))
                await db.commit()
            except asyncio.CancelledError:
                await db.rollback()
            logger.warning("Chat worker failed; type=%s request_id=%s",
                           type(exc).__name__, claimed["id"])
    return True


async def worker(factory, app):
    while True:
        try:
            worked = await execute_one(factory, app)
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise
            # Lease revocation is task cancellation, not worker shutdown.
            worked = True
        except Exception as exc:
            logger.warning("Chat worker retry; type=%s", type(exc).__name__)
            worked = False
        await asyncio.sleep(0.1 if worked else 1)
