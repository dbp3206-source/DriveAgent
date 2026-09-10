"""Bộ nhớ dài hạn có phân loại, dedup và tìm kiếm hybrid theo từng user."""

import hashlib
import json
import re

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.schemas import MemoryResponse
from app.auth.permissions import MEMORY_READ, MEMORY_WRITE
from app.core.security import SENSITIVE_CONTENT
from app.db.models import LongTermMemory, MemoryKind
from app.services.embeddings import EmbeddingService, EmbeddingTask, cosine_similarity, tokenize
from app.services.vector_store import MEMORY_COLLECTION, VectorStore
from app.tools.contracts import ToolContext, ToolDefinition, ToolError

# Memory search is user-facing recall, so an unrelated top-k result is worse
# than an honest empty result.  Dense-only matches need stronger evidence than
# matches that also share concrete terms with the user's query.
MIN_HYBRID_MEMORY_SCORE = 0.45


class SaveMemoryInput(BaseModel):
    kind: MemoryKind
    content: str = Field(min_length=2, max_length=8000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(default=1.0, ge=0, le=1)
    source_session_id: str | None = None


class SearchMemoryInput(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    kinds: list[MemoryKind] = Field(default_factory=list)
    limit: int = Field(default=6, ge=1, le=20)


class MemoryListResponse(BaseModel):
    memories: list[MemoryResponse]


def normalize_memory(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().casefold())


def memory_response(row: LongTermMemory) -> MemoryResponse:
    return MemoryResponse(
        id=row.id,
        kind=row.kind,
        content=row.content,
        tags=json.loads(row.tags_json),
        confidence=row.confidence,
        is_archived=row.is_archived,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class MemoryService:
    def __init__(self, embeddings: EmbeddingService, vectors: VectorStore):
        self.embeddings = embeddings
        self.vectors = vectors

    async def save(self, payload: SaveMemoryInput, context: ToolContext) -> MemoryResponse:
        if SENSITIVE_CONTENT.search(payload.content):
            raise ToolError(
                "Bộ nhớ có vẻ chứa secret. Hãy bỏ API key, token hoặc mật khẩu.",
                code="sensitive_memory_rejected",
            )
        normalized_hash = hashlib.sha256(normalize_memory(payload.content).encode()).hexdigest()
        existing = await context.db.scalar(
            select(LongTermMemory).where(
                LongTermMemory.user_id == context.user.id,
                LongTermMemory.normalized_hash == normalized_hash,
                LongTermMemory.is_archived.is_(False),
            )
        )
        if existing:
            # Dedup idempotent: cập nhật metadata thay vì tạo nhiều bản ghi giống nhau.
            existing.confidence = max(existing.confidence, payload.confidence)
            existing.tags_json = json.dumps(
                sorted(set(json.loads(existing.tags_json)) | set(payload.tags)),
                ensure_ascii=False,
            )
            await context.db.commit()
            return memory_response(existing)

        vector = await self.embeddings.embed(payload.content, EmbeddingTask.SEMANTIC_SIMILARITY)
        row = LongTermMemory(
            user_id=context.user.id,
            kind=payload.kind.value,
            content=payload.content.strip(),
            normalized_hash=normalized_hash,
            tags_json=json.dumps(sorted(set(payload.tags)), ensure_ascii=False),
            source_session_id=payload.source_session_id,
            confidence=payload.confidence,
            embedding_json=json.dumps(vector),
        )
        context.db.add(row)
        await context.db.flush()
        await self.vectors.upsert(
            MEMORY_COLLECTION,
            row.id,
            vector,
            {"user_id": context.user.id, "kind": row.kind},
        )
        await context.db.commit()
        return memory_response(row)

    async def search(self, payload: SearchMemoryInput, context: ToolContext) -> MemoryListResponse:
        statement = select(LongTermMemory).where(
            LongTermMemory.user_id == context.user.id,
            LongTermMemory.is_archived.is_(False),
        )
        if payload.kinds:
            statement = statement.where(
                LongTermMemory.kind.in_([kind.value for kind in payload.kinds])
            )
        rows = list((await context.db.scalars(statement)).all())
        query_vector = await self.embeddings.embed(payload.query, EmbeddingTask.SEMANTIC_SIMILARITY)
        query_terms = set(tokenize(payload.query))

        # Qdrant là đường tìm dense chính. SQLite giữ vector dự phòng để ứng dụng vẫn
        # hoạt động khi embedded store bị khóa/hỏng hoặc trong unit test tối giản.
        vector_filters: dict[str, str | list[str]] = {"user_id": context.user.id}
        if payload.kinds:
            vector_filters["kind"] = [kind.value for kind in payload.kinds]
        qdrant_hits = await self.vectors.search(
            MEMORY_COLLECTION,
            query_vector,
            vector_filters,
            max(payload.limit * 4, 24),
        )
        dense_scores = dict(qdrant_hits)
        scored: list[tuple[LongTermMemory, float]] = []
        for row in rows:
            dense_score = dense_scores.get(
                row.id,
                cosine_similarity(query_vector, json.loads(row.embedding_json)),
            )
            lexical_score = len(query_terms & set(tokenize(row.content))) / max(len(query_terms), 1)
            hybrid_score = 0.72 * dense_score + 0.28 * lexical_score
            # Dense embeddings are excellent for ordering plausible memories but
            # can assign a deceptively high score to unrelated short identifiers.
            if hybrid_score >= MIN_HYBRID_MEMORY_SCORE and lexical_score > 0:
                scored.append((row, hybrid_score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return MemoryListResponse(
            memories=[memory_response(row) for row, _score in scored[: payload.limit]]
        )


def memory_tool_definitions(service: MemoryService) -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="memory_save",
            description=(
                "Lưu một fact, preference, context, episode, procedure hoặc summary dài hạn."
            ),
            input_model=SaveMemoryInput,
            output_model=MemoryResponse,
            handler=service.save,
            required_permissions={MEMORY_WRITE},
            rate_limit_per_minute=30,
            max_attempts=1,
        ),
        ToolDefinition(
            name="memory_search",
            description="Tìm bộ nhớ dài hạn liên quan của đúng người dùng hiện tại.",
            input_model=SearchMemoryInput,
            output_model=MemoryListResponse,
            handler=service.search,
            required_permissions={MEMORY_READ},
            rate_limit_per_minute=60,
            max_attempts=2,
        ),
    ]
