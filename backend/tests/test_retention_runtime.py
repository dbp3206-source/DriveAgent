"""Actual isolated native-store discovery, SDK reset and interrupted cleanup.

No model, OAuth, provider request or configured personal database is used. Every
store path is asserted inside pytest's disposable directory before opening it.
"""

import json
import os
import sqlite3
from contextlib import asynccontextmanager, closing
from datetime import timedelta
from typing import TypedDict
from uuid import UUID, uuid4

import pytest
from google.adk.events import Event
from google.adk.sessions import DatabaseSessionService
from google.genai import types
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from test_retention_coordinator import BODY, NOW, SECRET
from test_retention_coordinator import runtime as runtime

from app.db.models import CleanupJob, GraphCheckpoint, LongTermMemory, Message
from app.services import cleanup_jobs
from app.services.owner_admission import OwnerAdmission
from app.services.relational_evaluation import RelationalEvaluationQueue
from app.services.relational_operations import RelationalOperationStore
from app.services.relational_skills import RelationalSkillStore
from app.services.retention_coordinator import RetentionCoordinator
from app.services.retention_policy import RetentionPolicyError
from app.services.retention_runtime import RetentionRuntime, existing_file


def assert_isolated(data):
    root = data.tmp_path
    assert root.is_absolute()
    assert data.settings.state_dir == root
    assert data.settings.data_dir == root
    expected_url = f"sqlite+aiosqlite:///{(root / 'app.db').as_posix()}"
    assert data.settings.resolved_database_url == expected_url
    assert data.settings.relational_state_url is None
    assert data.settings.resolved_qdrant_path.is_relative_to(root)
    assert data.storage.root.is_relative_to(root)
    assert data.stores.backup_root.is_relative_to(root)


def synthetic_uuid6(stamp, sequence):
    gregorian_ticks = 0x01B21DD213814000 + int(stamp.timestamp() * 10_000_000) + sequence
    time_high_mid = (gregorian_ticks >> 12) & 0xFFFFFFFFFFFF
    time_low_version = gregorian_ticks & 0x0FFF
    value = (time_high_mid << 80) | (6 << 76) | (time_low_version << 64)
    value |= (sequence & 0x3FFF) << 48
    value |= 0b10 << 62
    value |= 0x123456789ABC
    return str(UUID(int=value))


async def age_langgraph_thread(saver, thread_id, stamp):
    async with saver.conn.execute(
        "SELECT checkpoint_id FROM checkpoints WHERE thread_id=? ORDER BY checkpoint_id",
        (thread_id,),
    ) as cursor:
        old_ids = [row[0] for row in await cursor.fetchall()]
    assert old_ids, "fixture must contain real LangGraph checkpoints"
    replacements = {
        old_id: synthetic_uuid6(stamp + timedelta(microseconds=index), index)
        for index, old_id in enumerate(old_ids)
    }
    for old_id, new_id in replacements.items():
        await saver.conn.execute(
            "UPDATE checkpoints SET checkpoint_id=? WHERE thread_id=? AND checkpoint_id=?",
            (new_id, thread_id, old_id),
        )
        await saver.conn.execute(
            "UPDATE writes SET checkpoint_id=? WHERE thread_id=? AND checkpoint_id=?",
            (new_id, thread_id, old_id),
        )
    for old_id, new_id in replacements.items():
        await saver.conn.execute(
            "UPDATE checkpoints SET parent_checkpoint_id=? "
            "WHERE thread_id=? AND parent_checkpoint_id=?",
            (new_id, thread_id, old_id),
        )
    await saver.conn.commit()


class CounterState(TypedDict):
    value: int


