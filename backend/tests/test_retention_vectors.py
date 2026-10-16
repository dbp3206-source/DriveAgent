"""Real isolated Qdrant + adversarial adapter proofs; no AI or network."""

from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from qdrant_client import QdrantClient, models

from app.services.cleanup_jobs import PurgeReference
from app.services.retention_policy import RetentionPolicyError
from app.services.retention_vectors import (
    COLLECTIONS,
    RetentionVectors,
    VectorPoint,
)

OWNER, OTHER = "synthetic-owner", "synthetic-other"
FIRST, SECOND, THIRD = (str(UUID(int=i)) for i in (1, 2, 3))
SECRET = "PRIVATE PAYLOAD MUST NEVER LEAVE ADAPTER"


@pytest.fixture
def store(tmp_path):
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    for collection in COLLECTIONS:
        client.create_collection(collection, vectors_config=models.VectorParams(
            size=2, distance=models.Distance.COSINE,
        ))
    value = SimpleNamespace(client=client, settings=SimpleNamespace(
        resolved_database_url="sqlite+aiosqlite:///synthetic.db",
        resolved_qdrant_path=tmp_path / "qdrant",
    ))
    yield value
    client.close()


def put(store, collection, identity, owner=OWNER, **payload):
    store.client.upsert(collection, points=[models.PointStruct(
        id=identity, vector=[0.6, 0.8], payload={"user_id": owner, **payload},
    )], wait=True)


def ref(identity=FIRST, collection="drive_chunks", owner=OWNER):
    return PurgeReference(kind=collection, object_id=identity, owner_id=owner)


@pytest.mark.asyncio
async def test_inventory_exact_owner_bounded_metadata_and_verified_deletion(store):
    put(store, "drive_chunks", FIRST, content=SECRET)
    put(store, "drive_chunks", SECOND, OTHER)
    put(store, "agent_memories", THIRD, kind="fact")
    adapter = RetentionVectors(store)
    result = await adapter.inventory(OWNER)
    assert result.mode == "qdrant"
    assert {(p.collection, p.point_id) for p in result.points} == {
        ("drive_chunks", FIRST), ("agent_memories", THIRD),
    }
    assert SECRET not in repr(result)
    assert all(set(asdict(p)) == {"collection", "point_id", "owner_id", "fingerprint"}
               for p in result.points)
    point = next(p for p in result.points if p.point_id == FIRST)
    assert await adapter.delete_verified(ref(), approved=point) is True
    assert store.client.retrieve("drive_chunks", [FIRST]) == []
    assert len(store.client.retrieve("drive_chunks", [SECOND])) == 1
    assert len(store.client.retrieve("agent_memories", [THIRD])) == 1
    assert await adapter.delete_verified(ref(), approved=point) is True
    assert await adapter.delete_verified(ref(), approved=None) is True


