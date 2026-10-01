"""Ingestion và hybrid retrieval cho tài liệu Google Drive."""

import hashlib
import json
import math
import re
from collections import Counter
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update

from app.api.schemas import Citation, IndexFileResponse, RagSearchResponse, UnindexFileResponse
from app.auth.permissions import RAG_READ, RAG_WRITE
from app.db.models import DocumentChunk, DriveFileIndex, LocalSource
from app.services.chunking import chunk_document
from app.services.embeddings import (
    EMBEDDING_DIMENSION,
    EmbeddingService,
    EmbeddingTask,
    cosine_similarity,
    scoped_embeddings,
    tokenize,
)
from app.services.local_sources import excluded_ocr_source
from app.services.pgvector import is_postgres_session, rank_vectors
from app.services.vector_store import DRIVE_COLLECTION, VectorStore
from app.tools.contracts import ToolContext, ToolDefinition, ToolError
from app.tools.drive import ReadDriveFileInput
from app.tools.registry import ToolRegistry


class IndexDriveFileInput(BaseModel):
    file_id: str = Field(min_length=3, max_length=300)
    force: bool = False


class UnindexDriveFileInput(BaseModel):
    file_id: str = Field(min_length=3, max_length=300)


class SearchKnowledgeInput(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    file_ids: list[str] = Field(default_factory=list, max_length=50)
    limit: int = Field(default=6, ge=1, le=20)


# Changing extraction, chunk boundaries, provenance, embeddings, or stored payload semantics
# must invalidate old rows even when the Drive revision itself did not change. SQLite does
# not enforce String lengths, but the fingerprint deliberately stays at the existing 64-char
# contract so this remains portable to stricter databases.
INDEX_PIPELINE_VERSION = "rag-page-aware-v5-local-provenance"


def _index_version_tag(settings) -> str:  # type: ignore[no-untyped-def]
    identity = (
        f"{INDEX_PIPELINE_VERSION}|{settings.gemini_embedding_model}|"
        f"{EMBEDDING_DIMENSION}|"
        f"{'gemini' if settings.gemini_is_configured else 'local-hashing'}"
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]


def index_fingerprint(text: str, settings) -> str:  # type: ignore[no-untyped-def]
    """Return a content + pipeline fingerprint used as the durable index version."""

    content_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{_index_version_tag(settings)}:{content_digest[:51]}"


def is_current_index_hash(value: str | None, settings) -> bool:  # type: ignore[no-untyped-def]
    """Recognize only rows built by the active parser/chunker/embedding contract."""

    return bool(value and value.startswith(f"{_index_version_tag(settings)}:") and len(value) == 64)


class RagService:
    def __init__(self, embeddings: EmbeddingService, vectors: VectorStore):
        self.embeddings = embeddings
        self.vectors = vectors

    def _embedding_for(self, context: ToolContext):
        """Never spend the process owner's key for another user's retrieval.

        SQL/vector ownership alone does not isolate provider credentials. A
        request-scoped client also prevents key-switch races on a shared client.
        """
        return scoped_embeddings(self.embeddings, context.settings)

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
        content_hash = index_fingerprint(content_result.text, context.settings)
        existing = await context.db.scalar(
            select(DriveFileIndex).where(
                DriveFileIndex.user_id == context.user.id,
                DriveFileIndex.drive_file_id == payload.file_id,
            )
        )
        if existing and existing.content_hash == content_hash and not payload.force:
            # Rename/metadata-only edits still advance Drive revision without re-embedding.
            existing.modified_time = content_result.file.modified_time
            existing.name = content_result.file.name
            existing.web_view_link = content_result.file.web_view_link
            await context.db.execute(
                update(DocumentChunk)
                .where(
                    DocumentChunk.user_id == context.user.id,
                    DocumentChunk.drive_file_id == payload.file_id,
                )
                .values(
                    file_name=content_result.file.name,
                    web_view_link=content_result.file.web_view_link,
                )
            )
            await context.db.commit()
            return IndexFileResponse(
                file_id=payload.file_id,
                file_name=existing.name,
                chunks=existing.chunk_count,
                skipped=True,
                message="Tệp không thay đổi, không cần lập chỉ mục lại.",
            )

        drafts = chunk_document(content_result.text, content_result.file.mime_type)
        # Reserve/embed BEFORE replacing an existing index. Quota errors keep old data intact.
        async with self._embedding_for(context) as embeddings:
            vectors = await embeddings.embed_many(
                [draft.content for draft in drafts], EmbeddingTask.DOCUMENT
            )
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
        for draft, vector in zip(drafts, vectors, strict=True):
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
                # Keep page provenance in the durable row without a destructive
                # schema migration; it is invisible when Markdown is rendered.
                content=(
                    f"<!-- page:{draft.page_number} -->\n{draft.content}"
                    if draft.page_number is not None
                    else draft.content
                ),
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
            existing.indexed_at = datetime.now(UTC)
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

    async def unindex_file(
        self,
        payload: UnindexDriveFileInput,
        context: ToolContext,
    ) -> UnindexFileResponse:
        """Remove one user's index without touching the source file or another user."""

        index_row = await context.db.scalar(
            select(DriveFileIndex).where(
                DriveFileIndex.user_id == context.user.id,
                DriveFileIndex.drive_file_id == payload.file_id,
            )
        )
        chunks = list(
            (
                await context.db.scalars(
                    select(DocumentChunk).where(
                        DocumentChunk.user_id == context.user.id,
                        DocumentChunk.drive_file_id == payload.file_id,
                    )
                )
            ).all()
        )
        # Delete exact point IDs first when Qdrant is available. SQLite remains the
        # authoritative fallback, so a temporary vector-store outage cannot leave
        # searchable rows behind after the transaction commits.
        await self.vectors.delete_points(DRIVE_COLLECTION, [row.id for row in chunks])
        await context.db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.user_id == context.user.id,
                DocumentChunk.drive_file_id == payload.file_id,
            )
        )
        if index_row is not None:
            await context.db.delete(index_row)
        await context.db.commit()
        file_name = index_row.name if index_row is not None else payload.file_id
        return UnindexFileResponse(
            file_id=payload.file_id,
            file_name=file_name,
            chunks_removed=len(chunks),
            message=(
                f"Đã hoàn tác lập chỉ mục cho {file_name}; "
                f"đã xóa {len(chunks)} đoạn khỏi kho hỏi đáp."
                if chunks
                else "Tệp chưa có chỉ mục; không có dữ liệu nào cần xóa."
            ),
        )

    async def index_local_source(
        self,
        local_source: LocalSource,
        context: ToolContext,
    ) -> int:
        if excluded_ocr_source(local_source, context.settings):
            raise ToolError("OCR đã được loại khỏi phạm vi hỗ trợ.", code="pdf_ocr_excluded")
        file_id = f"local:{local_source.id}"
        content_hash = index_fingerprint(local_source.content, context.settings)
        web_link = f"{context.settings.public_base_url}/api/local-sources/{local_source.id}/text"

        drafts = chunk_document(local_source.content, "text/markdown")
        if not drafts:
            return 0
        async with self._embedding_for(context) as embeddings:
            vectors = await embeddings.embed_many(
                [draft.content for draft in drafts], EmbeddingTask.DOCUMENT
            )
        await context.db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.user_id == context.user.id,
                DocumentChunk.drive_file_id == file_id,
            )
        )
        await self.vectors.delete_by_filter(
            DRIVE_COLLECTION,
            {"user_id": context.user.id, "drive_file_id": file_id},
        )
        for draft, vector in zip(drafts, vectors, strict=True):
            chunk_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"{context.user.id}:{file_id}:{content_hash}:{draft.index}",
                )
            )
            row = DocumentChunk(
                id=chunk_id,
                user_id=context.user.id,
                drive_file_id=file_id,
                file_name=local_source.name,
                mime_type="text/markdown",
                web_view_link=web_link,
                chunk_index=draft.index,
                heading=draft.heading,
                content=(f"<!-- page:{draft.page_number} -->\n{draft.content}"
                         if draft.page_number is not None else draft.content),
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
                    "drive_file_id": file_id,
                    "file_name": local_source.name,
                    "chunk_index": draft.index,
                },
            )
        existing = await context.db.scalar(
            select(DriveFileIndex).where(
                DriveFileIndex.user_id == context.user.id,
                DriveFileIndex.drive_file_id == file_id,
            )
        )
        if existing:
            existing.name = local_source.name
            existing.content_hash = content_hash
            existing.chunk_count = len(drafts)
            existing.indexed_at = datetime.now(UTC)
        else:
            context.db.add(
                DriveFileIndex(
                    user_id=context.user.id,
                    drive_file_id=file_id,
                    name=local_source.name,
                    mime_type="text/markdown",
                    web_view_link=web_link,
                    modified_time=datetime.now(UTC).isoformat(),
                    content_hash=content_hash,
                    chunk_count=len(drafts),
                )
            )
        await context.db.commit()
        return len(drafts)

    async def search(
        self, payload: SearchKnowledgeInput, context: ToolContext
    ) -> RagSearchResponse:
        # Only retrieve chunks whose parent index was produced by the active
        # extraction/chunking/embedding contract.  Keeping old rows is useful
        # for an interrupted re-index, but serving them would leak stale parser
        # artefacts (including the legacy PDF asset manifest) into answers.
        version_prefix = f"{_index_version_tag(context.settings)}:%"
        statement = (
            select(DocumentChunk)
            .join(
                DriveFileIndex,
                (DriveFileIndex.user_id == DocumentChunk.user_id)
                & (DriveFileIndex.drive_file_id == DocumentChunk.drive_file_id),
            )
            .where(
                DocumentChunk.user_id == context.user.id,
                DriveFileIndex.content_hash.like(version_prefix),
            )
        )
        if payload.file_ids:
            statement = statement.where(DocumentChunk.drive_file_id.in_(payload.file_ids))
        chunks = list((await context.db.scalars(statement)).all())
        if not chunks:
            return RagSearchResponse(query=payload.query, citations=[])

        async with self._embedding_for(context) as embeddings:
            query_vector = await embeddings.embed(payload.query, EmbeddingTask.QUERY)
        # SQLite is the durable source already loaded for lexical retrieval.
        # A nonempty Qdrant response can still come from a partial/stale index.
        # Score this authorized SQL snapshot to preserve semantic recall even
        # after an interrupted dual-store write. Never fuse unknown point IDs.
        if is_postgres_session(context.db):
            dense_rank = await rank_vectors(
                context.db, table="document_chunks", owner=context.user.id,
                vector=query_vector, limit=max(payload.limit * 3, 12),
                file_ids=payload.file_ids, version_prefix=version_prefix,
            )
        else:
            dense_rank = sorted(
                (
                    (chunk.id, cosine_similarity(query_vector, json.loads(chunk.embedding_json)))
                    for chunk in chunks
                ),
                key=lambda item: (-item[1], item[0]),
            )[: max(payload.limit * 3, 12)]

        # Query expansion: original + entity terms
        expanded_queries = [payload.query]
        terms = tokenize(payload.query)
        if len(terms) > 3:
            expanded_queries.append(" ".join(terms[:8]))

        lexical_rankings = [
            self._lexical_rank(q, chunks)[: max(payload.limit * 3, 12)]
            for q in expanded_queries
        ]
        # Reciprocal Rank Fusion không phụ thuộc thang điểm của dense và lexical.
        fused: dict[str, float] = Counter()
        for rank, (chunk_id, _score) in enumerate(dense_rank, start=1):
            fused[chunk_id] += 1.0 / (60 + rank)
        for ranking in lexical_rankings:
            for rank, (chunk_id, _score) in enumerate(ranking, start=1):
                fused[chunk_id] += 1.0 / (60 + rank)

        # Boost table chunks if query asks for data/tables/numbers
        data_terms = [
            "bảng", "số liệu", "dự báo", "lnst", "doanh thu", "lợi nhuận",
            "%", "tỷ", "q1", "q2", "q3", "q4", "2026", "2025",
        ]
        is_data_query = any(term in payload.query.lower() for term in data_terms)
        if is_data_query:
            for chunk in chunks:
                if "|" in chunk.content:
                    fused[chunk.id] *= 1.35

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
                    page_number=(
                        int(page_match.group(1))
                        if (page_match := re.search(r"<!--\s*page:(\d+)\s*-->", chunk.content))
                        else None
                    ),
                    # Tool result cần đủ ngữ cảnh để model không bị cắt giữa danh sách/ý.
                    # UI chỉ hiện link nguồn nên tăng excerpt không làm nặng phần hiển thị.
                    snippet=chunk.content[:2_500],
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


