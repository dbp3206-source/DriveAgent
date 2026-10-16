"""Real isolated SQL queue checkpoints; no provider, file purge or live-data calls."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, CleanupJob, LongTermMemory, User
from app.services import cleanup_jobs as jobs
from app.services.retention_policy import (
    REQUIRED_INVENTORIES,
    RetentionCandidate,
    RetentionKind,
    RetentionPolicy,
    content_fingerprint,
)

NOW = datetime(2026, 10, 16, 9, tzinfo=UTC)
STAMP = NOW.timestamp()
SENTINEL = "PRIVATE_SYNTHETIC_BODY_NEVER_PUT_IN_QUEUE"


def plan(owner, *, external=True):
    old = NOW - timedelta(days=31)
    kind, identity = RetentionKind.MEMORY, "long_term_memories:synthetic-one"
    row = RetentionCandidate(
        owner_id=owner, kind=kind, record_id=identity, changed_at=old,
        fingerprint=content_fingerprint(
            owner_id=owner, kind=kind, record_id=identity, changed_at=old,
            values={"content": SENTINEL},
        ),
    )
    policy = RetentionPolicy("synthetic-cleanup-signing-key-not-a-real-secret")
    coverage = dict.fromkeys(REQUIRED_INVENTORIES, True)
    preview = policy.prepare(owner_id=owner, candidates=[row], inventories=coverage, now=NOW)
    snapshot = policy.validate(token=preview.token, owner_id=owner, current=[row],
                               inventories=coverage, now=NOW)
    refs = (jobs.PurgeReference(kind="pdf", owner_id=owner, object_id="synthetic-pdf"),
            jobs.PurgeReference(kind="agent_memories", owner_id=owner,
                                object_id="synthetic-memory")) if external else ()
    return jobs.CleanupPlan(snapshot=snapshot, external=refs)


@pytest.fixture
async def queue(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'cleanup.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            owner = User(email="cleanup-a@example.invalid", display_name="Synthetic A")
            other = User(email="cleanup-b@example.invalid", display_name="Synthetic B")
            db.add_all([owner, other])
            await db.commit()
        yield factory, owner.id, other.id, engine
    finally:
        await engine.dispose()


def lease_args(lease):
    return lease["id"], lease["token"], lease["attempt"]


async def enqueue_claim(queue, *, external=True):
    factory, owner, _other, _engine = queue
    scope = plan(owner, external=external)
    identity = await jobs.enqueue(factory, owner, scope, now=STAMP)
    lease = await jobs.claim(factory, now=STAMP)
    assert lease["id"] == identity
    return scope, lease


async def test_idempotent_enqueue_is_owner_bound_and_contains_only_scope_metadata(queue):
    factory, owner, other, _engine = queue
    scope = plan(owner)
    identity = await jobs.enqueue(factory, owner, scope, now=STAMP)
    # A lost HTTP response can be recovered, even after preview expiration.
    assert await jobs.enqueue(factory, owner, scope, now=STAMP + 601) == identity
    assert await jobs.status(factory, other, identity) is None
    with pytest.raises(jobs.CleanupStateError, match="owner_mismatch"):
        await jobs.enqueue(factory, other, scope, now=STAMP)
    changed = scope.model_copy(update={"external": ()})
    with pytest.raises(jobs.CleanupStateError, match="approval_conflict"):
        await jobs.enqueue(factory, owner, changed, now=STAMP)
    async with factory() as db:
        row = await db.get(CleanupJob, identity)
        assert SENTINEL not in row.plan_json and row.remaining_json != "[]"
        assert row.completed_json == "[]" and row.critical_started_at is None
        assert row.sql_completed_at is None
    public = await jobs.status(factory, owner, identity)
    assert set(public) == {"id", "status", "attempts", "selected_count", "remaining_count",
                           "completed_count", "sql_completed", "error_code"}
    assert public["selected_count"] == 1 and public["remaining_count"] == 2
    assert public["status"] == "queued" and public["attempts"] == 0


async def test_enqueue_return_does_not_rely_on_non_expiring_session_objects(queue):
    _factory, owner, _other, engine = queue
    factory = async_sessionmaker(engine, expire_on_commit=True)
    scope = plan(owner)
    identity = await jobs.enqueue(factory, owner, scope, now=STAMP)
    assert await jobs.enqueue(factory, owner, scope, now=STAMP) == identity


@pytest.mark.parametrize("offset", [-1, 600, 601])
async def test_new_enqueue_rejects_expired_or_future_approval(queue, offset):
    factory, owner, _other, _engine = queue
    with pytest.raises(jobs.CleanupStateError, match="approval_expired"):
        await jobs.enqueue(factory, owner, plan(owner), now=STAMP + offset)


@pytest.mark.parametrize("now", [float("nan"), float("inf"), -1, True, "bad"])
async def test_invalid_clock_cannot_enqueue_or_claim(queue, now):
    factory, owner, _other, _engine = queue
    with pytest.raises(jobs.CleanupStateError, match="invalid_cleanup_time"):
        await jobs.enqueue(factory, owner, plan(owner), now=now)
    with pytest.raises(jobs.CleanupStateError, match="invalid_cleanup_time"):
        await jobs.claim(factory, now=now)


async def test_one_open_job_per_owner_is_enforced_even_for_concurrent_enqueues(queue):
    factory, owner, other, _engine = queue

    async def create(scope):
        try:
            return await jobs.enqueue(factory, owner, scope, now=STAMP)
        except jobs.CleanupStateError as error:
            return str(error)

    results = await asyncio.gather(create(plan(owner)), create(plan(owner)))
    assert results.count("cleanup_already_open") == 1
    identity = next(value for value in results if value != "cleanup_already_open")
    assert await jobs.enqueue(factory, other, plan(other), now=STAMP) != identity
    await jobs.cancel(factory, owner, identity)
    assert await jobs.enqueue(factory, owner, plan(owner), now=STAMP) != identity


async def test_concurrent_claims_take_each_job_once(queue):
    factory, owner, other, _engine = queue
    identities = {await jobs.enqueue(factory, user, plan(user), now=STAMP)
                  for user in (owner, other)}
    claims = await asyncio.gather(*(jobs.claim(factory, now=STAMP) for _ in range(4)))
    taken = [item for item in claims if item is not None]
    assert len(taken) == 2 and {item["id"] for item in taken} == identities
    assert all(item["phase"] == "running" and item["attempt"] == 1 for item in taken)


async def test_sql_checkpoint_commits_and_rolls_back_with_synthetic_content_removal(queue):
    factory, owner, _other, _engine = queue
    _scope, lease = await enqueue_claim(queue, external=False)
    async with factory() as db:
        memory = LongTermMemory(user_id=owner, kind="fact", content=SENTINEL,
                                normalized_hash="synthetic")
        db.add(memory)
        await db.commit()
        memory_id = memory.id
    async with factory() as db:
        await jobs.mark_started(db, *lease_args(lease), now=STAMP)
        await db.execute(delete(LongTermMemory).where(LongTermMemory.id == memory_id))
        await jobs.mark_sql_done(db, *lease_args(lease), now=STAMP)
        await db.rollback()
    async with factory() as db:
        assert await db.get(LongTermMemory, memory_id) is not None
        row = await db.get(CleanupJob, lease["id"])
        assert row.critical_started_at is None and row.sql_completed_at is None
        await jobs.mark_started(db, *lease_args(lease), now=STAMP)
        await db.execute(delete(LongTermMemory).where(LongTermMemory.id == memory_id))
        await jobs.mark_sql_done(db, *lease_args(lease), now=STAMP)
        await db.commit()
    async with factory() as db:
        assert await db.get(LongTermMemory, memory_id) is None
        assert (await db.get(CleanupJob, lease["id"])).sql_completed_at is not None
        await jobs.finish(db, *lease_args(lease), now=STAMP)
        await db.commit()
    assert (await jobs.status(factory, owner, lease["id"]))["status"] == "succeeded"


async def test_exact_progress_survives_reopen_and_only_remaining_references_resume(queue):
    factory, owner, _other, engine = queue
    scope, first = await enqueue_claim(queue)
    async with factory() as db:
        with pytest.raises(jobs.CleanupStateError, match="not_finished"):
            await jobs.finish(db, *lease_args(first), now=STAMP)
        with pytest.raises(jobs.CleanupStateError, match="state_conflict"):
            await jobs.record_purge(db, *lease_args(first), scope.external[0], now=STAMP)
        await db.rollback()
        await jobs.mark_sql_done(db, *lease_args(first), now=STAMP)
        await jobs.record_purge(db, *lease_args(first), scope.external[0], now=STAMP)
        await db.commit()
    # Dispose/reopen the actual database connections, not an in-memory fake.
    await engine.dispose()
    second = await jobs.claim(factory, now=STAMP + 121)
    assert second["phase"] == "purging" and second["attempt"] == 2
    assert json.loads(second["remaining_json"]) == [scope.external[1].model_dump()]
    async with factory() as db:
        with pytest.raises(jobs.CleanupStateError, match="reference_not_pending"):
            await jobs.record_purge(db, *lease_args(second), scope.external[0], now=STAMP + 121)
        with pytest.raises(jobs.CleanupStateError, match="not_finished"):
            await jobs.finish(db, *lease_args(second), now=STAMP + 121)
        foreign = jobs.PurgeReference(kind="agent_memories", owner_id="foreign-owner",
                                      object_id="synthetic-memory")
        with pytest.raises(jobs.CleanupStateError, match="state_conflict"):
            await jobs.record_purge(db, *lease_args(second), foreign, now=STAMP + 121)
        await db.rollback()
        await jobs.record_purge(db, *lease_args(second), scope.external[1], now=STAMP + 121)
        await jobs.finish(db, *lease_args(second), now=STAMP + 121)
        await db.commit()
    public = await jobs.status(factory, owner, first["id"])
    assert public["status"] == "succeeded" and public["remaining_count"] == 0
    assert public["completed_count"] == 2
    assert await jobs.claim(factory, now=STAMP + 242) is None


async def test_expired_worker_cannot_checkpoint_or_finish_after_reclaim(queue):
    factory, _owner, _other, _engine = queue
    scope, first = await enqueue_claim(queue)
    second = await jobs.claim(factory, now=STAMP + 121)
    assert second["token"] != first["token"] and second["attempt"] == 2
    async with factory() as db:
        for action in (
            lambda: jobs.mark_started(db, *lease_args(first), now=STAMP),
            lambda: jobs.mark_sql_done(db, *lease_args(first), now=STAMP),
            lambda: jobs.record_purge(db, *lease_args(first), scope.external[0], now=STAMP),
            lambda: jobs.finish(db, *lease_args(first), now=STAMP),
            lambda: jobs.fail(db, *lease_args(first), "storage_unavailable", now=STAMP),
        ):
            with pytest.raises(jobs.CleanupLeaseLost):
                await action()
            await db.rollback()


async def test_actual_update_is_fenced_if_claim_changes_after_sqlite_read(queue, monkeypatch):
    factory, _owner, _other, _engine = queue
    _scope, first = await enqueue_claim(queue, external=False)
    read, proceed = asyncio.Event(), asyncio.Event()
    original = jobs.leased_row

    async def paused_read(*args, **kwargs):
        row = await original(*args, **kwargs)
        read.set()
        await proceed.wait()
        return row

    monkeypatch.setattr(jobs, "leased_row", paused_read)

    async def outdated_worker():
        async with factory() as db:
            try:
                with pytest.raises(jobs.CleanupLeaseLost):
                    await jobs.mark_sql_done(db, *lease_args(first), now=STAMP)
            finally:
                await db.rollback()

    old_worker = asyncio.create_task(outdated_worker())
    try:
        await asyncio.wait_for(read.wait(), timeout=3)
        second = await jobs.claim(factory, now=STAMP + 121)
        assert second["attempt"] == 2
    finally:
        proceed.set()
    await asyncio.wait_for(old_worker, timeout=3)
    async with factory() as db:
        assert (await db.get(CleanupJob, first["id"])).sql_completed_at is None


async def test_retry_limit_manual_retry_and_cancel_do_not_expand_or_reset_scope(queue):
    factory, owner, other, _engine = queue
    scope, first = await enqueue_claim(queue)
    async with factory() as db:
        await jobs.mark_sql_done(db, *lease_args(first), now=STAMP)
        await jobs.record_purge(db, *lease_args(first), scope.external[0], now=STAMP)
        await db.commit()
    assert (await jobs.claim(factory, now=STAMP + 121))["attempt"] == 2
    assert (await jobs.claim(factory, now=STAMP + 242))["attempt"] == 3
    assert await jobs.claim(factory, now=STAMP + 363) is None
    state = await jobs.status(factory, owner, first["id"])
    assert state["status"] == "needs_attention" and state["error_code"] == "retry_limit"
    assert state["completed_count"] == 1 and state["remaining_count"] == 1
    with pytest.raises(jobs.CleanupStateError, match="retry_state_conflict"):
        await jobs.retry(factory, other, first["id"])
    with pytest.raises(jobs.CleanupStateError, match="cancel_state_conflict"):
        await jobs.cancel(factory, owner, first["id"])
    await jobs.retry(factory, owner, first["id"])
    resumed = await jobs.claim(factory, now=STAMP + 364)
    assert resumed["phase"] == "purging" and resumed["attempt"] == 1
    assert resumed["plan_json"] == first["plan_json"]
    assert json.loads(resumed["remaining_json"]) == [scope.external[1].model_dump()]


async def test_cancel_only_before_effects_and_fail_accepts_only_safe_codes(queue):
    factory, owner, other, _engine = queue
    scope = plan(owner)
    identity = await jobs.enqueue(factory, owner, scope, now=STAMP)
    with pytest.raises(jobs.CleanupStateError, match="cancel_state_conflict"):
        await jobs.cancel(factory, other, identity)
    lease = await jobs.claim(factory, now=STAMP)
    with pytest.raises(jobs.CleanupStateError, match="cancel_state_conflict"):
        await jobs.cancel(factory, owner, identity)
    async with factory() as db:
        with pytest.raises(jobs.CleanupStateError, match="unsafe_cleanup_error_code"):
            await jobs.fail(db, *lease_args(lease), SENTINEL, now=STAMP)
        await jobs.fail(db, *lease_args(lease), "owner_busy", now=STAMP)
        await db.commit()
    await jobs.cancel(factory, owner, identity)
    assert (await jobs.status(factory, owner, identity))["status"] == "cancelled"
    assert await jobs.claim(factory, now=STAMP + 121) is None
    assert await jobs.enqueue(factory, owner, scope, now=STAMP + 601) == identity


@pytest.mark.parametrize("damage", ["missing", "extra", "overlap", "duplicate", "hash",
                                    "owner", "approval", "json"])
async def test_corrupt_progress_never_claims_success_and_does_not_starve_other_owner(queue, damage):
    factory, owner, other, _engine = queue
    scope = plan(owner)
    identity = await jobs.enqueue(factory, owner, scope, now=STAMP)
    next_id = await jobs.enqueue(factory, other, plan(other), now=STAMP + 1)
    async with factory() as db:
        row = await db.get(CleanupJob, identity)
        refs = [item.model_dump() for item in scope.external]
        changes = {
            "missing": {"remaining_json": "[]"},
            "extra": {"remaining_json": json.dumps(refs + [{
                "kind": "pdf", "owner_id": owner, "object_id": "not-approved"}])},
            "overlap": {"completed_json": json.dumps(refs[:1])},
            "duplicate": {"remaining_json": json.dumps(refs + refs[:1])},
            "hash": {"plan_hash": "0" * 64},
            "owner": {"user_id": other},
            "approval": {"approval_id": "a" * 36},
            "json": {"remaining_json": "not-json"},
        }[damage]
        # Owner corruption would hit the one-open-per-owner unique index if the
        # other job were already queued; use a third synthetic identity instead.
        if damage == "owner":
            third = User(email="third@example.invalid", display_name="Synthetic C")
            db.add(third)
            await db.flush()
            changes["user_id"] = third.id
        await db.execute(update(CleanupJob).where(CleanupJob.id == identity).values(**changes))
        await db.commit()
        assert row.id == identity
    assert await jobs.claim(factory, now=STAMP + 1) is None
    async with factory() as db:
        bad = await db.get(CleanupJob, identity)
        assert bad.status == "needs_attention" and bad.error_code == "checkpoint_invalid"
        assert bad.sql_completed_at is None
    assert (await jobs.claim(factory, now=STAMP + 1))["id"] == next_id


def test_scope_rejects_duplicate_foreign_new_content_and_path_injection():
    scope = plan("synthetic-owner")
    data = scope.model_dump(mode="json")
    invalid = [data | {"external": [*data["external"], data["external"][0]]},
               data | {"external": [{"kind": "pdf", "owner_id": "other",
                                     "object_id": "synthetic"}]},
               data | {"snapshot": data["snapshot"] | {"cutoff": NOW.isoformat()}},
               data | {"snapshot": data["snapshot"] | {"items": [
                   data["snapshot"]["items"][0] | {"changed_at": NOW.isoformat()}]}},
               data | {"snapshot": data["snapshot"] | {"items": data["snapshot"]["items"] * 2}}]
    for value in invalid:
        with pytest.raises(ValueError):
            jobs.CleanupPlan.model_validate(value)
    for value in ("../other", "a/b", "a\\b", "..", "é", "a" * 65):
        with pytest.raises(ValueError):
            jobs.PurgeReference(kind="pdf", owner_id="synthetic-owner", object_id=value)
    # A hash records metadata integrity, never proves physical-file deletion.
    body, digest = jobs._serialize(scope)
    assert hashlib.sha256(body.encode()).hexdigest() == digest
