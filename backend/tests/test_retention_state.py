"""Isolated native/relational SQL payload removal; never Google or live data."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services import operations, relational_operations, relational_skills, skills
from app.services.durable_evaluation import EvaluationQueue
from app.services.operations import OperationStore
from app.services.relational_evaluation import RelationalEvaluationQueue
from app.services.relational_operations import RelationalOperationStore
from app.services.relational_skills import RelationalSkillStore
from app.services.retention_policy import (
    REQUIRED_INVENTORIES,
    RetentionPolicy,
    RetentionPolicyError,
)
from app.services.retention_state import ENTITIES, purge_state, state_inventory
from app.services.skills import SkillSpec, SkillStore
from app.tools.contracts import ToolError

OLD = datetime(2026, 9, 1, 12, tzinfo=UTC)
NOW = OLD + timedelta(days=45)
BODY = "SYNTHETIC_PRIVATE_BODY_NOT_FROM_A_USER"


def spec(name="synthetic_report"):
    return SkillSpec(name=name, title="Synthetic report", description=BODY,
                     goal="Summarize synthetic notes", procedure=["Check selected sources"],
                     output_format="Short report")


@pytest.fixture(params=["native", "relational"])
async def stores(tmp_path, monkeypatch, request):
    clock = [OLD.timestamp()]
    clock_api = SimpleNamespace(time=lambda: clock[0])
    for module in (operations, relational_operations, skills, relational_skills):
        monkeypatch.setattr(module, "time", clock_api)
    native = request.param == "native"
    sync_engine = None
    if native:
        op = OperationStore(tmp_path / "operations.db")
        queue = EvaluationQueue(tmp_path)
        skill = SkillStore(tmp_path)
        paths = {"operations": op.path, "evaluation_jobs": queue.path,
                 "skills": tmp_path / "skills.db"}
    else:
        path = tmp_path / "state.db"
        sync_engine = create_engine(f"sqlite:///{path}")
        RelationalOperationStore.create_schema(sync_engine)
        RelationalEvaluationQueue.create_schema(sync_engine)
        RelationalSkillStore.create_schema(sync_engine)
        op, queue, skill = (RelationalOperationStore(sync_engine),
                            RelationalEvaluationQueue(sync_engine),
                            RelationalSkillStore(sync_engine))
        paths = dict.fromkeys(ENTITIES, path)
    engines = {path: create_async_engine(f"sqlite+aiosqlite:///{path}")
               for path in set(paths.values())}
    factories = {entity: async_sessionmaker(engines[path], expire_on_commit=False)
                 for entity, path in paths.items()}
    try:
        yield SimpleNamespace(op=op, queue=queue, skill=skill, clock=clock, native=native,
                              factories=factories, sync_engine=sync_engine)
    finally:
        for engine in engines.values():
            await engine.dispose()
        if sync_engine is not None:
            sync_engine.dispose()


def complete_operation(stores, owner="owner-a", key="synthetic-request"):
    row = stores.op.prepare(owner, key, "docs_create", {"title": BODY})
    stores.op.claim(owner, row["id"], row["digest"])
    stores.op.checkpoint(owner, row["id"], "synthetic-provider-resource-id")
    stores.op.finish(owner, row["id"], {"verified": True, "body": BODY})
    return row


def complete_evaluation(stores, owner="owner-a"):
    stamp = stores.clock[0]
    identity = stores.queue.enqueue(owner, stamp)
    lease = stores.queue.claim(stamp)
    assert lease["id"] == identity
    stores.queue.checkpoint(identity, {"synthetic": {"passed": 1}}, stamp,
                            attempt=lease["attempts"])
    stores.queue.finish(identity, "completed", attempt=lease["attempts"], now=stamp)
    return identity


async def inventory(stores, entity, owner="owner-a"):
    async with stores.factories[entity]() as db:
        return await state_inventory(db, owner, entities={entity}, native=stores.native)


def approval(candidates, owner="owner-a"):
    policy = RetentionPolicy("synthetic-state-retention-signing-key-not-production")
    coverage = dict.fromkeys(REQUIRED_INVENTORIES, True)
    preview = policy.prepare(owner_id=owner, candidates=list(candidates),
                             inventories=coverage, now=NOW)
    return policy.validate(token=preview.token, owner_id=owner, current=list(candidates),
                           inventories=coverage, now=NOW).items


async def test_state_inventory_has_real_clocks_owner_scope_and_no_payloads(stores):
    op = complete_operation(stores)
    job = complete_evaluation(stores)
    skill = stores.skill.save("owner-a", spec())
    complete_operation(stores, "owner-b")
    complete_evaluation(stores, "owner-b")
    stores.skill.save("owner-b", spec())
    stores.clock[0] = NOW.timestamp()
    stores.op.list_status("owner-a")
    stores.op.archive("owner-a", op["id"])
    stores.skill.archive("owner-a", skill["id"])
    stores.queue.get("owner-a", job)
    stores.queue.recent("owner-a")
    for entity in ENTITIES:
        result = await inventory(stores, entity)
        assert len(result.candidates) == 1 and not result.owner_busy
        assert result.candidates[0].changed_at == OLD
        assert BODY not in repr(result) and "owner-b" not in repr(result)
        assert await inventory(stores, entity) == result


async def test_purge_keeps_fresh_other_owner_and_external_replay_barrier(stores):
    op = complete_operation(stores)
    job = complete_evaluation(stores)
    old_skill = stores.skill.save("owner-a", spec())
    other = complete_operation(stores, "owner-b")
    other_job = complete_evaluation(stores, "owner-b")
    other_skill = stores.skill.save("owner-b", spec())
    pending = stores.op.prepare("owner-a", "never-claimed", "docs_create", {"title": BODY})
    selected = {entity: approval((await inventory(stores, entity)).candidates)
                for entity in ENTITIES}
    stores.clock[0] = NOW.timestamp()
    fresh_skill = stores.skill.save("owner-a", spec("fresh_synthetic_report"))
    counts = {"deleted": 0, "redacted": 0}
    for entity in sorted(ENTITIES):
        async with stores.factories[entity]() as db:
            result = await purge_state(db, "owner-a", selected[entity], entities={entity},
                                       native=stores.native, now=NOW.timestamp())
            await db.commit()
            for key, count in result.items():
                counts[key] += count
    assert counts == {"deleted": 2, "redacted": 2}
    assert stores.queue.get("owner-a", job) is None
    assert stores.queue.get("owner-b", other_job) is not None
    assert stores.skill.get("owner-b", other_skill["id"])["id"] == other_skill["id"]
    assert stores.skill.get("owner-a", fresh_skill["id"])["id"] == fresh_skill["id"]
    with pytest.raises(ToolError, match="Không tìm thấy"):
        stores.skill.get("owner-a", old_skill["id"])
    own = stores.op.get("owner-a", op["id"])
    assert own["spec"] == "{}" and own["result"] is None and own["error_code"] is None
    assert own["resource_id"] == "synthetic-provider-resource-id"
    assert own["digest"] == op["digest"] and own["request_key"] == op["request_key"]
    assert BODY not in str(own) and BODY in str(stores.op.get("owner-b", other["id"]))
    assert stores.op.get("owner-a", pending["id"])["state"] == "expired"
    assert stores.op.prepare("owner-a", "synthetic-request", "docs_create", {"title": BODY})[
        "id"] == op["id"]
    with pytest.raises(ToolError) as replay:
        stores.op.claim("owner-a", op["id"], op["digest"])
    assert replay.value.code == "operation_already_claimed"
    assert not (await inventory(stores, "operations")).candidates


async def test_purge_rollback_keeps_payloads_and_clock_together(stores):
    row = complete_operation(stores)
    before = await inventory(stores, "operations")
    async with stores.factories["operations"]() as db:
        assert (await purge_state(db, "owner-a", approval(before.candidates),
                                  entities={"operations"}, native=stores.native,
                                  now=NOW.timestamp()))["redacted"] == 1
        await db.rollback()
    assert BODY in stores.op.get("owner-a", row["id"])["result"]
    assert await inventory(stores, "operations") == before


async def test_wrong_owner_stale_payload_and_active_work_cannot_be_purged(stores):
    row = complete_operation(stores)
    before = await inventory(stores, "operations")
    chosen = approval(before.candidates)
    async with stores.factories["operations"]() as db:
        with pytest.raises(RetentionPolicyError, match="preview_changed"):
            await purge_state(db, "owner-b", chosen, entities={"operations"},
                              native=stores.native, now=NOW.timestamp())
        await db.rollback()
    # Mirror an older writer: no companion-clock write. A read must refuse the
    # mismatch, not silently give the newly changed body its older age.
    async with stores.factories["operations"]() as db:
        await db.execute(text("UPDATE operations SET result=:body WHERE id=:id"),
                         {"body": '"SYNTHETIC_CHANGED_BODY"', "id": row["id"]})
        await db.commit()
    with pytest.raises(RetentionPolicyError, match="clock_mismatch"):
        await inventory(stores, "operations")
    stores.clock[0] = NOW.timestamp()
    if stores.native:
        stores.op.reconcile_content_clocks()
    else:
        RelationalOperationStore.create_schema(stores.sync_engine)
    assert (await inventory(stores, "operations")).candidates[0].changed_at == NOW
    async with stores.factories["operations"]() as db:
        with pytest.raises(RetentionPolicyError, match="preview_changed"):
            await purge_state(db, "owner-a", chosen, entities={"operations"},
                              native=stores.native, now=NOW.timestamp())
        await db.rollback()
    active = stores.op.prepare("owner-a", str(uuid4()), "docs_create", {"title": "Synthetic"})
    stores.op.claim("owner-a", active["id"], active["digest"])
    assert (await inventory(stores, "operations")).owner_busy


async def test_completed_evaluation_is_not_deleted_by_another_enqueue(stores):
    old_job = complete_evaluation(stores)
    stores.clock[0] = NOW.timestamp()
    stores.queue.enqueue("owner-b", stores.clock[0])
    assert stores.queue.get("owner-a", old_job) is not None
    assert (await inventory(stores, "evaluation_jobs", "owner-b")).owner_busy


async def test_clock_owner_corruption_rolls_back_new_result_and_cannot_be_inventory(stores):
    row = stores.op.prepare("owner-a", "corruption-case", "docs_create", {"title": BODY})
    stores.op.claim("owner-a", row["id"], row["digest"])
    async with stores.factories["operations"]() as db:
        await db.execute(text("UPDATE state_content_clocks SET user_id='owner-b' "
                              "WHERE entity='operations' AND record_id=:id"), {"id": row["id"]})
        await db.commit()
    with pytest.raises(RetentionPolicyError, match="clock_mismatch"):
        stores.op.finish("owner-a", row["id"], {"body": "NEW_BODY_MUST_ROLL_BACK"})
    assert stores.op.get("owner-a", row["id"])["result"] is None
    assert stores.op.get("owner-a", row["id"])["state"] == "running"
    with pytest.raises(RetentionPolicyError, match="clock_mismatch"):
        await inventory(stores, "operations")


async def test_missing_table_is_not_an_empty_inventory(stores):
    async with stores.factories["operations"]() as db:
        if stores.native:
            with pytest.raises(RetentionPolicyError, match="schema_incomplete"):
                await state_inventory(db, "owner-a", entities=ENTITIES, native=True)
        else:
            result = await state_inventory(db, "owner-a", entities=ENTITIES)
            assert result.candidates == () and not result.owner_busy
