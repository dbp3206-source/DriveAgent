"""Embedding Gemini với fallback local có tính quyết định.

Fallback hashing không thay thế chất lượng semantic của Gemini. Nó tồn tại để app vẫn
khởi động, test và tìm lexical khi người dùng chưa nhập API key.
"""

import asyncio
import hashlib
import math
import re
from contextlib import asynccontextmanager
from enum import StrEnum

from google import genai
from google.genai import types

from app.core.config import Settings
from app.services.inference_gateway import create_inference_client
from app.services.quota import conservative_tokens
from app.services.relational_quota import quota_guard
from app.tools.contracts import ToolError

EMBEDDING_DIMENSION = 768
TOKEN_PATTERN = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)


@asynccontextmanager
async def scoped_embeddings(shared, settings: Settings):
    """Pin credentials/model without rotating a client another user is using."""
    original = shared.settings
    if (original.gemini_api_key == settings.gemini_api_key
            and original.gemini_embedding_model == settings.gemini_embedding_model):
        yield shared
        return
    client = EmbeddingService(settings)
    try:
        yield client
    finally:
        await client.close()


class EmbeddingTask(StrEnum):
    DOCUMENT = "RETRIEVAL_DOCUMENT"
    QUERY = "RETRIEVAL_QUERY"
    SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_PATTERN.findall(text)]


class EmbeddingService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client_lock = asyncio.Lock()
        self._client = (
            create_inference_client(
                settings=settings,
                api_key=settings.gemini_api_key,
                data_dir=settings.data_dir,
                client_factory=genai.Client,
                vertexai=False,
                http_options=types.HttpOptions(
                    base_url="https://generativelanguage.googleapis.com",
                    timeout=30_000,
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
            if settings.gemini_is_configured
            else None
        )

    @property
    def provider_name(self) -> str:
        return "gemini" if self._client else "local-hashing-fallback"

    async def close(self) -> None:
        async with self._client_lock:
            if self._client:
                await self._client.aio.aclose()
                self._client.close()
                self._client = None

    async def rotate_api_key(self, api_key: str) -> None:
        """Replace the embedding client without restarting or racing an active batch."""

        replacement = create_inference_client(
            settings=self.settings,
            api_key=api_key,
            data_dir=self.settings.data_dir,
            client_factory=genai.Client,
            vertexai=False,
            http_options=types.HttpOptions(
                base_url="https://generativelanguage.googleapis.com",
                timeout=30_000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        async with self._client_lock:
            previous = self._client
            self._client = replacement
            if previous:
                await previous.aio.aclose()
                previous.close()

    async def embed(self, text: str, task: EmbeddingTask) -> list[float]:
        if not self._client:
            return self._hashing_embedding(text)
        async with self._client_lock:
            return await asyncio.to_thread(self._embed_sync, text, task)

    async def embed_many(self, texts: list[str], task: EmbeddingTask) -> list[list[float]]:
        if not self._client:
            return [self._hashing_embedding(text) for text in texts]
        async with self._client_lock:
            return await asyncio.to_thread(self._embed_batch_sync, texts, task)

    def _embed_batch_sync(self, texts: list[str], task: EmbeddingTask) -> list[list[float]]:
        result: list[list[float]] = []
        batch: list[str] = []
        size = 0
        for text in texts:
            cost = conservative_tokens(text) + 100
            if cost > 25_000:
                raise ToolError("Đoạn văn vượt ngân sách embedding.", code="embedding_input_limit")
            if batch and (size + cost > 25_000 or len(batch) >= 32):
                result.extend(self._request_embeddings(batch, task))
                batch, size = [], 0
            batch.append(text)
            size += cost
        if batch:
            result.extend(self._request_embeddings(batch, task))
        return result

    def _embed_sync(self, text: str, task: EmbeddingTask) -> list[float]:
        return self._request_embeddings([text], task)[0]

    def _request_embeddings(self, texts: list[str], task: EmbeddingTask) -> list[list[float]]:
        assert self._client is not None
        if self.settings.gemini_embedding_model != "gemini-embedding-2":
            raise ToolError("Chỉ Gemini Embedding 2 được phép gọi.", code="model_not_allowed")
        # Embedding 2 không nhận task_type; không gửi field này kể cả với giá trị null.
        config = types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSION)
        if self.settings.gemini_embedding_model.startswith("gemini-embedding-2"):
            prefix = {
                EmbeddingTask.DOCUMENT: "title: none | text: ",
                EmbeddingTask.QUERY: "task: search result | query: ",
                EmbeddingTask.SEMANTIC_SIMILARITY: "task: sentence similarity | query: ",
            }[task]
            texts = [prefix + text for text in texts]
        else:
            config.task_type = task.value
        quota_guard(
            self.settings,
            credential=self.settings.gemini_api_key,
        ).reserve_with_wait(
            "embedding",
            sum(conservative_tokens(text) for text in texts),
            max_wait_seconds=70,
        )
        # Chuẩn bị contents: chuỗi đơn cho 1 văn bản, hoặc danh sách types.Content cho batch
        if len(texts) == 1:
            genai_contents = texts[0]
        else:
            genai_contents = [
                types.Content(parts=[types.Part.from_text(text=t)]) for t in texts
            ]

        try:
            response = self._client.models.embed_content(
                model=self.settings.gemini_embedding_model,
                contents=genai_contents,
                config=config,
            )
            if response.embeddings and len(response.embeddings) == len(texts):
                if all(
                    item.values
                    and len(item.values) == EMBEDDING_DIMENSION
                    and all(math.isfinite(v) for v in item.values)
                    for item in response.embeddings
                ):
                    return [list(item.values) for item in response.embeddings]
        except Exception:
            # Fallback nếu batch dạng Content không được hỗ trợ ở mock/endpoint cụ thể
            pass

        # Fallback gửi danh sách gốc hoặc từng text kèm retry ngắn
        embeddings: list[list[float]] = []
        for text in texts:
            response = self._client.models.embed_content(
                model=self.settings.gemini_embedding_model,
                contents=text,
                config=config,
            )
            if not response.embeddings or not response.embeddings[0].values:
                raise RuntimeError("Gemini không trả về embedding.")
            values = list(response.embeddings[0].values)
            if len(values) != EMBEDDING_DIMENSION or any(not math.isfinite(v) for v in values):
                raise ToolError("Gemini trả về vector không hợp lệ.", code="invalid_embedding")
            embeddings.append(values)
        return embeddings

    @staticmethod
    def _hashing_embedding(text: str) -> list[float]:
        """Feature hashing 768 chiều, ổn định qua các lần khởi động."""

        vector = [0.0] * EMBEDDING_DIMENSION
        for token in tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / magnitude for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)
