from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.schemas import Citation, RagSearchResponse
from app.core.config import Settings
from app.services.rag import SearchKnowledgeInput, index_fingerprint, rag_tool_definitions
from app.tools.contracts import ToolError


@pytest.mark.parametrize("mode", ["fresh", "stale", "missing", "revoked"])
async def test_cached_rag_requires_current_access_and_revision(mode):
    result = RagSearchResponse(
        query="test",
        citations=[
            Citation(file_id="file1", file_name="Test", chunk_index=0, snippet="PRIVATE", score=1.0)
        ],
    )
    service = SimpleNamespace(search=AsyncMock(return_value=result))
    registry = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(modified_time="now")))
    if mode == "revoked":
        registry.execute.side_effect = ToolError("Access revoked", code="google_drive_403")
    settings = Settings(gemini_api_key="")
    indexed = (
        None
        if mode == "missing"
        else SimpleNamespace(
            modified_time="old" if mode == "stale" else "now",
            content_hash=index_fingerprint("PRIVATE", settings),
        )
    )
    context = SimpleNamespace(
        user=SimpleNamespace(id="user-a"),
        db=SimpleNamespace(scalar=AsyncMock(return_value=indexed)),
        settings=settings,
    )
    handler = next(
        d.handler for d in rag_tool_definitions(service, registry) if d.name == "rag_search"
    )
    if mode == "fresh":
        assert (await handler(SearchKnowledgeInput(query="test"), context)).citations
    else:
        with pytest.raises(ToolError):
            await handler(SearchKnowledgeInput(query="test"), context)
    registry.execute.assert_awaited_once_with("drive_file_metadata", {"file_id": "file1"}, context)
