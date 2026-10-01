"""Rebuild the document-vector cache from committed SQL embeddings at startup."""

import asyncio
import json

from qdrant_client import models
from sqlalchemy import select

from app.db.models import DocumentChunk
from app.services.vector_store import DRIVE_COLLECTION


async def reconcile_document_vectors(db, store) -> int:
    if store.client is None:
        return 0
    rows = (await db.scalars(select(DocumentChunk))).all()
    repaired = 0
    for start in range(0, len(rows), 100):
        batch = rows[start:start + 100]
        points = [models.PointStruct(
            id=row.id, vector=json.loads(row.embedding_json),
            payload={"user_id": row.user_id, "drive_file_id": row.drive_file_id,
                     "file_name": row.file_name, "chunk_index": row.chunk_index},
        ) for row in batch]
        # Idempotent overwrite of the cache, never a new model/embedding call.
        await asyncio.to_thread(store.client.upsert, collection_name=DRIVE_COLLECTION,
                                points=points, wait=True)
        found = await asyncio.to_thread(store.client.retrieve,
                                       collection_name=DRIVE_COLLECTION,
                                       ids=[row.id for row in batch], with_payload=True)
        owners = {str(point.id): (point.payload or {}).get("user_id") for point in found}
        if any(owners.get(row.id) != row.user_id for row in batch):
            raise RuntimeError("Document vector reconciliation read-back failed")
        repaired += len(batch)
    return repaired
