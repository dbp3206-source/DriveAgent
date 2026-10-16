"""Owned PDF metadata only: actual files + isolated SQLite Storage-schema fixture."""

import hashlib
import os
import subprocess
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
import respx
from sqlalchemy import delete, event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import Base, CleanupJob, PdfIngestionJob, User
from app.services.cleanup_jobs import CleanupPlan, PurgeReference
from app.services.object_storage import LocalPdfObjectStorage, SupabasePdfObjectStorage
from app.services.retention_objects import object_inventory, validate_object_reference
from app.services.retention_policy import (
    ApprovalSnapshot,
    RetentionKind,
    RetentionPolicyError,
    SnapshotItem,
)

OWNER, OTHER = "owner-a", "owner-b"
OLD = datetime(2026, 8, 1, tzinfo=UTC)
NOW = OLD + timedelta(days=45)
CANARY = b"SYNTHETIC PRIVATE PDF BODY NEVER READ BY INVENTORY"
BUCKET_URL = "https://synthetic.supabase.co/storage/v1/bucket/veridra-private"


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'application.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def attach(connection, _):
        connection.execute("ATTACH DATABASE ? AS storage", (str(tmp_path / "storage.db"),))

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "CREATE TABLE storage.objects (id TEXT PRIMARY KEY, name TEXT, bucket_id TEXT, "
            "created_at TEXT, updated_at TEXT, private_body TEXT)"
        ))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            session.add_all([User(id=OWNER, email="a@example.invalid", display_name="Synthetic A"),
                             User(id=OTHER, email="b@example.invalid", display_name="Synthetic B")])
            await session.commit()
            yield session
    finally:
        await engine.dispose()


async def job(db, identity, owner=OWNER, status="completed"):
    row = PdfIngestionJob(
        id=identity, user_id=owner, name="SYNTHETIC_PRIVATE_NAME", size_bytes=1,
        content_hash=hashlib.sha256(identity.encode()).hexdigest(), status=status,
        created_at=OLD, updated_at=OLD,
    )
    db.add(row)
    await db.commit()
    return row


async def ledger(db, identity, owner=OWNER):
    approval = str(uuid4())
    snapshot = ApprovalSnapshot(
        approval_id=approval, owner_id=owner, issued_at=NOW,
        cutoff=NOW - timedelta(days=30), items=(SnapshotItem(
            kind=RetentionKind.SOURCE, record_id=f"pdf_objects:{identity}",
            changed_at=OLD, fingerprint="a" * 64,
        ),),
    )
    plan = CleanupPlan(snapshot=snapshot, external=(PurgeReference(
        kind="pdf", owner_id=owner, object_id=identity,
    ),))
    body = plan.model_dump_json()
    row = CleanupJob(
        user_id=owner, approval_id=approval, plan_json=body,
        plan_hash=hashlib.sha256(body.encode()).hexdigest(),
        remaining_json='[]', completed_json='[]', status="completed",
    )
    db.add(row)
    await db.commit()
    return row


async def cloud_object(db, name, *, bucket="veridra-private", created=OLD, updated=OLD):
    await db.execute(text(
        "INSERT INTO storage.objects VALUES (:id,:name,:bucket,:created,:updated,:body)"
    ), {"id": str(uuid4()), "name": name, "bucket": bucket,
        "created": created.isoformat() if created else None,
        "updated": updated.isoformat() if updated else None, "body": CANARY.decode()})
    await db.commit()


def cloud_storage():
    return SupabasePdfObjectStorage(Settings(
        _env_file=None, storage_backend="supabase", supabase_url="https://synthetic.supabase.co",
        supabase_service_role_key="FAKE-NOT-A-REAL-KEY",
    ))


def age(path, stamp=OLD):
    os.utime(path, (stamp.timestamp(), stamp.timestamp()))


async def test_native_namespace_orphans_active_jobs_and_metadata_only(db, tmp_path, monkeypatch):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.put(OWNER, "old-job", CANARY)
    await storage.put(OWNER, "orphan", CANARY)
    await storage.put(OTHER, "other-job", CANARY)
    await job(db, "old-job", status="running")
    for identity in ("old-job", "orphan"):
        age(storage.root / OWNER / f"{identity}.pdf")
    monkeypatch.setattr(storage, "get", MagicMock(side_effect=AssertionError("body read")))
    result = await object_inventory(db, storage, OWNER)
    assert result.mode == "local" and result.owner_id == OWNER
    assert result.existing_job_ids == ("old-job",)
    assert {c.record_id for c in result.candidates} == {"pdf_objects:old-job", "pdf_objects:orphan"}
    assert {c.changed_at for c in result.candidates} == {OLD}
    assert next(c for c in result.candidates if c.record_id.endswith("old-job")).active is True
    assert CANARY.decode() not in repr(result) and "SYNTHETIC_PRIVATE_NAME" not in repr(result)
    assert all(ref.fingerprint for ref in result.references)
    assert all(validate_object_reference(ref, result) for ref in result.references)
    storage.get.assert_not_called()


