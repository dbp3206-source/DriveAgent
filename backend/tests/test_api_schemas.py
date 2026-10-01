from datetime import datetime

import pytest
from pydantic import ValidationError

from app.api.schemas import HealthResponse, MemoryUpdateRequest, SessionResponse


@pytest.mark.parametrize("field", ["content", "tags", "confidence", "is_archived"])
def test_memory_patch_rejects_explicit_null(field: str) -> None:
    with pytest.raises(ValidationError):
        MemoryUpdateRequest.model_validate({field: None})


def test_memory_patch_preserves_omitted_fields_and_false_values() -> None:
    assert MemoryUpdateRequest().model_dump(exclude_unset=True) == {}
    assert MemoryUpdateRequest(confidence=0, is_archived=False, tags=[]).model_dump(
        exclude_unset=True
    ) == {"confidence": 0, "is_archived": False, "tags": []}


def test_health_contract_marks_external_providers_as_unprobed() -> None:
    response = HealthResponse(
        status="ok",
        database=True,
        gemini_configured=True,
        google_oauth_configured=True,
        vector_store="qdrant-embedded",
        gemini_chat_model="gemini-3.5-flash-lite",
        gemini_fallback_model="gemini-3.5-flash-lite",
        gemini_embedding_model="gemini-embedding-2",
        embedding_dimensions=768,
    )

    assert response.model_dump()["gemini_connectivity"] == "not_probed"
    assert response.model_dump()["google_workspace_connectivity"] == "not_probed"


def test_public_api_serializes_legacy_naive_datetimes_as_utc() -> None:
    response = SessionResponse(
        id="session",
        title="QA",
        summary=None,
        created_at=datetime(2026, 9, 14, 13, 0),
        updated_at=datetime(2026, 9, 14, 13, 5),
    )

    payload = response.model_dump(mode="json")
    assert payload["created_at"] == "2026-09-14T13:00:00Z"
    assert payload["updated_at"] == "2026-09-14T13:05:00Z"
