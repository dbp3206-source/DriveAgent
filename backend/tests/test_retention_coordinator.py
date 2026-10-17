"""Actual isolated SQL/files/context/queue; never connects personal stores or AI."""

import json
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import (
    Base,
    ChatSession,
    CleanupJob,
    GraphCheckpoint,
    LongTermMemory,
    Message,
    PdfIngestionJob,
    User,
)
from app.services import cleanup_jobs
from app.services.cleanup_jobs import PurgeReference
from app.services.object_storage import LocalPdfObjectStorage, ObjectStorageError
from app.services.owner_admission import AdmissionError, OwnerAdmission
from app.services.retention_coordinator import RetentionCoordinator
from app.services.retention_policy import RetentionPolicyError, StoreBinding
from app.services.retention_runtime import RetentionRuntime

NOW = datetime(2026, 10, 16, 9, tzinfo=UTC)
OLD = NOW - timedelta(days=40)
SECRET = "synthetic-coordinator-signing-secret-not-for-production"
BODY = "SYNTHETIC_EXPIRED_COPY_NOT_REAL_USER_CONTENT"


@pytest.fixture
async def runtime(tmp_path):
    settings = Settings(_env_file=None, state_dir=tmp_path,
                        database_url=f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
                        qdrant_path=str(tmp_path / "not-created-qdrant"),
                        relational_state_url=None, storage_backend="local")
    assert settings.data_dir == tmp_path
    assert settings.resolved_qdrant_path.is_relative_to(tmp_path)
    engine = create_async_engine(settings.resolved_database_url)

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as db:
        await db.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    gate = OwnerAdmission(factory)
    storage = LocalPdfObjectStorage(tmp_path / "pdf-inputs")
    await storage.initialize()
    stores = RetentionRuntime(settings, storage, SimpleNamespace(settings=settings, client=None),
                              backup_root=tmp_path / "no-backups")
    coordinator = RetentionCoordinator(factory, gate, stores, SECRET, clock=lambda: NOW.timestamp())
    async with factory() as db:
        owner, other = (User(email=f"{uuid4()}@example.invalid", display_name="Synthetic")
                        for _ in range(2))
        db.add_all([owner, other])
        await db.flush()
        old = LongTermMemory(user_id=owner.id, kind="fact", content=BODY, normalized_hash="a" * 64,
                             embedding_json="[]", created_at=OLD, updated_at=OLD,
                             content_updated_at=OLD)
        fresh = LongTermMemory(user_id=owner.id, kind="fact", content="FRESH_CANARY",
                               normalized_hash="b" * 64,
                               embedding_json="[]", created_at=NOW, updated_at=NOW,
                               content_updated_at=NOW)
        foreign = LongTermMemory(user_id=other.id, kind="fact", content="FOREIGN_CANARY",
                                 normalized_hash="c" * 64,
                                 embedding_json="[]", created_at=OLD, updated_at=OLD,
                                 content_updated_at=OLD)
        chat = ChatSession(user_id=owner.id, title="Fresh chat", created_at=NOW, updated_at=NOW)
        db.add_all([old, fresh, foreign, chat])
        await db.flush()
        db.add(Message(user_id=owner.id, session_id=chat.id, role="user", content="FRESH_CHAT",
                       status="completed", created_at=NOW))
        db.add_all([GraphCheckpoint(user_id=owner.id, thread_id=f"{owner.id}:{chat.id}",
                                    state_json=json.dumps({"derived_old_body": BODY}),
                                    created_at=NOW),
                    GraphCheckpoint(user_id=other.id, thread_id=f"{other.id}:synthetic",
                                    state_json='{"canary":"FOREIGN_CONTEXT"}', created_at=OLD)])
        await db.commit()
    try:
        yield SimpleNamespace(coordinator=coordinator, factory=factory, gate=gate, stores=stores,
                              storage=storage, settings=settings, owner=owner.id, other=other.id,
                              old=old.id, fresh=fresh.id, foreign=foreign.id, tmp_path=tmp_path)
    finally:
        await stores.close()
        await engine.dispose()


