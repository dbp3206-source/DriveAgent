"""Embedding Gemini với fallback local có tính quyết định.

Fallback hashing không thay thế chất lượng semantic của Gemini. Nó tồn tại để app vẫn
khởi động, test và tìm lexical khi người dùng chưa nhập API key.
"""

import asyncio
import hashlib
import math
import re
from enum import StrEnum

from google import genai
from google.genai import types

from app.core.config import Settings

EMBEDDING_DIMENSION = 768
TOKEN_PATTERN = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)


class EmbeddingTask(StrEnum):
    DOCUMENT = "RETRIEVAL_DOCUMENT"
    QUERY = "RETRIEVAL_QUERY"
    SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_PATTERN.findall(text)]


class EmbeddingService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = (
            genai.Client(api_key=settings.gemini_api_key,
                         http_options=types.HttpOptions(timeout=30_000))
            if settings.gemini_is_configured else None
        )

    @property
    def provider_name(self) -> str:
        return "gemini" if self._client else "local-hashing-fallback"

    async def embed(self, text: str, task: EmbeddingTask) -> list[float]:
        if not self._client:
            return self._hashing_embedding(text)
        return await asyncio.to_thread(self._embed_sync, text, task)

    def _embed_sync(self, text: str, task: EmbeddingTask) -> list[float]:
        assert self._client is not None
        # Embedding 2 không nhận task_type; không gửi field này kể cả với giá trị null.
        config = types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSION)
        if self.settings.gemini_embedding_model.startswith("gemini-embedding-2"):
            prefix = {
                EmbeddingTask.DOCUMENT: "title: none | text: ",
                EmbeddingTask.QUERY: "task: search result | query: ",
                EmbeddingTask.SEMANTIC_SIMILARITY: "task: sentence similarity | query: ",
            }[task]
            text = prefix + text
        else:
            config.task_type = task.value
        response = self._client.models.embed_content(
            model=self.settings.gemini_embedding_model,
            contents=text,
            config=config,
        )
        if not response.embeddings or not response.embeddings[0].values:
            raise RuntimeError("Gemini không trả về embedding.")
        return list(response.embeddings[0].values)

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
