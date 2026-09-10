from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.services.embeddings import EMBEDDING_DIMENSION, EmbeddingService, EmbeddingTask
from app.tools.contracts import ToolError


def test_embedding_2_uses_google_prefix_and_omits_unsupported_task_type(tmp_path) -> None:
    seen = {}

    def embed_content(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.25] * EMBEDDING_DIMENSION)])

    service = EmbeddingService(
        Settings(
            _env_file=None,
            gemini_api_key="test-key",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
        )
    )
    service._client = SimpleNamespace(models=SimpleNamespace(embed_content=embed_content))

    vector = service._embed_sync("Mã DA-LOCAL-2026", EmbeddingTask.QUERY)

    assert seen["model"] == "gemini-embedding-2"
    assert seen["contents"] == "task: search result | query: Mã DA-LOCAL-2026"
    assert seen["config"].output_dimensionality == EMBEDDING_DIMENSION
    assert seen["config"].task_type is None
    assert len(vector) == EMBEDDING_DIMENSION


def test_embedding_2_uses_document_prefix(tmp_path) -> None:
    seen = {}

    def embed_content(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0] * EMBEDDING_DIMENSION)])

    service = EmbeddingService(
        Settings(
            _env_file=None,
            gemini_api_key="test-key",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
        )
    )
    service._client = SimpleNamespace(models=SimpleNamespace(embed_content=embed_content))

    service._embed_sync("Nội dung", EmbeddingTask.DOCUMENT)

    assert seen["contents"] == "title: none | text: Nội dung"


async def test_chunks_are_batched_not_one_request_per_chunk(tmp_path):
    calls = []

    def embed_content(**kwargs):
        contents = kwargs["contents"]
        calls.append(contents)
        count = len(contents) if isinstance(contents, list) else 1
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=[0.1] * EMBEDDING_DIMENSION) for _ in range(count)]
        )

    service = EmbeddingService(
        Settings(
            _env_file=None,
            gemini_api_key="test-key",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
        )
    )
    service._client = SimpleNamespace(models=SimpleNamespace(embed_content=embed_content))
    assert len(await service.embed_many(["a"] * 33, EmbeddingTask.DOCUMENT)) == 33
    assert len(calls) == 2 and len(calls[0]) == 32


@pytest.mark.parametrize("vector", [[1.0], [float("nan")] * EMBEDDING_DIMENSION])
def test_invalid_vectors_rejected_before_index_write(tmp_path, vector):
    service = EmbeddingService(
        Settings(
            _env_file=None,
            gemini_api_key="test-key",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
        )
    )
    service._client = SimpleNamespace(
        models=SimpleNamespace(
            embed_content=lambda **kwargs: SimpleNamespace(
                embeddings=[SimpleNamespace(values=vector)]
            )
        )
    )
    with pytest.raises(ToolError) as failure:
        service._embed_sync("text", EmbeddingTask.DOCUMENT)
    assert failure.value.code == "invalid_embedding"
