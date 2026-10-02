from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import memory as memory_api
from app.api.schemas import MemoryUpdateRequest
from app.core.config import Settings
from app.db.models import Base, ChatSession, User, UserRole
from app.services.embeddings import EmbeddingService
from app.services.memory import MemoryService, SaveMemoryInput, SearchMemoryInput
from app.services.vector_store import VectorStore
from app.tools.contracts import ToolContext, ToolError


class SameVectorEmbeddings:
    """Simulate a dense model that over-scores every candidate equally."""

    def __init__(self, settings):
        self.settings = settings

    async def embed(self, _text, _task):
        return [1.0] + [0.0] * 767


@pytest.mark.asyncio
async def test_memory_source_session_requires_owner(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'source.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    settings = Settings(
        _env_file=None, gemini_api_key="", qdrant_path=str(tmp_path / "source-vectors")
    )
    vectors = VectorStore(settings)
    service = MemoryService(SameVectorEmbeddings(settings), vectors)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        owner = User(email="source-owner@example.com", display_name="Owner")
        other = User(email="source-other@example.com", display_name="Other")
        db.add_all([owner, other])
        await db.flush()
        own_session = ChatSession(user_id=owner.id)
        other_session = ChatSession(user_id=other.id)
        db.add_all([own_session, other_session])
        await db.commit()
        context = ToolContext(request_id="memory-source", user=owner, db=db, settings=settings)
        for source_id in (other_session.id, "missing-session"):
            with pytest.raises(ToolError) as denied:
                await service.save(
                    SaveMemoryInput(
                        kind="fact", content="Bối cảnh khách hàng", source_session_id=source_id
                    ),
                    context,
                )
            assert denied.value.code == "memory_source_not_found"
        saved = await service.save(
            SaveMemoryInput(
                kind="fact", content="Bối cảnh khách hàng", source_session_id=own_session.id
            ),
            context,
        )
        assert saved.content == "Bối cảnh khách hàng"
        # A matching saved value must not bypass provenance ownership checks.
        with pytest.raises(ToolError) as duplicate_denied:
            await service.save(
                SaveMemoryInput(
                    kind="fact",
                    content="Bối cảnh khách hàng",
                    source_session_id=other_session.id,
                ),
                context,
            )
        assert duplicate_denied.value.code == "memory_source_not_found"
    await vectors.close()
    await engine.dispose()


@pytest.mark.asyncio
async def test_memory_edit_archive_restart_delete_and_cross_owner(tmp_path, monkeypatch):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'lifecycle.db'}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(_env_file=None, gemini_api_key="", qdrant_path=str(tmp_path / "vectors"))
    vectors = VectorStore(settings)
    await vectors.initialize()
    embeddings = SameVectorEmbeddings(settings)
    service = MemoryService(embeddings, vectors)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                embeddings=embeddings,
                vector_store=vectors,
            )
        )
    )
    monkeypatch.setattr(memory_api, "user_runtime_settings", AsyncMock(return_value=settings))
    async with factory() as db:
        owner = User(email="owner@example.com", display_name="Owner", role=UserRole.EDITOR.value)
        other = User(email="other@example.com", display_name="Other", role=UserRole.EDITOR.value)
        db.add_all([owner, other])
        await db.commit()
        context = ToolContext(request_id="memory-lifecycle", user=owner, db=db, settings=settings)
        saved = await service.save(
            SaveMemoryInput(kind="preference", content="Báo cáo ngắn gọn"), context
        )
        for action in ("edit", "delete"):
            with pytest.raises(HTTPException) as denied:
                if action == "edit":
                    await memory_api.update_memory(
                        saved.id, MemoryUpdateRequest(content="Nội dung khác"), request, other, db
                    )
                else:
                    await memory_api.delete_memory(saved.id, request, other, db)
            assert denied.value.status_code == 404
        updated = await memory_api.update_memory(
            saved.id, MemoryUpdateRequest(content="Báo cáo chi tiết"), request, owner, db
        )
        assert updated.content == "Báo cáo chi tiết"
        assert not (await service.search(SearchMemoryInput(query="ngắn gọn"), context)).memories
        assert (await service.search(SearchMemoryInput(query="chi tiết"), context)).memories[
            0
        ].id == saved.id
        await memory_api.update_memory(
            saved.id, MemoryUpdateRequest(is_archived=True), request, owner, db
        )
        assert not (await service.search(SearchMemoryInput(query="chi tiết"), context)).memories
        owner_id, saved_id = owner.id, saved.id
    await vectors.close()
    await engine.dispose()

    reopened = create_async_engine(database_url)
    vectors = VectorStore(settings)
    await vectors.initialize()
    request.app.state.vector_store = vectors
    service = MemoryService(embeddings, vectors)
    async with async_sessionmaker(reopened, expire_on_commit=False)() as db:
        owner = await db.get(User, owner_id)
        context = ToolContext(request_id="memory-reopened", user=owner, db=db, settings=settings)
        assert not (await service.search(SearchMemoryInput(query="chi tiết"), context)).memories
        await memory_api.update_memory(
            saved_id, MemoryUpdateRequest(is_archived=False), request, owner, db
        )
        assert (await service.search(SearchMemoryInput(query="chi tiết"), context)).memories[
            0
        ].id == saved_id
        await memory_api.delete_memory(saved_id, request, owner, db)
        assert not (await service.search(SearchMemoryInput(query="chi tiết"), context)).memories
        assert not (
            await memory_api.list_memories(user=owner, db=db, include_archived=True)
        ).memories
    await vectors.close()
    await reopened.dispose()


