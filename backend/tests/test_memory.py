from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import Base, User, UserRole
from app.services.embeddings import EmbeddingService
from app.services.memory import MemoryService, SaveMemoryInput, SearchMemoryInput
from app.services.vector_store import VectorStore
from app.tools.contracts import ToolContext, ToolError


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
    assert [point_id for point_id, _score in hits] == [
        "7cc7bb17-ef96-4c72-b211-1276c6b88673"
    ]
    await vectors.close()