@pytest.mark.asyncio
async def test_inventory_pages_and_digest_detect_payload_change(store, monkeypatch):
    monkeypatch.setattr("app.services.retention_vectors.PAGE_SIZE", 1)
    put(store, "drive_chunks", FIRST, tag="before")
    put(store, "drive_chunks", SECOND)
    adapter = RetentionVectors(store)
    original = store.client.scroll
    calls = []

    def scroll(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(store.client, "scroll", scroll)
    first = await adapter.inventory(OWNER)
    assert len(first.points) == 2
    assert len(calls) >= 3  # second collection is also positively inventoried
    assert all(c["with_vectors"] is False and c["limit"] == 1 for c in calls)
    assert all(c["scroll_filter"].must[0].match.value == OWNER for c in calls)
    assert (await adapter.inventory(OWNER)).digest == first.digest
    put(store, "drive_chunks", FIRST, tag="after")
    assert (await adapter.inventory(OWNER)).digest != first.digest
    with pytest.raises(RetentionPolicyError, match="retention_vector_snapshot_changed"):
        await adapter.delete_verified(ref(), approved=first.points[0])
    assert len(store.client.retrieve("drive_chunks", [FIRST])) == 1


@pytest.mark.asyncio
async def test_inventory_limit_never_returns_partial_completeness(store):
    put(store, "drive_chunks", FIRST)
    put(store, "agent_memories", SECOND)
    with pytest.raises(RetentionPolicyError, match="retention_vector_inventory_too_large"):
        await RetentionVectors(store).inventory(OWNER, max_points=1)


@pytest.mark.asyncio
async def test_fallback_with_existing_native_store_is_not_empty_proof(store):
    store.client = None
    adapter = RetentionVectors(store)
    with pytest.raises(RetentionPolicyError, match="retention_vector_unavailable"):
        await adapter.inventory(OWNER)
    with pytest.raises(RetentionPolicyError, match="retention_vector_unavailable"):
        await adapter.delete_verified(ref(), approved=None)


@pytest.mark.asyncio
async def test_nonexistent_native_store_is_explicit_absence_not_qdrant_or_sql(tmp_path):
    store = SimpleNamespace(client=None, settings=SimpleNamespace(
        resolved_database_url="sqlite+aiosqlite:///synthetic.db",
        resolved_qdrant_path=tmp_path / "never-created",
    ))
    adapter = RetentionVectors(store)
    inventory = await adapter.inventory(OWNER)
    assert inventory.mode == "native-not-created" and inventory.points == ()
    assert await adapter.delete_verified(ref(), approved=None) is True
    store.settings.resolved_qdrant_path.mkdir()
    with pytest.raises(RetentionPolicyError, match="retention_vector_unavailable"):
        await adapter.inventory(OWNER)


@pytest.mark.asyncio
async def test_postgres_generated_vectors_need_sql_transaction_evidence():
    store = SimpleNamespace(client=None, settings=SimpleNamespace(
        resolved_database_url="postgresql+psycopg://synthetic",
    ))
    adapter = RetentionVectors(store)
    inventory = await adapter.inventory(OWNER)
    assert inventory.mode == "postgres-generated" and inventory.points == ()
    with pytest.raises(RetentionPolicyError, match="retention_vector_sql_proof_required"):
        await adapter.delete_verified(ref(), approved=None)
    store.client = MagicMock()
    with pytest.raises(RetentionPolicyError, match="retention_vector_backend_invalid"):
        await adapter.inventory(OWNER)
    store.client.assert_not_called()


@pytest.mark.asyncio
async def test_wrong_owner_and_unapproved_present_point_are_not_deleted(store):
    put(store, "drive_chunks", FIRST, OTHER)
    adapter = RetentionVectors(store)
    with pytest.raises(RetentionPolicyError, match="retention_vector_owner_mismatch"):
        await adapter.delete_verified(ref(), approved=None)
    put(store, "drive_chunks", FIRST)
    with pytest.raises(RetentionPolicyError, match="retention_vector_snapshot_changed"):
        await adapter.delete_verified(ref(), approved=None)
    point = (await adapter.inventory(OWNER)).points[0]
    with pytest.raises(RetentionPolicyError, match="retention_vector_snapshot_invalid"):
        await adapter.delete_verified(ref(owner=OTHER), approved=point)
    with pytest.raises(RetentionPolicyError, match="retention_vector_snapshot_invalid"):
        await adapter.delete_verified(ref(collection="agent_memories"), approved=point)
    assert len(store.client.retrieve("drive_chunks", [FIRST])) == 1


@pytest.mark.asyncio
async def test_delete_success_without_absence_is_not_verified(store, monkeypatch):
    put(store, "drive_chunks", FIRST)
    adapter = RetentionVectors(store)
    point = (await adapter.inventory(OWNER)).points[0]
    monkeypatch.setattr(store.client, "delete", MagicMock(return_value={"status": "completed"}))
    with pytest.raises(RetentionPolicyError, match="retention_vector_delete_unverified"):
        await adapter.delete_verified(ref(), approved=point)
    call = store.client.delete.call_args.kwargs
    assert call["wait"] is True and call["points_selector"].points == [FIRST]


@pytest.mark.asyncio
async def test_unavailable_scroll_or_delete_or_readback_exposes_safe_code_only(store, monkeypatch):
    put(store, "drive_chunks", FIRST)
    adapter = RetentionVectors(store)
    point = (await adapter.inventory(OWNER)).points[0]
    for method in ("scroll", "delete", "retrieve"):
        with monkeypatch.context() as patch:
            patch.setattr(store.client, method, MagicMock(side_effect=RuntimeError(SECRET)))
            with pytest.raises(RetentionPolicyError) as error:
                if method == "scroll":
                    await adapter.inventory(OWNER)
                else:
                    await adapter.delete_verified(ref(), approved=point)
            assert str(error.value) == "retention_vector_unavailable"
            assert SECRET not in str(error.value)


@pytest.mark.asyncio
async def test_bad_server_owner_repeated_cursor_and_duplicate_point_fail_closed(store, monkeypatch):
    put(store, "drive_chunks", FIRST)
    record = store.client.retrieve("drive_chunks", [FIRST], with_payload=True)[0]
    adapter = RetentionVectors(store)
    for pages in (
        [([record], FIRST), ([record], FIRST)],
        [([record, record], None)],
        [([], FIRST)],
    ):
        with monkeypatch.context() as patch:
            patch.setattr(store.client, "scroll", MagicMock(side_effect=pages))
            with pytest.raises(RetentionPolicyError, match="retention_vector_inventory_invalid"):
                await adapter.inventory(OWNER)
    record.payload["user_id"] = OTHER
    monkeypatch.setattr(store.client, "scroll", MagicMock(return_value=([record], None)))
    with pytest.raises(RetentionPolicyError, match="retention_vector_owner_mismatch"):
        await adapter.inventory(OWNER)


@pytest.mark.asyncio
async def test_missing_collection_and_uint64_point_id_are_exact(store):
    put(store, "drive_chunks", 7)
    adapter = RetentionVectors(store)
    point = (await adapter.inventory(OWNER)).points[0]
    assert point.point_id == "7"
    assert await adapter.delete_verified(ref("7"), approved=point) is True
    store.client.delete_collection("drive_chunks")
    assert await adapter.delete_verified(ref(), approved=None) is True
    assert (await adapter.inventory(OWNER)).points == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("unproven", [None, 0, "false"])
async def test_non_boolean_collection_status_is_not_absence_proof(store, monkeypatch, unproven):
    monkeypatch.setattr(store.client, "collection_exists", MagicMock(return_value=unproven))
    adapter = RetentionVectors(store)
    with pytest.raises(RetentionPolicyError, match="retention_vector_inventory_invalid"):
        await adapter.inventory(OWNER)
    with pytest.raises(RetentionPolicyError, match="retention_vector_inventory_invalid"):
        await adapter.delete_verified(ref(), approved=None)


@pytest.mark.asyncio
async def test_readback_failure_after_successful_delete_does_not_acknowledge(store, monkeypatch):
    put(store, "drive_chunks", FIRST)
    adapter = RetentionVectors(store)
    point = (await adapter.inventory(OWNER)).points[0]
    current = store.client.retrieve("drive_chunks", [FIRST])[0]
    monkeypatch.setattr(store.client, "retrieve", MagicMock(side_effect=[
        [current], RuntimeError(SECRET),
    ]))
    with pytest.raises(RetentionPolicyError, match="retention_vector_unavailable"):
        await adapter.delete_verified(ref(), approved=point)
    assert store.client.retrieve.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("bound", [0, -1, 10001, True, 1.5])
async def test_invalid_bound_is_rejected_without_reading(store, bound, monkeypatch):
    monkeypatch.setattr(store.client, "scroll", MagicMock())
    with pytest.raises(RetentionPolicyError, match="retention_vector_bound_invalid"):
        await RetentionVectors(store).inventory(OWNER, max_points=bound)
    store.client.scroll.assert_not_called()


@pytest.mark.parametrize("identity", ["not-a-point", "-1", str(2**64), True])
def test_invalid_snapshot_identity_is_rejected(identity):
    with pytest.raises(RetentionPolicyError):
        VectorPoint("drive_chunks", identity, OWNER, "a" * 64)
