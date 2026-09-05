"""Ingestion và hybrid retrieval cho tài liệu Google Drive."""

import hashlib
import json
import math
from collections import Counter
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from app.api.schemas import Citation, IndexFileResponse, RagSearchResponse
from app.auth.permissions import RAG_READ, RAG_WRITE
from app.db.models import DocumentChunk, DriveFileIndex
from app.services.chunking import chunk_document
from app.services.embeddings import EmbeddingService, EmbeddingTask, cosine_similarity, tokenize
from app.services.vector_store import DRIVE_COLLECTION, VectorStore
from app.tools.contracts import ToolContext, ToolDefinition
from app.tools.drive import ReadDriveFileInput
from app.tools.registry import ToolRegistry


class IndexDriveFileInput(BaseModel):
    file_id: str = Field(min_length=3, max_length=300)
    force: bool = False


class SearchKnowledgeInput(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    file_ids: list[str] = Field(default_factory=list, max_length=50)
    limit: int = Field(default=6, ge=1, le=20)


class RagService:
    def __init__(self, embeddings: EmbeddingService, vectors: VectorStore):
        self.embeddings = embeddings
        self.vectors = vectors

    async def index_file(
        self,
        payload: IndexDriveFileInput,
        context: ToolContext,
        registry: ToolRegistry,
    ) -> IndexFileResponse:
        # Gọi lồng qua registry để thao tác đọc Drive vẫn đi qua đủ sáu cổng và audit riêng.
        content_result = await registry.execute(
            "drive_read_file",
            ReadDriveFileInput(file_id=payload.file_id, max_characters=500_000).model_dump(),
            ToolContext(
                request_id=context.request_id,
                user=context.user,
                db=context.db,
                settings=context.settings,
                source="rag_ingestion",
            ),
        )
        content_hash = hashlib.sha256(content_result.text.encode("utf-8")).hexdigest()
        existing = await context.db.scalar(
            select(DriveFileIndex).where(
                DriveFileIndex.user_id == context.user.id,
                DriveFileIndex.drive_file_id == payload.file_id,
            )
        )
        if existing and existing.content_hash == content_hash and not payload.force:
            return IndexFileResponse(
                file_id=payload.file_id,
                file_name=existing.name,
                chunks=existing.chunk_count,
                skipped=True,
                message="Tệp không thay đổi, không cần lập chỉ mục lại.",
            )

        drafts = chunk_document(content_result.text, content_result.file.mime_type)
        await context.db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.user_id == context.user.id,
                DocumentChunk.drive_file_id == payload.file_id,
            )
        )
        await self.vectors.delete_by_filter(
            DRIVE_COLLECTION,
            {"user_id": context.user.id, "drive_file_id": payload.file_id},
        )
        for draft in drafts:
            vector = await self.embeddings.embed(draft.content, EmbeddingTask.DOCUMENT)
            # Qdrant nhận UUID hoặc số nguyên làm point ID. UUID5 vừa hợp lệ vừa ổn định,
            # nên re-index cùng nội dung không tạo point trùng.
            chunk_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"{context.user.id}:{payload.file_id}:{content_hash}:{draft.index}",
                )
            )
            row = DocumentChunk(
                id=chunk_id,
                user_id=context.user.id,
                drive_file_id=payload.file_id,
                file_name=content_result.file.name,
                mime_type=content_result.file.mime_type,
                web_view_link=content_result.file.web_view_link,
                chunk_index=draft.index,
                heading=draft.heading,
                content=draft.content,
                token_terms_json=json.dumps(tokenize(draft.content), ensure_ascii=False),
                embedding_json=json.dumps(vector),
            )
            context.db.add(row)
            await self.vectors.upsert(
                DRIVE_COLLECTION,
                chunk_id,
                vector,
                {
                    "user_id": context.user.id,
                    "drive_file_id": payload.file_id,
                    "file_name": content_result.file.name,
                    "chunk_index": draft.index,
                },
            )

        if existing:
            existing.name = content_result.file.name
            existing.mime_type = content_result.file.mime_type
            existing.web_view_link = content_result.file.web_view_link
            existing.modified_time = content_result.file.modified_time
            existing.content_hash = content_hash
            existing.chunk_count = len(drafts)
        else:
            context.db.add(
                DriveFileIndex(
                    user_id=context.user.id,
                    drive_file_id=payload.file_id,
                    name=content_result.file.name,
                    mime_type=content_result.file.mime_type,
                    web_view_link=content_result.file.web_view_link,
                    modified_time=content_result.file.modified_time,
                    content_hash=content_hash,
                    chunk_count=len(drafts),
                )
            )
        await context.db.commit()
        return IndexFileResponse(
            file_id=payload.file_id,
            file_name=content_result.file.name,
            chunks=len(drafts),
            skipped=False,
            message=f"Đã lập chỉ mục {len(drafts)} đoạn.",
        )

    async def search(
        self, payload: SearchKnowledgeInput, context: ToolContext
    ) -> RagSearchResponse:
        statement = select(DocumentChunk).where(DocumentChunk.user_id == context.user.id)
        if payload.file_ids:
            statement = statement.where(DocumentChunk.drive_file_id.in_(payload.file_ids))
        chunks = list((await context.db.scalars(statement)).all())
        if not chunks:
            return RagSearchResponse(query=payload.query, citations=[])

        query_vector = await self.embeddings.embed(payload.query, EmbeddingTask.QUERY)
        dense_rank: list[tuple[str, float]] = []
        if not payload.file_ids:
            dense_rank = await self.vectors.search(
                DRIVE_COLLECTION,
                query_vector,
                {"user_id": context.user.id},
                max(payload.limit * 3, 12),
            )
        if not dense_rank:
            dense_rank = sorted(
                (
                    (chunk.id, cosine_similarity(query_vector, json.loads(chunk.embedding_json)))
                    for chunk in chunks
                ),
                key=lambda item: item[1],
                reverse=True,
            )[: max(payload.limit * 3, 12)]

        lexical_rank = self._lexical_rank(payload.query, chunks)[: max(payload.limit * 3, 12)]
        # Reciprocal Rank Fusion không phụ thuộc thang điểm của dense và lexical.
        fused: dict[str, float] = Counter()
        for ranking in (dense_rank, lexical_rank):
            for rank, (chunk_id, _score) in enumerate(ranking, start=1):
                fused[chunk_id] += 1.0 / (60 + rank)

        by_id = {chunk.id: chunk for chunk in chunks}
        ordered = sorted(fused.items(), key=lambda item: item[1], reverse=True)
        citations: list[Citation] = []
        for chunk_id, score in ordered[: payload.limit]:
            chunk = by_id.get(chunk_id)
            if not chunk:
                continue
            citations.append(
                Citation(
                    file_id=chunk.drive_file_id,
                    file_name=chunk.file_name,
                    chunk_index=chunk.chunk_index,
                    snippet=chunk.content[:500],
                    web_view_link=chunk.web_view_link,
                    score=round(score, 6),
                )
            )
        return RagSearchResponse(query=payload.query, citations=citations)

    @staticmethod
    def _lexical_rank(query: str, chunks: list[DocumentChunk]) -> list[tuple[str, float]]:
        query_terms = tokenize(query)
        if not query_terms:
            return []
        documents = [set(json.loads(chunk.token_terms_json)) for chunk in chunks]
        document_count = len(documents)
        document_frequency = {
            term: sum(1 for terms in documents if term in terms) for term in set(query_terms)
        }
        scores: list[tuple[str, float]] = []
        for chunk, terms in zip(chunks, documents, strict=True):
            score = sum(
                math.log((document_count + 1) / (document_frequency.get(term, 0) + 1)) + 1
                for term in query_terms
                if term in terms
            )
            if score > 0:
                scores.append((chunk.id, score))
        return sorted(scores, key=lambda item: item[1], reverse=True)


def rag_tool_definitions(service: RagService, registry: ToolRegistry) -> list[ToolDefinition]:
    async def index_handler(
        payload: IndexDriveFileInput, context: ToolContext
    ) -> IndexFileResponse:
        return await service.index_file(payload, context, registry)

    async def search_handler(
        payload: SearchKnowledgeInput, context: ToolContext
    ) -> RagSearchResponse:
        return await service.search(payload, context)

    return [
        ToolDefinition(
            name="rag_index_drive_file",
            description="Đọc một tệp Drive và lập chỉ mục RAG bền vững cho người dùng hiện tại.",
            input_model=IndexDriveFileInput,
            output_model=IndexFileResponse,
            handler=index_handler,
            required_permissions={RAG_WRITE},
            rate_limit_per_minute=15,
            max_attempts=1,
        ),
        ToolDefinition(
            name="rag_search",
            description="Tìm các đoạn tài liệu liên quan bằng hybrid dense + lexical retrieval.",
            input_model=SearchKnowledgeInput,
            output_model=RagSearchResponse,
            handler=search_handler,
            required_permissions={RAG_READ},
            rate_limit_per_minute=60,
            max_attempts=2,
        ),
    ]