async def test_native_legacy_and_current_group_into_one_candidate_with_newest_age(db, tmp_path):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.put(OWNER, "old-job", CANARY)
    await job(db, "old-job")
    legacy = storage.root / "old-job.pdf"
    legacy.write_bytes(CANARY)
    age(legacy, NOW)
    age(storage.root / OWNER / "old-job.pdf", OLD)
    result = await object_inventory(db, storage, OWNER)
    assert len(result.candidates) == len(result.references) == 1
    assert result.candidates[0].changed_at == NOW
    assert validate_object_reference(result.references[0], result)
    await db.execute(delete(PdfIngestionJob))
    await ledger(db, "old-job")
    after_sql = await object_inventory(db, storage, OWNER)
    assert after_sql.existing_job_ids == ()
    assert validate_object_reference(result.references[0], after_sql)


async def test_native_legacy_owner_from_job_or_plan_excludes_other_owner(db, tmp_path):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.initialize()
    for identity in ("own-job", "other-job", "other-gone-job"):
        (storage.root / f"{identity}.pdf").write_bytes(CANARY)
    await job(db, "own-job")
    await job(db, "other-job", OTHER)
    await ledger(db, "other-gone-job", OTHER)
    result = await object_inventory(db, storage, OWNER)
    assert [c.record_id for c in result.candidates] == ["pdf_objects:own-job"]
    assert OTHER not in repr(result) and "other-gone-job" not in repr(result)


async def test_native_unknown_legacy_and_tampered_ledger_fail_closed(db, tmp_path):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.initialize()
    (storage.root / "unknown.pdf").write_bytes(CANARY)
    with pytest.raises(RetentionPolicyError, match="retention_object_ownership_unverified"):
        await object_inventory(db, storage, OWNER)
    row = await ledger(db, "unknown")
    assert len((await object_inventory(db, storage, OWNER)).candidates) == 1
    row.plan_hash = "f" * 64
    await db.commit()
    with pytest.raises(RetentionPolicyError, match="retention_object_ownership_unverified"):
        await object_inventory(db, storage, OWNER)


async def test_native_legacy_conflicting_owner_cannot_be_deleted_with_current_copy(db, tmp_path):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.put(OWNER, "same-id", CANARY)
    (storage.root / "same-id.pdf").write_bytes(CANARY)
    await job(db, "same-id", OTHER)
    with pytest.raises(RetentionPolicyError, match="retention_object_ownership_unverified"):
        await object_inventory(db, storage, OWNER)


async def test_native_fingerprint_changes_and_absence_is_not_delete_proof(db, tmp_path):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.put(OWNER, "old-job", CANARY)
    first = await object_inventory(db, storage, OWNER)
    await storage.put(OWNER, "old-job", CANARY + b"new")
    changed = await object_inventory(db, storage, OWNER)
    with pytest.raises(RetentionPolicyError, match="retention_object_snapshot_changed"):
        validate_object_reference(first.references[0], changed)
    unpinned = first.references[0].model_copy(update={"fingerprint": None})
    with pytest.raises(RetentionPolicyError, match="retention_object_snapshot_changed"):
        validate_object_reference(unpinned, changed)
    await storage.delete_verified(OWNER, "old-job")
    absent = await object_inventory(db, storage, OWNER)
    assert validate_object_reference(first.references[0], absent) is False
    assert absent.candidates == ()