@asynccontextmanager
async def native_contexts(data):
    assert_isolated(data)
    adk_path = data.tmp_path / "adk_sessions.db"
    graph_path = data.tmp_path / "langgraph_checkpoints.db"
    assert adk_path.is_relative_to(data.tmp_path) and not adk_path.exists()
    assert graph_path.is_relative_to(data.tmp_path) and not graph_path.exists()
    service = DatabaseSessionService(db_url=f"sqlite+aiosqlite:///{adk_path}")
    try:
        sessions = {}
        for owner in (data.owner, data.other):
            session = await service.create_session(
                app_name="drive_agent", user_id=owner, session_id=str(uuid4()),
                state={"derived_copy": BODY, "user:language": "Vietnamese"},
            )
            await service.append_event(session, Event(author="assistant", content=types.Content(
                role="model", parts=[types.Part(text=BODY)],
            )))
            sessions[owner] = session.id
        async with AsyncSqliteSaver.from_conn_string(str(graph_path)) as saver:
            builder = StateGraph(CounterState)
            builder.add_node("increment", lambda state: {"value": state["value"] + 1})
            builder.add_edge(START, "increment")
            builder.add_edge("increment", END)
            graph = builder.compile(checkpointer=saver)
            configs = {}
            for owner in (data.owner, data.other):
                config = {"configurable": {"thread_id": f"{owner}:synthetic-session"}}
                assert (await graph.ainvoke({"value": 4}, config))["value"] == 5
                configs[owner] = config
            yield service, sessions, saver, configs
    finally:
        await service.close()


async def assert_canonical_and_foreign_kept(data):
    async with data.factory() as db:
        assert await db.get(LongTermMemory, data.old) is None
        assert await db.get(LongTermMemory, data.fresh) is not None
        assert await db.get(LongTermMemory, data.foreign) is not None
        assert await db.scalar(select(Message.content).where(Message.user_id == data.owner)) == (
            "FRESH_CHAT")
        assert await db.scalar(select(func.count()).select_from(GraphCheckpoint).where(
            GraphCheckpoint.user_id == data.owner)) == 0
        assert await db.scalar(select(func.count()).select_from(GraphCheckpoint).where(
            GraphCheckpoint.user_id == data.other)) == 1


async def test_actual_runtime_discovers_resets_both_sdks_and_preserves_canonical_work(runtime):
    data = runtime
    async with native_contexts(data) as (adk, sessions, saver, configs):
        async with data.factory() as db:
            inventory = await data.stores.inventory(db, data.owner)
        assert {store.name for store in inventory.stores} == {"graph", "adk_local", "langgraph"}
        assert inventory.contexts["adk_local"].row_count == 3
        assert inventory.contexts["langgraph"].row_count > 2
        expected = sum(context.row_count for context in inventory.contexts.values())
        preview = await data.coordinator.preview(data.owner)
        assert preview["selected_count"] == 1  # Only the expired canonical note.
        assert preview["reset_context_count"] == expected
        assert BODY not in json.dumps(preview, default=str)
        identity = await data.coordinator.confirm(data.owner, preview["token"])
        assert await data.coordinator.execute_one()
        status = await cleanup_jobs.status(data.factory, data.owner, identity)
        assert status["status"] == "succeeded" and status["remaining_count"] == 0
        assert await adk.get_session(app_name="drive_agent", user_id=data.owner,
                                      session_id=sessions[data.owner]) is None
        preserved = await adk.get_session(app_name="drive_agent", user_id=data.other,
                                          session_id=sessions[data.other])
        assert len(preserved.events) == 1
        assert preserved.state["derived_copy"] == BODY
        assert await saver.aget_tuple(configs[data.owner]) is None
        assert (await saver.aget_tuple(configs[data.other])).checkpoint[
            "channel_values"]["value"] == 5
        await assert_canonical_and_foreign_kept(data)


async def test_adk_change_after_preview_rejects_cleanup_without_partial_deletion(runtime):
    data = runtime
    async with native_contexts(data) as (adk, sessions, saver, configs):
        preview = await data.coordinator.preview(data.owner)
        current = await adk.get_session(app_name="drive_agent", user_id=data.owner,
                                         session_id=sessions[data.owner])
        await adk.append_event(current, Event(author="assistant", content=types.Content(
            role="model", parts=[types.Part(text="NEW_CANARY_AFTER_PREVIEW")],
        )))
        with pytest.raises(RetentionPolicyError, match="retention_preview_changed"):
            await data.coordinator.confirm(data.owner, preview["token"])
        async with data.factory() as db:
            assert await db.get(LongTermMemory, data.old) is not None
            assert await db.scalar(select(func.count()).select_from(CleanupJob)) == 0
        assert len((await adk.get_session(app_name="drive_agent", user_id=data.owner,
                                          session_id=sessions[data.owner])).events) == 2
        assert await saver.aget_tuple(configs[data.owner]) is not None