def same_drive_revision(left: str | None, right: str | None) -> bool:
    """Compare Drive timestamps by instant, not by provider string formatting."""

    if not left or not right:
        return False
    values: list[datetime] = []
    for value in (left, right):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return left == right
        values.append(
            parsed.replace(tzinfo=UTC)
            if parsed.tzinfo is None
            else parsed.astimezone(UTC)
        )
    return values[0] == values[1]


async def retain_fresh_citations(
    result: RagSearchResponse,
    context: ToolContext,
    registry: ToolRegistry,
) -> RagSearchResponse:
    """Remove evidence that can no longer be authorized or version-verified.

    Retrieval can return chunks from several files. One stale file must not make
    an otherwise valid answer unavailable, but its cached text must never leave
    the tool boundary. Provider/network failures still propagate because the
    server cannot safely distinguish a temporary outage from revoked access.
    """

    if not result.citations:
        return result

    fresh_file_ids: set[str] = set()
    rejected_file_ids: set[str] = set()
    for file_id in dict.fromkeys(citation.file_id for citation in result.citations):
        # Local sources use a durable `local:<uuid>` namespace and never exist
        # in Google Drive. Verify their current DB content/hash directly; a
        # Drive metadata call here turns an otherwise valid mixed-source search
        # into a misleading Google 404.
        if file_id.startswith("local:"):
            local_id = file_id.removeprefix("local:").strip()
            local_source = await context.db.scalar(
                select(LocalSource).where(
                    LocalSource.user_id == context.user.id,
                    LocalSource.id == local_id,
                )
            )
            indexed = await context.db.scalar(
                select(DriveFileIndex).where(
                    DriveFileIndex.user_id == context.user.id,
                    DriveFileIndex.drive_file_id == file_id,
                )
            )
            if (
                local_source is not None
                and not excluded_ocr_source(local_source, context.settings)
                and indexed is not None
                and is_current_index_hash(indexed.content_hash, context.settings)
                and indexed.content_hash
                == index_fingerprint(local_source.content, context.settings)
            ):
                fresh_file_ids.add(file_id)
            else:
                rejected_file_ids.add(file_id)
            continue
        try:
            current = await registry.execute(
                "drive_file_metadata", {"file_id": file_id}, context
            )
        except ToolError as exc:
            if exc.code == "source_unavailable":
                rejected_file_ids.add(file_id)
                continue
            raise
        indexed = await context.db.scalar(
            select(DriveFileIndex).where(
                DriveFileIndex.user_id == context.user.id,
                DriveFileIndex.drive_file_id == file_id,
            )
        )
        if (
            indexed is not None
            and is_current_index_hash(indexed.content_hash, context.settings)
            and indexed.modified_time
            and same_drive_revision(indexed.modified_time, current.modified_time)
        ):
            fresh_file_ids.add(file_id)
        else:
            rejected_file_ids.add(file_id)

    citations = [
        citation for citation in result.citations if citation.file_id in fresh_file_ids
    ]
    if not citations and rejected_file_ids:
        raise ToolError(
            "Tài liệu đã thay đổi hoặc thiếu phiên bản. "
            "Hãy chuẩn bị lại tài liệu để hỏi đáp trước khi dùng RAG.",
            code="stale_index",
        )
    return result.model_copy(update={"citations": citations})


