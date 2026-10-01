"""Authenticated queue endpoints; no credentials or cross-owner task visibility."""

import asyncio
from uuid import UUID
from weakref import WeakValueDictionary

from fastapi import APIRouter, HTTPException
from pydantic import Field
from sqlalchemy import select, update

from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import ChatRequest
from app.db.models import ChatSession, ChatTask, Message, User
from app.services.chat_tasks import public_task

router = APIRouter(prefix="/api/chat/tasks", tags=["chat"])
_owner_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


class SubmitTask(ChatRequest):
    client_key: str = Field(min_length=36, max_length=36)


@router.post("", status_code=202)
async def enqueue(payload: SubmitTask, user: CurrentUser, db: DbSession):
    lock = _owner_locks.setdefault(user.id, asyncio.Lock())
    async with lock:
        return await _enqueue(payload, user, db)


async def _enqueue(payload: SubmitTask, user: CurrentUser, db: DbSession):
    try:
        client_key = str(UUID(payload.client_key))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid client task identifier") from exc
    # Serialize owner submissions (and duplicate retries) on PostgreSQL.
    await db.scalar(select(User).where(User.id == user.id).with_for_update())
    previous = await db.scalar(select(ChatTask).where(
        ChatTask.user_id == user.id, ChatTask.client_key == client_key))
    body = ChatRequest.model_validate(payload.model_dump(exclude={"client_key"}))
    if previous:
        original = ChatRequest.model_validate_json(previous.payload_json)
        # A new session's ID is allocated server-side after the first submit.
        original.session_id = payload.session_id
        if original != body:
            raise HTTPException(
                status_code=409, detail="Task identifier belongs to another request")
        return public_task(previous)
    active = await db.scalar(select(ChatTask.id).where(
        ChatTask.user_id == user.id, ChatTask.status.in_(["queued", "running"])))
    if active:
        raise HTTPException(status_code=409, detail="Một yêu cầu đang xử lý; hãy chờ hoặc dừng nó.")
    _, message = body.controls.parse_leading_commands(body.message)
    if not message:
        raise HTTPException(status_code=422, detail="Hãy nhập nội dung sau lệnh nhanh.")
    if body.session_id:
        session = await db.scalar(select(ChatSession).where(
            ChatSession.id == body.session_id, ChatSession.user_id == user.id))
        if session is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện.")
    else:
        session = ChatSession(user_id=user.id, title=message[:80])
        db.add(session)
        await db.flush()
    body.session_id = session.id
    task = ChatTask(user_id=user.id, session_id=session.id, client_key=client_key,
                    payload_json=body.model_dump_json())
    db.add(task)
    await db.flush()
    db.add(Message(user_id=user.id, session_id=session.id, request_id=task.id,
                   role="user", content=message, status="running"))
    await db.commit()
    await db.refresh(task)
    return public_task(task)


@router.get("")
async def pending(user: CurrentUser, db: DbSession):
    rows = (await db.scalars(select(ChatTask).where(
        ChatTask.user_id == user.id, ChatTask.status.in_(["queued", "running"])
    ).order_by(ChatTask.created_at).limit(4))).all()
    return {"items": [public_task(row) for row in rows]}


async def owned(db, owner: str, task_id: str) -> ChatTask:
    row = await db.scalar(select(ChatTask).where(ChatTask.id == task_id, ChatTask.user_id == owner))
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu.")
    return row


@router.get("/{task_id}")
async def get_task(task_id: str, user: CurrentUser, db: DbSession):
    return public_task(await owned(db, user.id, task_id))


@router.post("/{task_id}/cancel")
async def cancel(task_id: str, user: CurrentUser, db: DbSession):
    row = await owned(db, user.id, task_id)
    if row.status in {"queued", "running"}:
        changed = await db.execute(update(ChatTask).where(
            ChatTask.id == task_id, ChatTask.user_id == user.id,
            ChatTask.status.in_(["queued", "running"]),
        ).values(status="cancelled", lease_until=None, lease_token=None))
        if changed.rowcount:
            await db.execute(update(Message).where(
                Message.user_id == user.id, Message.request_id == task_id,
                Message.role == "user").values(status="cancelled"))
        await db.commit()
        await db.refresh(row)
    return public_task(row)
