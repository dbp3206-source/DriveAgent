"""Strict, bounded retention access to the optional native Qdrant copy.

Callers must hold the owner's admission fence while inventory is revalidated and
through deletion. This adapter establishes neither age nor user consent: select
points only from an approved application's exact IDs. Store the returned point
fingerprints with the durable plan before removing the authoritative SQL rows.

No embedding, vector value or raw payload leaves this module. PostgreSQL vectors
are generated columns, not Qdrant copies: their absence is proven by the owning
SQL purge transaction, never by this adapter returning an empty inventory.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from app.services.owner_admission import joined_thread
from app.services.retention_policy import RetentionPolicyError
from app.services.vector_store import DRIVE_COLLECTION, MEMORY_COLLECTION

if TYPE_CHECKING:
    from app.services.cleanup_jobs import PurgeReference
    from app.services.vector_store import VectorStore

COLLECTIONS = (DRIVE_COLLECTION, MEMORY_COLLECTION)
PAGE_SIZE = 128
MAX_OWNER_POINTS = 10_000


def _owner(owner_id: str) -> None:
    if (not isinstance(owner_id, str) or not owner_id or len(owner_id) > 64
            or any(not (c.isascii() and (c.isalnum() or c == "-")) for c in owner_id)):
        raise RetentionPolicyError("retention_vector_owner_invalid")


def _identity(value) -> tuple[str, int | str]:
    if isinstance(value, bool):
        raise RetentionPolicyError("retention_vector_identity_invalid")
    if isinstance(value, int) or (isinstance(value, str) and value.isascii() and value.isdecimal()):
        number = int(value)
        if 0 <= number < 2**64:
            return str(number), number
    elif isinstance(value, str):
        try:
            identity = str(UUID(value))
            return identity, identity
        except ValueError:
            pass
    raise RetentionPolicyError("retention_vector_identity_invalid")


def _digest(value) -> str:
    try:
        body = json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, OverflowError):
        raise RetentionPolicyError("retention_vector_payload_invalid") from None
    return hashlib.sha256(body.encode()).hexdigest()


@dataclass(frozen=True)
class VectorPoint:
    collection: str
    point_id: str
    owner_id: str
    fingerprint: str

    def __post_init__(self):
        _owner(self.owner_id)
        identity, _ = _identity(self.point_id)
        if (self.collection not in COLLECTIONS or identity != self.point_id
                or not isinstance(self.fingerprint, str) or len(self.fingerprint) != 64
                or any(c not in "0123456789abcdef" for c in self.fingerprint)):
            raise RetentionPolicyError("retention_vector_snapshot_invalid")


@dataclass(frozen=True)
class VectorInventory:
    # postgres-generated explicitly requires SQL transaction evidence.
    mode: str
    points: tuple[VectorPoint, ...]
    digest: str


def _point(record, collection: str, owner_id: str) -> VectorPoint:
    identity, _ = _identity(record.id)
    payload = record.payload
    if not isinstance(payload, dict) or payload.get("user_id") != owner_id:
        raise RetentionPolicyError("retention_vector_owner_mismatch")
    return VectorPoint(collection, identity, owner_id,
                       _digest([collection, identity, owner_id, payload]))


async def _exists(client, collection: str) -> bool:
    exists = await joined_thread(client.collection_exists, collection)
    if type(exists) is not bool:
        raise RetentionPolicyError("retention_vector_inventory_invalid")
    return exists


class RetentionVectors:
    def __init__(self, store: VectorStore):
        self.store = store

    def _backend(self):
        if self.store.settings.resolved_database_url.startswith("postgresql+psycopg"):
            if self.store.client is not None:
                raise RetentionPolicyError("retention_vector_backend_invalid")
            return "postgres-generated", None
        client = self.store.client
        if client is not None:
            return "qdrant", client
        try:
            # Existing but locked/corrupt/unreadable data is not an empty store.
            path = self.store.settings.resolved_qdrant_path
            exists = path.exists() or path.is_symlink()
        except (OSError, ValueError):
            raise RetentionPolicyError("retention_vector_unavailable") from None
        if exists:
            raise RetentionPolicyError("retention_vector_unavailable")
        return "native-not-created", None

    async def inventory(self, owner_id: str, *, max_points: int = MAX_OWNER_POINTS
                        ) -> VectorInventory:
        """Complete owner-filtered metadata inventory, or fail without partial proof.

        At most max_points are retained in memory; another point fails closed.
        Each Qdrant request is bounded and explicitly excludes vector values.
        The returned digest is safe to bind into an authenticated preview.
        """
        _owner(owner_id)
        if type(max_points) is not int or not 1 <= max_points <= MAX_OWNER_POINTS:
            raise RetentionPolicyError("retention_vector_bound_invalid")
        mode, client = self._backend()
        points = []
        if client is not None:
            from qdrant_client import models

            query = models.Filter(must=[models.FieldCondition(
                key="user_id", match=models.MatchValue(value=owner_id),
            )])
            try:
                for collection in COLLECTIONS:
                    if not await _exists(client, collection):
                        continue
                    offset, cursors, identities = None, set(), set()
                    while True:
                        page, next_offset = await joined_thread(
                            client.scroll, collection_name=collection, scroll_filter=query,
                            limit=min(PAGE_SIZE, max_points - len(points) + 1), offset=offset,
                            with_payload=True, with_vectors=False,
                        )
                        if len(page) > min(PAGE_SIZE, max_points - len(points) + 1):
                            raise RetentionPolicyError("retention_vector_inventory_invalid")
                        for record in page:
                            point = _point(record, collection, owner_id)
                            if point.point_id in identities:
                                raise RetentionPolicyError("retention_vector_inventory_invalid")
                            identities.add(point.point_id)
                            points.append(point)
                            if len(points) > max_points:
                                raise RetentionPolicyError("retention_vector_inventory_too_large")
                        if next_offset is None:
                            break
                        cursor, _ = _identity(next_offset)
                        if not page or cursor in cursors:
                            raise RetentionPolicyError("retention_vector_inventory_invalid")
                        cursors.add(cursor)
                        offset = next_offset
            except RetentionPolicyError:
                raise
            except Exception:
                raise RetentionPolicyError("retention_vector_unavailable") from None
        ordered = tuple(sorted(points, key=lambda p: (p.collection, p.point_id)))
        digest = _digest([
            mode, owner_id, [(p.collection, p.point_id, p.fingerprint) for p in ordered],
        ])
        return VectorInventory(mode, ordered, digest)

    async def delete_verified(self, reference: PurgeReference, *, approved: VectorPoint | None
                              ) -> bool:
        """Delete one approved exact ID and prove absence; retries are idempotent.

        approved=None is permitted only when that exact ID is already absent.
        Never use this API for PostgreSQL generated vectors, which have no
        external PurgeReference. No success is inferred from delete(wait=True).
        """
        _owner(reference.owner_id)
        identity, wire_id = _identity(reference.object_id)
        if reference.kind not in COLLECTIONS:
            raise RetentionPolicyError("retention_vector_collection_invalid")
        if approved is not None and (
            approved.collection != reference.kind or approved.owner_id != reference.owner_id
            or approved.point_id != identity
        ):
            raise RetentionPolicyError("retention_vector_snapshot_invalid")
        mode, client = self._backend()
        if mode == "postgres-generated":
            raise RetentionPolicyError("retention_vector_sql_proof_required")
        if client is None:
            return True
        from qdrant_client import models

        async def read():
            records = await joined_thread(
                client.retrieve, collection_name=reference.kind, ids=[wire_id],
                with_payload=True, with_vectors=False,
            )
            if len(records) > 1:
                raise RetentionPolicyError("retention_vector_inventory_invalid")
            if not records:
                return None
            point = _point(records[0], reference.kind, reference.owner_id)
            if point.point_id != identity:
                raise RetentionPolicyError("retention_vector_inventory_invalid")
            return point

        try:
            if not await _exists(client, reference.kind):
                return True
            current = await read()
            if current is None:
                return True
            if approved is None or current != approved:
                raise RetentionPolicyError("retention_vector_snapshot_changed")
            await joined_thread(
                client.delete, collection_name=reference.kind,
                points_selector=models.PointIdsList(points=[wire_id]), wait=True,
            )
            if await read() is not None:
                raise RetentionPolicyError("retention_vector_delete_unverified")
            return True
        except RetentionPolicyError:
            raise
        except Exception:
            raise RetentionPolicyError("retention_vector_unavailable") from None