def rag_tool_definitions(service: RagService, registry: ToolRegistry) -> list[ToolDefinition]:
    async def index_handler(
        payload: IndexDriveFileInput, context: ToolContext
    ) -> IndexFileResponse:
        return await service.index_file(payload, context, registry)

    async def unindex_handler(
        payload: UnindexDriveFileInput, context: ToolContext
    ) -> UnindexFileResponse:
        return await service.unindex_file(payload, context)

    async def search_handler(
        payload: SearchKnowledgeInput, context: ToolContext
    ) -> RagSearchResponse:
        result = await service.search(payload, context)
        # Cached snippets are not an entitlement: verify access and revision online
        # before any text leaves this handler. Offline/revoked/stale => fail closed.
        return await retain_fresh_citations(result, context, registry)

    return [
        ToolDefinition(
            name="rag_index_drive_file",
            requires_user_action=True,
            description="Đọc một tệp Drive và lập chỉ mục RAG bền vững cho người dùng hiện tại.",
            input_model=IndexDriveFileInput,
            output_model=IndexFileResponse,
            handler=index_handler,
            required_permissions={RAG_WRITE},
            rate_limit_per_minute=15,
            max_attempts=1,
            timeout_seconds=300,
        ),
        ToolDefinition(
            name="rag_unindex_drive_file",
            requires_user_action=True,
            description=(
                "Hoàn tác lập chỉ mục của một tệp Drive trong kho hỏi đáp "
                "của người dùng hiện tại."
            ),
            input_model=UnindexDriveFileInput,
            output_model=UnindexFileResponse,
            handler=unindex_handler,
            required_permissions={RAG_WRITE},
            rate_limit_per_minute=30,
            max_attempts=1,
            timeout_seconds=60,
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