async def test_native_sdk_reset_resumes_after_committed_reset_lost_receipt_and_runtime_restart(
    runtime, monkeypatch,
):
    data = runtime
    async with native_contexts(data) as (adk, sessions, saver, configs):
        preview = await data.coordinator.preview(data.owner)
        identity = await data.coordinator.confirm(data.owner, preview["token"])
        original = cleanup_jobs.record_critical_step

        async def lose_first_adk_receipt(*args, **kwargs):
            if args[4].kind == "adk_context":
                raise RuntimeError("SYNTHETIC_INTERRUPTION_AFTER_COMMIT")
            return await original(*args, **kwargs)

        monkeypatch.setattr(cleanup_jobs, "record_critical_step", lose_first_adk_receipt)
        assert await data.coordinator.execute_one()
        status = await cleanup_jobs.status(data.factory, data.owner, identity)
        assert status["status"] == "needs_attention" and not status["sql_completed"]
        assert status["completed_count"] == 0
        assert await adk.get_session(app_name="drive_agent", user_id=data.owner,
                                      session_id=sessions[data.owner]) is None
        assert await saver.aget_tuple(configs[data.owner]) is not None
        async with data.factory() as db:
            assert await db.get(LongTermMemory, data.old) is not None
        monkeypatch.setattr(cleanup_jobs, "record_critical_step", original)
        await data.stores.close()
        reopened = RetentionRuntime(data.settings, data.storage, data.stores.vectors.store,
                                    backup_root=data.stores.backup_root)
        resumed = RetentionCoordinator(data.factory, OwnerAdmission(data.factory), reopened,
                                       SECRET, clock=lambda: NOW.timestamp())
        try:
            await cleanup_jobs.retry(data.factory, data.owner, identity)
            assert await resumed.execute_one()
            status = await cleanup_jobs.status(data.factory, data.owner, identity)
            assert status["status"] == "succeeded" and status["remaining_count"] == 0
            assert await saver.aget_tuple(configs[data.owner]) is None
            assert await adk.get_session(app_name="drive_agent", user_id=data.other,
                                          session_id=sessions[data.other]) is not None
            assert await saver.aget_tuple(configs[data.other]) is not None
            await assert_canonical_and_foreign_kept(data)
        finally:
            await reopened.close()


async def test_langgraph_retention_uses_owner_checkpoint_age_not_shared_file_mtime(runtime):
    from app.services.retention_context import langgraph_context_oldest_at

    data = runtime
    async with native_contexts(data) as (_adk, _sessions, saver, configs):
        old_stamp = NOW - timedelta(days=40)
        await age_langgraph_thread(saver, configs[data.owner]["configurable"]["thread_id"],
                                  old_stamp)
        graph_path = data.tmp_path / "langgraph_checkpoints.db"
        assert graph_path.stat().st_mtime > (NOW - timedelta(days=30)).timestamp()
        async with data.factory() as db:
            store = next(item for item in await data.stores.stores(db)
                         if item.name == "langgraph")
            async with store.session(db) as langgraph_db:
                owner_age = await langgraph_context_oldest_at(langgraph_db, data.owner)
                other_age = await langgraph_context_oldest_at(langgraph_db, data.other)
            inventory = await data.stores.inventory(db, data.owner)
        assert owner_age is not None and owner_age <= NOW - timedelta(days=40)
        assert other_age is not None and other_age > NOW - timedelta(days=30)
        graph_candidate = next(item for item in inventory.candidates
                               if item.record_id == "derived_context:langgraph")
        assert graph_candidate.changed_at == owner_age

        # A real coordinator preview now includes the aged owner context while
        # retaining canonical chat history and every other owner's context.
        preview = await data.coordinator.preview(data.owner)
        assert preview["counts"]["framework"] >= 1
        assert "synthetic-session" not in json.dumps(preview, default=str)
        identity = await data.coordinator.confirm(data.owner, preview["token"])
        assert await data.coordinator.execute_one()
        status = await cleanup_jobs.status(data.factory, data.owner, identity)
        assert status["status"] == "succeeded"
        assert await saver.aget_tuple(configs[data.owner]) is None
        assert await saver.aget_tuple(configs[data.other]) is not None
        await assert_canonical_and_foreign_kept(data)


