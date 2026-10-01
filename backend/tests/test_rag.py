import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.schemas import Citation, DriveFileResponse, FileContentResponse, RagSearchResponse
from app.core.config import Settings
from app.db.models import Base, DocumentChunk, DriveFileIndex, LocalSource, User, UserRole
from app.services.embeddings import EmbeddingService
from app.services.local_sources import hash_content
from app.services.rag import (
    INDEX_PIPELINE_VERSION,
    IndexDriveFileInput,
    RagService,
    SearchKnowledgeInput,
    UnindexDriveFileInput,
    index_fingerprint,
    is_current_index_hash,
    retain_fresh_citations,
    same_drive_revision,
)
from app.services.vector_recovery import reconcile_document_vectors
from app.services.vector_store import VectorStore
from app.tools.contracts import ToolContext, ToolError


@pytest.mark.asyncio
async def test_local_pdf_index_keeps_page_citation(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'local-pages.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(_env_file=None, gemini_api_key="", qdrant_path=str(tmp_path / "vectors"))
    embeddings, vectors = EmbeddingService(settings), VectorStore(settings)
    service = RagService(embeddings, vectors)
    try:
        async with factory() as db:
            user = User(email="pages@example.test", display_name="Pages", role="editor")
            db.add(user)
            await db.flush()
            text = "<!-- page:3 -->\nChi phí 200.\n<!-- page:7 -->\nDoanh thu quý một 125 tỷ."
            source = LocalSource(user_id=user.id, name="pages.pdf", content=text,
                                 content_hash=hash_content(text))
            db.add(source)
            await db.commit()
            context = ToolContext(request_id="local-pages", user=user, db=db, settings=settings)
            assert await service.index_local_source(source, context) == 2
            result = await service.search(
                SearchKnowledgeInput(query="Doanh thu quý một", limit=1), context)
            assert result.citations[0].page_number == 7
            assert "125 tỷ" in result.citations[0].snippet
            chunks = list(await db.scalars(select(DocumentChunk)))
            assert {chunk.content.splitlines()[0] for chunk in chunks} == {
                "<!-- page:3 -->", "<!-- page:7 -->"}
    finally:
        await embeddings.close()
        await vectors.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_embedding_client_is_scoped_and_closed_on_failure(monkeypatch):
    owner = Settings(_env_file=None, gemini_api_key="owner-key")
    visitor = owner.model_copy(update={"gemini_api_key": "visitor-key"})
    shared = SimpleNamespace(settings=owner, close=AsyncMock())
    created = []

    def make(settings):
        client = SimpleNamespace(settings=settings, close=AsyncMock())
        created.append(client)
        return client

    monkeypatch.setattr("app.services.embeddings.EmbeddingService", make)
    service = RagService(shared, None)
    with pytest.raises(RuntimeError):
        async with service._embedding_for(SimpleNamespace(settings=visitor)) as client:
            assert client.settings.gemini_api_key == "visitor-key"
            raise RuntimeError("provider failed")
    created[0].close.assert_awaited_once()
    shared.close.assert_not_awaited()
    async with service._embedding_for(SimpleNamespace(settings=owner)) as client:
        assert client is shared
    assert owner.gemini_api_key == "owner-key"


def test_drive_revision_comparison_ignores_provider_timestamp_formatting() -> None:
    assert same_drive_revision("2026-09-11T10:00:00Z", "2026-09-11T17:00:00+07:00")
    assert not same_drive_revision("2026-09-11T10:00:00Z", "2026-09-11T10:00:01Z")
    assert not same_drive_revision(None, "2026-09-11T10:00:00Z")


def test_index_fingerprint_is_versioned_and_fixed_width() -> None:
    settings = Settings(gemini_api_key="")
    fingerprint = index_fingerprint("same content", settings)

    assert len(fingerprint) == 64
    assert is_current_index_hash(fingerprint, settings)
    assert not is_current_index_hash(hashlib.sha256(b"same content").hexdigest(), settings)
    changed_model = settings.model_copy(update={"gemini_embedding_model": "other-model"})
    assert not is_current_index_hash(fingerprint, changed_model)
    assert INDEX_PIPELINE_VERSION


def test_hashing_vectors_are_never_claimed_as_gemini_semantics():
    offline = Settings(_env_file=None, gemini_api_key="")
    online = offline.model_copy(update={"gemini_api_key": "own-key"})
    fingerprint = index_fingerprint("same source", offline)
    assert not is_current_index_hash(fingerprint, online)
    second_key = online.model_copy(update={"gemini_api_key": "other-own-key"})
    assert index_fingerprint("same source", online) == index_fingerprint("same source", second_key)


class FakeDriveRegistry:
    """Thay Google API bằng nội dung cố định; RagService vẫn chạy toàn bộ ingestion."""

    async def execute(self, _name, arguments, _context):  # type: ignore[no-untyped-def]
        return FileContentResponse(
            file=DriveFileResponse(
                id=arguments["file_id"],
                name="ke-hoach-quy.md",
                mime_type="text/markdown",
                web_view_link="https://drive.google.com/file/d/file-rag/view",
            ),
            text=(
                "# Kế hoạch quý\n\n"
                "Mục tiêu trọng tâm là hoàn thiện tìm kiếm tài liệu và trích dẫn nguồn. "
                "Nhóm sẽ đo độ chính xác retrieval trước khi mở rộng tính năng."
            ),
        )


class FakePagedPdfRegistry:
    async def execute(self, _name, arguments, _context):  # type: ignore[no-untyped-def]
        return FileContentResponse(
            file=DriveFileResponse(
                id=arguments["file_id"],
                name="bao-cao.pdf",
                mime_type="application/pdf",
                web_view_link="https://drive.google.com/file/d/paged/view",
            ),
            text=(
                "<!-- page:4 -->\n\n"
                "Doanh thu quý một là 125 tỷ đồng.\n\n"
                "<!-- page:5 -->\n\n"
                "Rủi ro trọng yếu là phụ thuộc một nhà cung cấp."
            ),
        )


class FakeMetadataRegistry:
    def __init__(self, revisions: dict[str, str | ToolError]):
        self.revisions = revisions

    async def execute(self, _name, arguments, _context):  # type: ignore[no-untyped-def]
        value = self.revisions[arguments["file_id"]]
        if isinstance(value, ToolError):
            raise value
        return DriveFileResponse(
            id=arguments["file_id"],
            name=f'{arguments["file_id"]}.md',
            mime_type="text/markdown",
            modified_time=value,
        )


@pytest.mark.asyncio
async def test_rag_verification_drops_stale_sources_without_blocking_fresh_evidence(
    tmp_path: Path,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'freshness.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email="fresh@example.com", display_name="Fresh", role="editor")
        db.add(user)
        await db.commit()
        settings = Settings(gemini_api_key="")
        db.add_all(
            [
                DriveFileIndex(
                    user_id=user.id,
                    drive_file_id="stale-file",
                    name="stale.md",
                    mime_type="text/markdown",
                    modified_time="2026-09-11T10:00:00Z",
                    content_hash=index_fingerprint("old", settings),
                    chunk_count=1,
                ),
                DriveFileIndex(
                    user_id=user.id,
                    drive_file_id="fresh-file",
                    name="fresh.md",
                    mime_type="text/markdown",
                    modified_time="2026-09-12T10:00:00Z",
                    content_hash=index_fingerprint("DA-CREATE-2026", settings),
                    chunk_count=1,
                ),
            ]
        )
        await db.commit()
        context = ToolContext(
            request_id="freshness", user=user, db=db, settings=settings
        )
        result = RagSearchResponse(
            query="mã kiểm thử",
            citations=[
                Citation(
                    file_id="stale-file",
                    file_name="stale.md",
                    chunk_index=0,
                    snippet="old",
                    score=0.9,
                ),
                Citation(
                    file_id="fresh-file",
                    file_name="fresh.md",
                    chunk_index=0,
                    snippet="DA-CREATE-2026",
                    score=0.8,
                ),
            ],
        )
        registry = FakeMetadataRegistry(
            {
                "stale-file": "2026-09-12T10:00:00Z",
                "fresh-file": "2026-09-12T10:00:00Z",
            }
        )

        verified = await retain_fresh_citations(
            result, context, registry  # type: ignore[arg-type]
        )

        assert [citation.file_id for citation in verified.citations] == ["fresh-file"]
        with pytest.raises(ToolError, match="thay đổi hoặc thiếu phiên bản") as caught:
            await retain_fresh_citations(
                result.model_copy(update={"citations": result.citations[:1]}),
                context,
                registry,  # type: ignore[arg-type]
            )
        assert caught.value.code == "stale_index"
    await engine.dispose()


@pytest.mark.asyncio
async def test_rag_verification_keeps_fresh_local_citations_without_drive_metadata_call(
    tmp_path: Path,
) -> None:
    """Local IDs must be verified in SQLite, not sent to the Drive API."""

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'local-freshness.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(gemini_api_key="")
    local_text = "Mã local DA-LOCAL-2026 và ngày họp là thứ Sáu."

    async with factory() as db:
        user = User(email="local-fresh@example.com", display_name="Local Fresh", role="editor")
        db.add(user)
        await db.flush()
        local = LocalSource(
            user_id=user.id,
            name="qa-local.md",
            content=local_text,
            content_hash=hash_content(local_text),
        )
        db.add(local)
        await db.flush()
        local_id = f"local:{local.id}"
        db.add_all(
            [
                DriveFileIndex(
                    user_id=user.id,
                    drive_file_id=local_id,
                    name=local.name,
                    mime_type="text/markdown",
                    modified_time="2026-09-17T10:00:00Z",
                    content_hash=index_fingerprint(local_text, settings),
                    chunk_count=1,
                ),
                DriveFileIndex(
                    user_id=user.id,
                    drive_file_id="drive-fresh",
                    name="drive.md",
                    mime_type="text/markdown",
                    modified_time="2026-09-17T10:00:00Z",
                    content_hash=index_fingerprint("drive content", settings),
                    chunk_count=1,
                ),
            ]
        )
        await db.commit()
        context = ToolContext(request_id="local-freshness", user=user, db=db, settings=settings)
        verified = await retain_fresh_citations(
            RagSearchResponse(
                query="mã kiểm thử",
                citations=[
                    Citation(
                        file_id=local_id,
                        file_name=local.name,
                        chunk_index=0,
                        snippet=local_text,
                        score=0.9,
                    ),
                    Citation(
                        file_id="drive-fresh",
                        file_name="drive.md",
                        chunk_index=0,
                        snippet="drive",
                        score=0.8,
                    ),
                ],
            ),
            context,
            FakeMetadataRegistry({"drive-fresh": "2026-09-17T10:00:00Z"}),
        )

        assert [citation.file_id for citation in verified.citations] == [local_id, "drive-fresh"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_rag_index_is_idempotent_and_search_is_user_scoped(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'rag.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(gemini_api_key="", qdrant_path=str(tmp_path / "qdrant"))
    service = RagService(EmbeddingService(settings), VectorStore(settings))
    registry = FakeDriveRegistry()

    async with factory() as db:
        first = User(email="rag-a@example.com", display_name="RAG A", role=UserRole.EDITOR.value)
        second = User(email="rag-b@example.com", display_name="RAG B", role=UserRole.EDITOR.value)
        db.add_all([first, second])
        await db.commit()
        first_context = ToolContext(request_id="rag-1", user=first, db=db, settings=settings)

        indexed = await service.index_file(
            IndexDriveFileInput(file_id="file-rag"),
            first_context,
            registry,  # type: ignore[arg-type]
        )
        repeated = await service.index_file(
            IndexDriveFileInput(file_id="file-rag"),
            first_context,
            registry,  # type: ignore[arg-type]
        )
        found = await service.search(
            SearchKnowledgeInput(query="độ chính xác tìm kiếm", limit=3), first_context
        )
        second_context = ToolContext(request_id="rag-2", user=second, db=db, settings=settings)
        isolated = await service.search(
            SearchKnowledgeInput(query="độ chính xác tìm kiếm", limit=3), second_context
        )

        assert indexed.skipped is False
        assert indexed.chunks >= 1
        assert repeated.skipped is True
        assert found.citations[0].file_id == "file-rag"
        assert "retrieval" in found.citations[0].snippet
        assert isolated.citations == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_rag_unindex_removes_only_current_users_file_and_search_evidence(
    tmp_path: Path,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'unindex.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(gemini_api_key="", qdrant_path=str(tmp_path / "unindex-vectors"))
    service = RagService(EmbeddingService(settings), VectorStore(settings))
    registry = FakeDriveRegistry()
    async with factory() as db:
        user = User(email="unindex@example.com", display_name="Unindex", role="editor")
        db.add(user)
        await db.commit()
        context = ToolContext(request_id="unindex", user=user, db=db, settings=settings)
        await service.index_file(IndexDriveFileInput(file_id="file-rag"), context, registry)
        removed = await service.unindex_file(UnindexDriveFileInput(file_id="file-rag"), context)
        assert removed.chunks_removed >= 1
        index_row = await db.scalar(
            select(DriveFileIndex).where(DriveFileIndex.drive_file_id == "file-rag")
        )
        assert index_row is None
        chunks = await db.scalars(
            select(DocumentChunk).where(DocumentChunk.drive_file_id == "file-rag")
        )
        assert chunks.all() == []
        search = await service.search(SearchKnowledgeInput(query="retrieval"), context)
        assert search.citations == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_search_never_serves_chunks_from_an_obsolete_pipeline(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'stale-pipeline.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(gemini_api_key="", qdrant_path=str(tmp_path / "stale-vectors"))
    service = RagService(EmbeddingService(settings), VectorStore(settings))
    async with factory() as db:
        user = User(email="stale@example.com", display_name="Stale", role="editor")
        db.add(user)
        await db.commit()
        context = ToolContext(request_id="stale", user=user, db=db, settings=settings)
        await service.index_file(
            IndexDriveFileInput(file_id="file-rag"), context, FakeDriveRegistry()
        )
        index = await db.scalar(
            select(DriveFileIndex).where(DriveFileIndex.drive_file_id == "file-rag")
        )
        assert index is not None
        index.content_hash = "legacy:" + "0" * 57
        await db.commit()

        result = await service.search(SearchKnowledgeInput(query="retrieval"), context)
        assert result.citations == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_pdf_rag_citation_exposes_verified_page_number(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'paged.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(gemini_api_key="", qdrant_path=str(tmp_path / "paged-vectors"))
    service = RagService(EmbeddingService(settings), VectorStore(settings))
    async with factory() as db:
        user = User(email="paged@example.com", display_name="Paged", role="editor")
        db.add(user)
        await db.commit()
        context = ToolContext(request_id="paged", user=user, db=db, settings=settings)
        await service.index_file(
            IndexDriveFileInput(file_id="paged-pdf"),
            context,
            FakePagedPdfRegistry(),  # type: ignore[arg-type]
        )
        result = await service.search(
            SearchKnowledgeInput(query="doanh thu quý một", limit=1), context
        )

        assert result.citations[0].page_number == 4
        assert "125 tỷ" in result.citations[0].snippet
    await engine.dispose()


@pytest.mark.asyncio
async def test_partial_vector_index_preserves_recall_and_is_repaired(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'partial.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(gemini_api_key="", qdrant_path=str(tmp_path / "vectors"))
    store = VectorStore(settings)
    await store.initialize()
    embeddings = EmbeddingService(settings)
    service = RagService(embeddings, store)
    try:
        async with factory() as db:
            user = User(email="partial@example.com", display_name="Test", role="editor")
            db.add(user)
            await db.commit()
            context = ToolContext(request_id="partial", user=user, db=db, settings=settings)
            for file_id in ("file-one", "file-two"):
                await service.index_file(IndexDriveFileInput(file_id=file_id), context,
                                         FakeDriveRegistry())
            query = SearchKnowledgeInput(query="độ chính xác retrieval", limit=20)
            expected = await service.search(query, context)
            points, _ = store.client.scroll("drive_chunks", limit=100)
            assert len(points) >= 2
            await store.delete_points("drive_chunks", [str(points[0].id)])
            assert store.client.count("drive_chunks", exact=True).count > 0
            actual = await service.search(query, context)
            assert actual.model_dump() == expected.model_dump()
            assert await reconcile_document_vectors(db, store) == len(points)
            assert store.client.count("drive_chunks", exact=True).count == len(points)
            assert await reconcile_document_vectors(db, store) == len(points)
            assert store.client.count("drive_chunks", exact=True).count == len(points)
    finally:
        await embeddings.close()
        await store.close()
        await engine.dispose()
