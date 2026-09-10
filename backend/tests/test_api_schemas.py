import pytest
from pydantic import ValidationError

from app.api.schemas import MemoryUpdateRequest


@pytest.mark.parametrize("field", ["content", "tags", "confidence", "is_archived"])
def test_memory_patch_rejects_explicit_null(field: str) -> None:
    with pytest.raises(ValidationError):
        MemoryUpdateRequest.model_validate({field: None})


def test_memory_patch_preserves_omitted_fields_and_false_values() -> None:
    assert MemoryUpdateRequest().model_dump(exclude_unset=True) == {}
    assert MemoryUpdateRequest(confidence=0, is_archived=False, tags=[]).model_dump(
        exclude_unset=True
    ) == {"confidence": 0, "is_archived": False, "tags": []}