@pytest.mark.asyncio
async def test_memory_deduplicates_and_isolates_users(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(gemini_api_key="", qdrant_path=str(tmp_path / "qdrant"))
    vectors = VectorStore(settings)
    service = MemoryService(EmbeddingService(settings), vectors)

    async with factory() as db:
        first = User(email="first@example.com", display_name="First", role=UserRole.EDITOR.value)
        second = User(email="second@example.com", display_name="Second", role=UserRole.EDITOR.value)
        db.add_all([first, second])
        await db.commit()
        first_context = ToolContext(request_id="m1", user=first, db=db, settings=settings)
        original = await service.save(
            SaveMemoryInput(kind="preference", content="Tôi thích câu trả lời ngắn", tags=["ui"]),
            first_context,
        )
        duplicate = await service.save(
            SaveMemoryInput(kind="preference", content="  tôi thích câu trả lời ngắn  "),
            first_context,
        )
        assert original.id == duplicate.id

        second_context = ToolContext(request_id="m2", user=second, db=db, settings=settings)
        result = await service.search(SearchMemoryInput(query="câu trả lời ngắn"), second_context)
        assert result.memories == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_memory_search_returns_empty_instead_of_unrelated_top_k(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'no-match.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(gemini_api_key="", qdrant_path=str(tmp_path / "qdrant-no-match"))
    service = MemoryService(SameVectorEmbeddings(settings), VectorStore(settings))

    async with factory() as db:
        user = User(email="memory@example.com", display_name="Memory", role=UserRole.EDITOR.value)
        db.add(user)
        await db.commit()
        context = ToolContext(request_id="m-no-match", user=user, db=db, settings=settings)
        await service.save(
            SaveMemoryInput(
                kind="preference",
                content="Tôi thích câu trả lời kỹ thuật ngắn gọn có nguồn trích dẫn",
            ),
            context,
        )

        matching = await service.search(
            SearchMemoryInput(query="câu trả lời kỹ thuật ngắn gọn"), context
        )
        unrelated = await service.search(
            SearchMemoryInput(query="DA-QA-NO-MATCH-20260909"), context
        )

        assert [item.content for item in matching.memories] == [
            "Tôi thích câu trả lời kỹ thuật ngắn gọn có nguồn trích dẫn"
        ]
        assert unrelated.memories == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_memory_rejects_secret_like_content(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'secret.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(gemini_api_key="")
    service = MemoryService(EmbeddingService(settings), VectorStore(settings))
    async with factory() as db:
        user = User(email="secure@example.com", display_name="Secure", role=UserRole.EDITOR.value)
        db.add(user)
        await db.commit()
        with pytest.raises(ToolError, match="secret"):
            await service.save(
                SaveMemoryInput(kind="fact", content="api_key là 123456"),
                ToolContext(request_id="m3", user=user, db=db, settings=settings),
            )
    await engine.dispose()


@pytest.mark.asyncio
async def test_memory_allows_security_guidance_without_a_secret(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'guidance.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(gemini_api_key="")
    service = MemoryService(EmbeddingService(settings), VectorStore(settings))
    async with factory() as db:
        user = User(email="guide@example.com", display_name="Guide", role=UserRole.EDITOR.value)
        db.add(user)
        await db.commit()
        saved = await service.save(
            SaveMemoryInput(kind="procedural", content="Không lưu API key trong bộ nhớ."),
            ToolContext(request_id="m4", user=user, db=db, settings=settings),
        )
        assert saved.content == "Không lưu API key trong bộ nhớ."
    await engine.dispose()


@pytest.mark.asyncio
async def test_qdrant_memory_search_is_filtered_by_user(tmp_path: Path) -> None:
    settings = Settings(gemini_api_key="", qdrant_path=str(tmp_path / "qdrant-filter"))
    vectors = VectorStore(settings)
    await vectors.initialize()
    assert vectors.backend_name == "qdrant-embedded"

    first = [1.0] + [0.0] * 767
    second = [0.99, 0.01] + [0.0] * 766
    await vectors.upsert(
        "agent_memories",
        "7cc7bb17-ef96-4c72-b211-1276c6b88673",
        first,
        {"user_id": "user-a", "kind": "fact"},
    )
    await vectors.upsert(
        "agent_memories",
        "3cbf7288-42f8-4f59-8a5f-4fb4c3507826",
        second,
        {"user_id": "user-b", "kind": "fact"},
    )
    hits = await vectors.search(
        "agent_memories", first, {"user_id": "user-a", "kind": ["fact"]}, 10
    )
    assert [point_id for point_id, _score in hits] == ["7cc7bb17-ef96-4c72-b211-1276c6b88673"]
    await vectors.close()