async def test_preview_is_readonly_and_confirmed_run_removes_old_content_and_derived_copies(
    runtime,
):
    data = runtime
    preview = await data.coordinator.preview(data.owner)
    assert preview["selected_count"] == 1 and preview["reset_context_count"] == 1
    assert BODY not in json.dumps(preview, default=str)
    async with data.factory() as db:
        assert await db.get(LongTermMemory, data.old) is not None
        assert await db.scalar(select(func.count()).select_from(CleanupJob)) == 0
    identity = await data.coordinator.confirm(data.owner, preview["token"])
    with pytest.raises(AdmissionError):
        async with data.gate.shared(data.owner):
            pass
    assert await data.coordinator.execute_one()
    status = await cleanup_jobs.status(data.factory, data.owner, identity)
    assert status["status"] == "succeeded" and status["sql_completed"]
    assert status["remaining_count"] == 0
    async with data.factory() as db:
        assert await db.get(LongTermMemory, data.old) is None
        assert await db.get(LongTermMemory, data.fresh) is not None
        assert await db.get(LongTermMemory, data.foreign) is not None
        assert await db.scalar(select(func.count()).select_from(GraphCheckpoint).where(
            GraphCheckpoint.user_id == data.owner)) == 0
        assert await db.scalar(select(func.count()).select_from(GraphCheckpoint).where(
            GraphCheckpoint.user_id == data.other)) == 1
        assert await db.scalar(select(Message.content).where(Message.user_id == data.owner)) == (
            "FRESH_CHAT")
        assert await db.get(User, data.owner) is not None
    async with data.gate.shared(data.owner):
        pass


async def test_scheduled_retention_enqueues_due_work_without_deleting_inline(runtime):
    data = runtime
    async with data.factory() as db:
        inactive_owner = await db.get(User, data.other)
        inactive_owner.is_active = False
        await db.commit()

    result = await data.coordinator.enqueue_due_retention()
    assert result == {"checked": 2, "enqueued": 2, "retried": 0, "skipped": 0, "failed": 0}
    async with data.factory() as db:
        owner_job = await db.scalar(select(CleanupJob).where(CleanupJob.user_id == data.owner))
        other_job = await db.scalar(select(CleanupJob).where(CleanupJob.user_id == data.other))
        assert owner_job is not None and other_job is not None
        assert owner_job.automatic and other_job.automatic
        assert owner_job.status == other_job.status == "queued"
        assert await db.get(LongTermMemory, data.old) is not None

    repeated = await data.coordinator.enqueue_due_retention()
    assert repeated == {"checked": 2, "enqueued": 0, "retried": 0, "skipped": 2, "failed": 0}


async def test_automatic_cleanup_is_retried_after_backoff_but_stays_non_cancellable(runtime):
    data = runtime
    await data.coordinator.enqueue_due_retention()
    async with data.factory() as db:
        job = await db.scalar(select(CleanupJob).where(CleanupJob.user_id == data.owner))
        job.status = "needs_attention"
        job.attempts = 3
        job.error_code = "storage_unavailable"
        job.updated_at = NOW - timedelta(hours=2)
        identity = job.id
        await db.commit()

    result = await data.coordinator.enqueue_due_retention()
    assert result["retried"] == 1
    status = await cleanup_jobs.status(data.factory, data.owner, identity)
    assert status["status"] == "queued" and status["automatic"]
    assert status["can_cancel"] is False
    with pytest.raises(cleanup_jobs.CleanupStateError, match="cancel_state_conflict"):
        await cleanup_jobs.cancel(data.factory, data.owner, identity)


async def test_preview_warns_three_days_before_expiry(runtime):
    data = runtime
    reminder = LongTermMemory(
        user_id=data.owner, kind="fact", content="SYNTHETIC_UPCOMING",
        normalized_hash="f" * 64, embedding_json="[]", created_at=NOW - timedelta(days=28),
        updated_at=NOW - timedelta(days=28), content_updated_at=NOW - timedelta(days=28),
    )
    async with data.factory() as db:
        db.add(reminder)
        await db.commit()

    preview = await data.coordinator.preview(data.owner)
    assert preview["upcoming_count"] == 1
    assert preview["next_due_at"] == (NOW + timedelta(days=2)).isoformat()


