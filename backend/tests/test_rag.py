from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.schemas import DriveFileResponse, FileContentResponse
from app.core.config import Settings
from app.db.models import Base, User, UserRole
from app.services.embeddings import EmbeddingService
from app.services.rag import IndexDriveFileInput, RagService, SearchKnowledgeInput
from app.services.vector_store import VectorStore
from app.tools.contracts import ToolContext


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
            IndexDriveFileInput(file_id="file-rag"), first_context, registry  # type: ignore[arg-type]
        )
        repeated = await service.index_file(
            IndexDriveFileInput(file_id="file-rag"), first_context, registry  # type: ignore[arg-type]
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