async def test_native_partial_delete_accepts_only_unchanged_approved_survivor(db, tmp_path):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.put(OWNER, "old-job", CANARY)
    await job(db, "old-job")
    legacy = storage.root / "old-job.pdf"
    legacy.write_bytes(CANARY)
    before = await object_inventory(db, storage, OWNER)
    approved = before.references[0]
    assert len(approved.copy_fingerprints) == 2
    # Emulate LocalPdfObjectStorage.delete crashing after its first unlink.
    (storage.root / OWNER / "old-job.pdf").unlink()
    after = await object_inventory(db, storage, OWNER)
    assert after.references[0].fingerprint != approved.fingerprint
    assert len(after.references[0].copy_fingerprints) == 1
    assert validate_object_reference(approved, after)
    old_format = approved.model_copy(update={"copy_fingerprints": ()})
    with pytest.raises(RetentionPolicyError, match="retention_object_snapshot_changed"):
        validate_object_reference(old_format, after)
    await storage.delete_verified(OWNER, "old-job")
    assert validate_object_reference(approved, await object_inventory(db, storage, OWNER)) is False


@pytest.mark.parametrize("change", ["modify", "replace", "introduce"])
async def test_native_partial_delete_rejects_modified_replaced_or_new_copy(db, tmp_path, change):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.put(OWNER, "old-job", CANARY)
    await job(db, "old-job")
    legacy = storage.root / "old-job.pdf"
    legacy.write_bytes(CANARY)
    age(legacy)
    approved = (await object_inventory(db, storage, OWNER)).references[0]
    (storage.root / OWNER / "old-job.pdf").unlink()
    assert validate_object_reference(approved, await object_inventory(db, storage, OWNER))
    if change == "modify":
        legacy.write_bytes(CANARY + b"changed")
    elif change == "replace":
        legacy.unlink()
        legacy.write_bytes(CANARY)
        age(legacy)
    else:
        await storage.put(OWNER, "old-job", CANARY)
    with pytest.raises(RetentionPolicyError, match="retention_object_snapshot_changed"):
        validate_object_reference(approved, await object_inventory(db, storage, OWNER))


async def test_native_owner_alias_hardlink_and_subdirectory_fail_without_reading(db, tmp_path):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.put(OTHER, "private", CANARY)
    alias = storage.root / OWNER
    try:
        alias.symlink_to(storage.root / OTHER, target_is_directory=True)
    except (OSError, NotImplementedError):
        if os.name != "nt":
            pytest.skip("directory aliases unavailable")
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias),
                                 str(storage.root / OTHER)], capture_output=True, check=False)
        assert result.returncode == 0
    with pytest.raises(RetentionPolicyError, match="retention_object_path_unsafe"):
        await object_inventory(db, storage, OWNER)


async def test_native_file_hardlinks_are_rejected(db, tmp_path):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.put(OWNER, "old-job", CANARY)
    os.link(storage.root / OWNER / "old-job.pdf", tmp_path / "outside.pdf")
    with pytest.raises(RetentionPolicyError, match="retention_object_path_unsafe"):
        await object_inventory(db, storage, OWNER)


@pytest.mark.parametrize("name", ["nested", "wrong.txt", "../bad.pdf", "job.PDF"])
async def test_native_invalid_owner_file_names_fail(db, tmp_path, name):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.initialize()
    directory = storage.root / OWNER
    directory.mkdir()
    if name == "nested":
        (directory / name).mkdir()
    else:
        (directory / name).write_bytes(CANARY)
    with pytest.raises(RetentionPolicyError):
        await object_inventory(db, storage, OWNER)


async def test_native_missing_root_is_explicit_empty_without_creation(db, tmp_path):
    storage = LocalPdfObjectStorage(tmp_path / "missing")
    result = await object_inventory(db, storage, OWNER)
    assert result.mode == "local" and result.candidates == ()
    assert not storage.root.exists()


async def test_native_caps_never_return_partial_inventory(db, tmp_path):
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    await storage.put(OWNER, "one", CANARY)
    await storage.put(OWNER, "two", CANARY)
    with pytest.raises(RetentionPolicyError, match="retention_object_inventory_too_large"):
        await object_inventory(db, storage, OWNER, max_objects=1)


