"""Qdrant embedded với fallback đọc vector từ SQLite.

Qdrant chạy trực tiếp trên thư mục local, vì vậy người dùng không cần Docker. SQLite vẫn
giữ bản sao embedding để dữ liệu có thể phục hồi và test không phụ thuộc engine vector.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from app.core.config import Settings
from app.services.embeddings import EMBEDDING_DIMENSION

if TYPE_CHECKING:
    from qdrant_client import QdrantClient, models

DRIVE_COLLECTION = "drive_chunks"
MEMORY_COLLECTION = "agent_memories"


class VectorStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: QdrantClient | None = None
        self.backend_name = "sqlite-fallback"

    async def initialize(self) -> None:
        if self.settings.resolved_database_url.startswith("postgresql+psycopg"):
            # PostgreSQL generated vector columns are committed with the row;
            # RAG/Memory use the same request session for owner-filtered ranking.
            # No Qdrant sidecar or independent dual-store write on cloud.
            self.backend_name = "postgres-pgvector"
            return
        try:
            from qdrant_client import QdrantClient, models

            path = self.settings.resolved_qdrant_path
            path.mkdir(parents=True, exist_ok=True)
            self.client = await asyncio.to_thread(QdrantClient, path=str(path))
            for collection in (DRIVE_COLLECTION, MEMORY_COLLECTION):
                exists = await asyncio.to_thread(self.client.collection_exists, collection)
                if not exists:
                    await asyncio.to_thread(
                        self.client.create_collection,
                        collection_name=collection,
                        vectors_config=models.VectorParams(
                            size=EMBEDDING_DIMENSION, distance=models.Distance.COSINE
                        ),
                    )
            self.backend_name = "qdrant-embedded"
        except Exception:
            # App vẫn dùng cosine trên bản sao SQLite. Health endpoint báo rõ fallback.
            self.client = None
            self.backend_name = "sqlite-fallback"

    async def upsert(
        self, collection: str, point_id: str, vector: list[float], payload: dict[str, Any]
    ) -> None:
        if not self.client:
            return
        from qdrant_client import models

        try:
            await asyncio.to_thread(
                self.client.upsert,
                collection_name=collection,
                points=[models.PointStruct(id=point_id, vector=vector, payload=payload)],
                wait=True,
            )
        except Exception:
            self.client = None
            self.backend_name = "sqlite-fallback"

    async def delete_by_filter(self, collection: str, filters: dict[str, str | list[str]]) -> None:
        if not self.client:
            return
        from qdrant_client import models

        qfilter = self._filter(filters)
        try:
            await asyncio.to_thread(
                self.client.delete,
                collection_name=collection,
                points_selector=models.FilterSelector(filter=qfilter),
                wait=True,
            )
        except Exception:
            self.client = None
            self.backend_name = "sqlite-fallback"

    async def delete_points(self, collection: str, point_ids: list[str]) -> None:
        """Xóa đúng các vector đã biết, không dùng filter rộng dễ xóa nhầm user khác."""

        if not self.client or not point_ids:
            return
        from qdrant_client import models

        try:
            await asyncio.to_thread(
                self.client.delete,
                collection_name=collection,
                points_selector=models.PointIdsList(points=point_ids),
                wait=True,
            )
        except Exception:
            self.client = None
            self.backend_name = "sqlite-fallback"

    async def search(
        self,
        collection: str,
        vector: list[float],
        filters: dict[str, str | list[str]],
        limit: int,
    ) -> list[tuple[str, float]]:
        if not self.client:
            return []
        try:
            result = await asyncio.to_thread(
                self.client.query_points,
                collection_name=collection,
                query=vector,
                query_filter=self._filter(filters),
                limit=limit,
                with_payload=False,
            )
            return [(str(point.id), float(point.score)) for point in result.points]
        except Exception:
            self.client = None
            self.backend_name = "sqlite-fallback"
            return []

    @staticmethod
    def _filter(filters: dict[str, str | list[str]]) -> models.Filter:
        from qdrant_client import models

        return models.Filter(
            must=[
                models.FieldCondition(
                    key=key,
                    match=(
                        models.MatchAny(any=value)
                        if isinstance(value, list)
                        else models.MatchValue(value=value)
                    ),
                )
                for key, value in filters.items()
            ]
        )

    async def close(self) -> None:
        if self.client:
            await asyncio.to_thread(self.client.close)
