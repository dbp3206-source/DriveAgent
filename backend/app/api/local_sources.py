import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DbSession, require_permission
from app.auth.permissions import RAG_READ, RAG_WRITE, permissions_for_role
from app.db.models import AuditEvent, LocalSource
from app.services.local_sources import MAX_BYTES, extract_text, hash_content

router = APIRouter(prefix="/api/local-sources", tags=["local-sources"])


@router.get("", dependencies=[Depends(require_permission(RAG_READ))])
async def listing(user: CurrentUser, db: DbSession):
    rows = await db.scalars(
        select(LocalSource)
        .where(LocalSource.user_id == user.id)
        .order_by(LocalSource.created_at.desc())
        .limit(200)
    )
    return [{"id": row.id, "name": row.name, "characters": len(row.content)} for row in rows]


@router.post("")
async def upload(name: str, request: Request, user: CurrentUser, db: DbSession):
    if RAG_WRITE not in permissions_for_role(user.role):
        raise HTTPException(403, "Bạn không có quyền import tài liệu.")
    if not name.strip() or len(name) > 240 or any(c in name for c in "/\\\r\n\x00"):
        raise HTTPException(400, "Tên tệp không hợp lệ.")
    # Read raw stream: rejects oversized bodies before buffering an entire multipart upload.
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, "Tệp vượt 2 MB.")
        data.extend(chunk)
    text = await asyncio.to_thread(extract_text, name, bytes(data))
    digest = hash_content(text)
    row = await db.scalar(
        select(LocalSource).where(
            LocalSource.user_id == user.id, LocalSource.content_hash == digest
        )
    )
    if row is None:
        row = LocalSource(user_id=user.id, name=name, content=text, content_hash=digest)
        try:
            async with db.begin_nested():
                db.add(row)
                await db.flush()
        except IntegrityError:
            row = await db.scalar(
                select(LocalSource).where(
                    LocalSource.user_id == user.id, LocalSource.content_hash == digest
                )
            )
            if row is None:
                raise HTTPException(409, "Tài liệu vừa thay đổi, hãy thử lại.") from None
    db.add(
        AuditEvent(
            request_id=request.state.request_id,
            user_id=user.id,
            role=user.role,
            tool_name="local_source_import",
            status="success",
            result_json=json.dumps({"source_id": row.id, "characters": len(text)}),
        )
    )
    await db.commit()
    return {"id": row.id, "name": row.name, "characters": len(row.content)}


@router.get(
    "/{source_id}/text",
    response_class=PlainTextResponse,
    dependencies=[Depends(require_permission(RAG_READ))],
)
async def read(source_id: str, user: CurrentUser, db: DbSession):
    row = await db.scalar(
        select(LocalSource).where(LocalSource.id == source_id, LocalSource.user_id == user.id)
    )
    if row is None:
        raise HTTPException(404, "Không tìm thấy tài liệu.")
    return PlainTextResponse(
        row.content, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    )