@respx.mock
async def test_cloud_metadata_owner_prefix_newest_age_and_select_only(db):
    await cloud_object(db, f"{OWNER}/old-job.pdf", updated=NOW)
    await cloud_object(db, f"{OTHER}/other-job.pdf")
    await cloud_object(db, f"{OWNER}-suffix/other-job.pdf")
    await cloud_object(db, f"{OWNER}/other-bucket.pdf", bucket="other-bucket")
    await job(db, "old-job")
    route = respx.get(BUCKET_URL).mock(return_value=httpx.Response(200, json={"public": False}))
    statements = []

    def capture(_conn, _cursor, statement, parameters, _ctx, _many):
        statements.append((statement, parameters))

    event.listen(db.bind.sync_engine, "before_cursor_execute", capture)
    try:
        result = await object_inventory(db, cloud_storage(), OWNER)
    finally:
        event.remove(db.bind.sync_engine, "before_cursor_execute", capture)
    assert route.call_count == 1 and len(respx.calls) == 1
    assert result.mode == "supabase" and len(result.candidates) == 1
    assert result.candidates[0].record_id == "pdf_objects:old-job"
    assert result.candidates[0].changed_at == NOW
    assert result.existing_job_ids == ("old-job",)
    assert CANARY.decode() not in repr(result) and OTHER not in repr(result)
    assert statements and all(statement.lstrip().upper().startswith("SELECT")
                              for statement, _ in statements)
    storage_query = next((s, p) for s, p in statements if "storage.objects" in s)
    assert "private_body" not in storage_query[0] and OWNER not in storage_query[0]
    assert f"{OWNER}/%" in storage_query[1]


@respx.mock
@pytest.mark.parametrize("name", ["nested/job.pdf", "../job.pdf", "job.txt", "job.PDF", ".pdf"])
async def test_cloud_invalid_names_fail_instead_of_silently_skipping(db, name):
    await cloud_object(db, f"{OWNER}/{name}")
    respx.get(BUCKET_URL).mock(return_value=httpx.Response(200, json={"public": False}))
    with pytest.raises(RetentionPolicyError):
        await object_inventory(db, cloud_storage(), OWNER)


@respx.mock
@pytest.mark.parametrize("status,body", [(200, {"public": True}), (200, {}), (404, {}), (403, {})])
async def test_cloud_requires_positive_private_bucket_proof(db, status, body):
    respx.get(BUCKET_URL).mock(return_value=httpx.Response(status, json=body))
    with pytest.raises(RetentionPolicyError, match="retention_object_bucket_unverified"):
        await object_inventory(db, cloud_storage(), OWNER)


@respx.mock
async def test_cloud_age_missing_schema_or_clock_fail_closed_and_cap_is_honest(db):
    storage = cloud_storage()
    respx.get(BUCKET_URL).mock(return_value=httpx.Response(200, json={"public": False}))
    await cloud_object(db, f"{OWNER}/unknown-age.pdf", updated=None)
    with pytest.raises(RetentionPolicyError, match="retention_object_age_unknown"):
        await object_inventory(db, storage, OWNER)
    await db.execute(text("DELETE FROM storage.objects"))
    await cloud_object(db, f"{OWNER}/one.pdf")
    await cloud_object(db, f"{OWNER}/two.pdf")
    with pytest.raises(RetentionPolicyError, match="retention_object_inventory_too_large"):
        await object_inventory(db, storage, OWNER, max_objects=1)
    await db.execute(text("DROP TABLE storage.objects"))
    with pytest.raises(RetentionPolicyError, match="retention_object_inventory_unavailable"):
        await object_inventory(db, storage, OWNER)


@respx.mock
async def test_cloud_fingerprint_pin_survives_sql_job_delete_but_detects_object_update(db):
    storage = cloud_storage()
    respx.get(BUCKET_URL).mock(return_value=httpx.Response(200, json={"public": False}))
    await cloud_object(db, f"{OWNER}/old-job.pdf")
    await job(db, "old-job")
    first = await object_inventory(db, storage, OWNER)
    await db.execute(delete(PdfIngestionJob))
    after_sql = await object_inventory(db, storage, OWNER)
    assert validate_object_reference(first.references[0], after_sql)
    await db.execute(text("UPDATE storage.objects SET updated_at=:stamp"),
                     {"stamp": NOW.isoformat()})
    with pytest.raises(RetentionPolicyError, match="retention_object_snapshot_changed"):
        validate_object_reference(first.references[0], await object_inventory(db, storage, OWNER))


@pytest.mark.parametrize("owner", ["../escape", "owner_%", "", "a" * 65])
async def test_owner_identity_is_validated_before_database_or_http(owner, tmp_path):
    with pytest.raises(RetentionPolicyError, match="retention_object_identity_invalid"):
        await object_inventory(None, LocalPdfObjectStorage(tmp_path / "objects"), owner)


@pytest.mark.parametrize("bound", [0, 10001, True])
async def test_inventory_bound_is_checked_before_database_or_filesystem(bound, tmp_path):
    with pytest.raises(RetentionPolicyError, match="retention_object_bound_invalid"):
        await object_inventory(None, LocalPdfObjectStorage(tmp_path / "objects"), OWNER,
                               max_objects=bound)