async def test_changed_context_after_preview_or_other_owner_cannot_confirm(runtime):
    preview = await runtime.coordinator.preview(runtime.owner)
    with pytest.raises(RetentionPolicyError, match="invalid_retention_approval"):
        await runtime.coordinator.confirm(runtime.other, preview["token"])
    async with runtime.factory() as db:
        await db.execute(update(GraphCheckpoint).where(
            GraphCheckpoint.user_id == runtime.owner).values(state_json='{"changed":true}'))
        await db.commit()
    with pytest.raises(RetentionPolicyError, match="retention_preview_changed"):
        await runtime.coordinator.confirm(runtime.owner, preview["token"])
    async with runtime.factory() as db:
        assert await db.get(LongTermMemory, runtime.old) is not None
        assert await db.scalar(select(func.count()).select_from(CleanupJob)) == 0


async def test_native_auxiliary_state_commits_resumes_after_lost_receipt_without_replay(runtime):
    from app.services.skills import SkillSpec, SkillStore

    store = SkillStore(runtime.tmp_path)
    row = store.save(runtime.owner, SkillSpec(name="synthetic_report", title="Synthetic",
                    description="Synthetic only", goal="Read {input}", procedure=["Read {input}"],
                    output_format="Markdown"))
    import sqlite3
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE skill_content_clocks SET content_changed=? WHERE skill_id=?",
                   (OLD.timestamp(), row["id"]))
    preview = await runtime.coordinator.preview(runtime.owner)
    identity = await runtime.coordinator.confirm(runtime.owner, preview["token"])
    claimed = await cleanup_jobs.claim(runtime.factory, now=NOW.timestamp())
    # Emulate a worker crash immediately after the foreign store committed,
    # before its durable progress receipt. All scope was already approved.
    async with runtime.factory() as db:
        await cleanup_jobs.mark_started(db, identity, claimed["token"], claimed["attempt"],
                                        now=NOW.timestamp())
        await db.commit()
    with sqlite3.connect(store.path) as db:
        db.execute("DELETE FROM skill_content_clocks WHERE skill_id=?", (row["id"],))
        db.execute("DELETE FROM skills WHERE id=?", (row["id"],))
    async with runtime.factory() as db:
        await db.execute(update(CleanupJob).where(CleanupJob.id == identity).values(
            lease_until=NOW.timestamp() - 1))
        await db.commit()
    assert await runtime.coordinator.execute_one()
    assert (await cleanup_jobs.status(runtime.factory, runtime.owner, identity))["status"] == (
        "succeeded")
    assert store.list(runtime.owner) == []


async def test_orphan_pdf_is_confirmed_physically_deleted_and_failure_resumes(runtime, monkeypatch):
    identity = "synthetic-orphan"
    await runtime.storage.put(runtime.owner, identity, b"SYNTHETIC_PDF_ONLY")
    path = runtime.storage.root / runtime.owner / f"{identity}.pdf"
    assert path.is_relative_to(runtime.tmp_path)
    os.utime(path, (OLD.timestamp(), OLD.timestamp()))
    preview = await runtime.coordinator.preview(runtime.owner)
    job = await runtime.coordinator.confirm(runtime.owner, preview["token"])
    original = runtime.storage.delete_verified

    async def unavailable(*_args):
        raise ObjectStorageError("object_delete_failed")

    monkeypatch.setattr(runtime.storage, "delete_verified", unavailable)
    assert await runtime.coordinator.execute_one()
    status = await cleanup_jobs.status(runtime.factory, runtime.owner, job)
    assert status["status"] == "needs_attention" and status["sql_completed"]
    assert status["remaining_count"] == 1 and path.is_file()
    async with runtime.gate.shared(runtime.owner, readonly=True):
        with pytest.raises(AdmissionError):
            async with runtime.gate.shared(runtime.owner):
                pass
    monkeypatch.setattr(runtime.storage, "delete_verified", original)
    await cleanup_jobs.retry(runtime.factory, runtime.owner, job)
    assert await runtime.coordinator.execute_one()
    assert not path.exists()
    assert (await cleanup_jobs.status(runtime.factory, runtime.owner, job))["status"] == "succeeded"


