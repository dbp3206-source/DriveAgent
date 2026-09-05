"""CRUD và tìm kiếm bộ nhớ dài hạn của người dùng hiện tại."""

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession, require_permission
from app.api.drive import execute
from app.api.schemas import MemoryCreateRequest, MemoryResponse, MemoryUpdateRequest
from app.auth.permissions import MEMORY_READ, MEMORY_WRITE
from app.core.security import SENSITIVE_CONTENT
from app.db.models import LongTermMemory
from app.services.embeddings import EmbeddingTask
from app.services.memory import (
    MemoryListResponse,
    SaveMemoryInput,
    SearchMemoryInput,
    memory_response,
)
from app.services.vector_store import MEMORY_COLLECTION

router = APIRouter(prefix="/api/memories", tags=["memory"])


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    user: CurrentUser,
    db: DbSession,
    include_archived: bool = False,
    kind: str | None = None,
    _allowed=Depends(require_permission(MEMORY_READ)),
):
    statement = select(LongTermMemory).where(LongTermMemory.user_id == user.id)
    if not include_archived:
        statement = statement.where(LongTermMemory.is_archived.is_(False))
    if kind:
        statement = statement.where(LongTermMemory.kind == kind)
    statement = statement.order_by(LongTermMemory.updated_at.desc())
    rows = list((await db.scalars(statement)).all())
    return MemoryListResponse(memories=[memory_response(row) for row in rows])


@router.post("", response_model=MemoryResponse)
async def create_memory(
    payload: MemoryCreateRequest, request: Request, user: CurrentUser, db: DbSession
):
    return await execute(
        request,
        user,
        db,
        "memory_save",
        SaveMemoryInput(**payload.model_dump()).model_dump(mode="json"),
    )


@router.get("/search", response_model=MemoryListResponse)
async def search_memories(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    q: str = Query(min_length=2, max_length=2000),
    limit: int = Query(default=6, ge=1, le=20),
):
    return await execute(
        request,
        user,
        db,
        "memory_search",
        SearchMemoryInput(query=q, limit=limit).model_dump(mode="json"),
    )


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    payload: MemoryUpdateRequest,
    request: Request,
    user: CurrentUser,
    db: DbSession,
    _allowed=Depends(require_permission(MEMORY_WRITE)),
):
    row = await db.scalar(
        select(LongTermMemory).where(
            LongTermMemory.id == memory_id, LongTermMemory.user_id == user.id
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy bộ nhớ.")
    updates = payload.model_dump(exclude_unset=True)
    if "content" in updates:
        if SENSITIVE_CONTENT.search(updates["content"]):
            raise HTTPException(
                status_code=400,
                detail="Bộ nhớ có vẻ chứa secret. Hãy bỏ API key, token hoặc mật khẩu.",
            )
        row.content = updates["content"]
        normalized = " ".join(row.content.strip().casefold().split())
        row.normalized_hash = hashlib.sha256(normalized.encode()).hexdigest()
        vector = await request.app.state.embeddings.embed(
            row.content, EmbeddingTask.SEMANTIC_SIMILARITY
        )
        row.embedding_json = json.dumps(vector)
    if "tags" in updates:
        row.tags_json = json.dumps(sorted(set(updates["tags"])), ensure_ascii=False)
    if "confidence" in updates:
        row.confidence = updates["confidence"]
    if "is_archived" in updates:
        row.is_archived = updates["is_archived"]
    if "content" in updates:
        await request.app.state.vector_store.upsert(
            MEMORY_COLLECTION,
            row.id,
            json.loads(row.embedding_json),
            {"user_id": user.id, "kind": row.kind},
        )
    await db.commit()
    return memory_response(row)


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: str,
    request: Request,
    user: CurrentUser,
    db: DbSession,
    _allowed=Depends(require_permission(MEMORY_WRITE)),
):
    row = await db.scalar(
        select(LongTermMemory).where(
            LongTermMemory.id == memory_id, LongTermMemory.user_id == user.id
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy bộ nhớ.")
    await db.delete(row)
    await db.commit()
    await request.app.state.vector_store.delete_points(MEMORY_COLLECTION, [memory_id])