@pytest.mark.parametrize("legacy", ["skills.db", "operations.db", "evaluation_jobs.db"])
async def test_relational_native_store_rejects_existing_inactive_legacy_copy(runtime, legacy):
    data = runtime
    assert_isolated(data)
    target = data.tmp_path / "state.db"
    legacy_path = data.tmp_path / legacy
    assert target.is_relative_to(data.tmp_path) and not target.exists()
    assert legacy_path.is_relative_to(data.tmp_path) and not legacy_path.exists()
    url = f"sqlite:///{target}"
    engine = create_engine(url)
    try:
        RelationalSkillStore.create_schema(engine)
        RelationalOperationStore.create_schema(engine)
        RelationalEvaluationQueue.create_schema(engine)
    finally:
        engine.dispose()
    settings = data.settings.model_copy(update={"relational_state_url": SecretStr(url)})
    stores = RetentionRuntime(settings, data.storage, data.stores.vectors.store,
                              backup_root=data.stores.backup_root)
    try:
        async with data.factory() as db:
            inventory = await stores.inventory(db, data.owner)
        assert {store.name for store in inventory.stores} == {"graph", "state"}
        assert next(item for item in inventory.bindings if item.name == "state").count == 0
        # It is an actual separate SQLite file, not a fake reported path.
        with closing(sqlite3.connect(legacy_path)) as old:
            old.execute("CREATE TABLE synthetic_legacy_copy (value TEXT)")
            old.execute("INSERT INTO synthetic_legacy_copy VALUES (?)", (BODY,))
            old.commit()
        async with data.factory() as db:
            with pytest.raises(RetentionPolicyError, match="legacy_store_not_reconciled"):
                await stores.inventory(db, data.owner)
        with closing(sqlite3.connect(legacy_path)) as old:
            assert old.execute("SELECT value FROM synthetic_legacy_copy").fetchone() == (BODY,)
    finally:
        await stores.close()


async def test_missing_optional_store_is_not_created_and_disappeared_store_cannot_reopen(runtime):
    data = runtime
    assert_isolated(data)
    missing = data.tmp_path / "adk_sessions.db"
    assert not missing.exists() and existing_file(missing) is False
    async with data.factory() as db:
        assert {store.name for store in await data.stores.stores(db)} == {"graph"}
    assert not missing.exists() and data.stores._engines == {}
    # Only this synthetic fixture file is moved, never a configured user file.
    with closing(sqlite3.connect(missing)) as connection:
        connection.execute("CREATE TABLE synthetic_metadata (id INTEGER)")
        connection.commit()
    store = data.stores._local("adk_local", "adk", missing)
    moved = data.tmp_path / "moved-synthetic-store.db"
    assert moved.is_relative_to(data.tmp_path) and not moved.exists()
    missing.rename(moved)
    async with data.factory() as db:
        with pytest.raises(RetentionPolicyError, match="retention_store_disappeared"):
            async with store.session(db):
                pytest.fail("Missing store must never produce a new session")
    assert moved.is_file() and not missing.exists()


async def test_local_hardlink_alias_is_rejected_before_runtime_engine_open(runtime):
    data = runtime
    assert_isolated(data)
    original = data.tmp_path / "synthetic-original.db"
    alias = data.tmp_path / "adk_sessions.db"
    assert original.is_relative_to(data.tmp_path) and alias.is_relative_to(data.tmp_path)
    assert not original.exists() and not alias.exists()
    with closing(sqlite3.connect(original)) as connection:
        connection.execute("CREATE TABLE synthetic_canary (id INTEGER)")
        connection.commit()
    try:
        os.link(original, alias)
    except OSError as error:
        pytest.skip(f"Hardlink fixture unsupported by this filesystem: {type(error).__name__}")
    async with data.factory() as db:
        with pytest.raises(RetentionPolicyError, match="retention_store_path_unsafe"):
            await data.stores.stores(db)
    assert data.stores._engines == {} and original.is_file() and alias.is_file()
