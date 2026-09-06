from types import SimpleNamespace

from app.core.config import Settings
from app.services.embeddings import EMBEDDING_DIMENSION, EmbeddingService, EmbeddingTask


def test_embedding_2_uses_google_prefix_and_omits_unsupported_task_type() -> None:
    seen = {}

    def embed_content(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=[0.25] * EMBEDDING_DIMENSION)]
        )

    service = EmbeddingService(Settings(_env_file=None, gemini_api_key="test-key"))
    service._client = SimpleNamespace(models=SimpleNamespace(embed_content=embed_content))

    vector = service._embed_sync("Mã DA-LOCAL-2026", EmbeddingTask.QUERY)

    assert seen["model"] == "gemini-embedding-2"
    assert seen["contents"] == "task: search result | query: Mã DA-LOCAL-2026"
    assert seen["config"].output_dimensionality == EMBEDDING_DIMENSION
    assert seen["config"].task_type is None
    assert len(vector) == EMBEDDING_DIMENSION


def test_embedding_2_uses_document_prefix() -> None:
    seen = {}

    def embed_content(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0, 0.0])])

    service = EmbeddingService(Settings(_env_file=None, gemini_api_key="test-key"))
    service._client = SimpleNamespace(models=SimpleNamespace(embed_content=embed_content))

    service._embed_sync("Nội dung", EmbeddingTask.DOCUMENT)

    assert seen["contents"] == "title: none | text: Nội dung"