async def test_nonempty_shared_backup_prevents_partial_retention_claim(runtime):
    root = runtime.stores.backup_root
    root.mkdir()
    (root / "audit-pre-scrub-20260901T000000Z.db.fernet").write_bytes(b"SYNTHETIC_ENCRYPTED")
    with pytest.raises(RetentionPolicyError, match="retention_shared_backup_present"):
        await runtime.coordinator.preview(runtime.owner)


@pytest.mark.parametrize("change_survivor", [False, True])
async def test_partial_native_pdf_delete_retries_only_unchanged_approved_copy(
    runtime, monkeypatch, change_survivor,
):
    identity = "synthetic-duplicate"
    async with runtime.factory() as db:
        db.add(PdfIngestionJob(id=identity, user_id=runtime.owner, name="synthetic.pdf",
                              status="completed", content_hash="d" * 64, size_bytes=1,
                              created_at=OLD, updated_at=OLD))
        await db.commit()
    await runtime.storage.put(runtime.owner, identity, b"SYNTHETIC_CURRENT")
    current = runtime.storage.root / runtime.owner / f"{identity}.pdf"
    legacy = runtime.storage.root / f"{identity}.pdf"
    assert all(path.is_relative_to(runtime.tmp_path) for path in (current, legacy))
    legacy.write_bytes(b"SYNTHETIC_LEGACY")
    for path in (current, legacy):
        os.utime(path, (OLD.timestamp(), OLD.timestamp()))
    preview = await runtime.coordinator.preview(runtime.owner)
    job = await runtime.coordinator.confirm(runtime.owner, preview["token"])
    original = runtime.storage.delete

    async def interrupted_delete(owner, job_id):
        assert owner == runtime.owner and job_id == identity
        current.unlink()
        raise ObjectStorageError("object_delete_failed")

    monkeypatch.setattr(runtime.storage, "delete", interrupted_delete)
    await runtime.coordinator.execute_one()
    assert not current.exists() and legacy.exists()
    assert (await cleanup_jobs.status(runtime.factory, runtime.owner, job))["status"] == (
        "needs_attention")
    if change_survivor:
        legacy.write_bytes(b"CHANGED_SYNTHETIC_NOT_APPROVED")
    monkeypatch.setattr(runtime.storage, "delete", original)
    await cleanup_jobs.retry(runtime.factory, runtime.owner, job)
    await runtime.coordinator.execute_one()
    status = await cleanup_jobs.status(runtime.factory, runtime.owner, job)
    assert status["status"] == ("needs_attention" if change_survivor else "succeeded")
    assert legacy.exists() is change_survivor


def test_binding_change_and_critical_steps_are_not_implicit_consent():
    from test_retention_policy import NOW as POLICY_NOW
    from test_retention_policy import candidate, inventories

    from app.services.retention_policy import RetentionPolicy

    policy = RetentionPolicy(SECRET)
    binding = StoreBinding(name="graph", fingerprint="a" * 64, count=2)
    preview = policy.prepare(owner_id="synthetic-owner-a", candidates=[candidate()],
                             inventories=inventories(), now=POLICY_NOW, bindings=(binding,))
    with pytest.raises(RetentionPolicyError, match="preview_changed"):
        policy.validate(token=preview.token, owner_id="synthetic-owner-a", current=[candidate()],
                        inventories=inventories(), now=POLICY_NOW,
                        bindings=(binding.model_copy(update={"count": 3}),))
    assert PurgeReference(kind="state", owner_id="owner-a", object_id="skills",
                          fingerprint="a" * 64).fingerprint == "a" * 64
