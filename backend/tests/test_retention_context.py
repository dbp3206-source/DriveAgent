"""Real SDK context stores and disposable app DBs; no model/provider/network."""

import json
import pickle
from types import SimpleNamespace
from typing import TypedDict
from uuid import uuid4

import pytest
from google.adk.events import Event
from google.adk.sessions import DatabaseSessionService
from google.genai import types
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, ChatSession, GraphCheckpoint, Message, User
from app.services.retention_context import (
    _graph_table,
    adk_context_inventory,
    graph_context_inventory,
    langgraph_context_inventory,
    langgraph_context_oldest_at,
    reset_adk_context,
    reset_graph_context,
    reset_langgraph_context,
)
from app.services.retention_framework import _tables
from app.services.retention_policy import RetentionPolicyError

OWNER = "synthetic-owner-a"
OTHER = "synthetic-owner-b"


@pytest.fixture
async def adk(tmp_path):
    service = DatabaseSessionService(db_url=f"sqlite+aiosqlite:///{tmp_path / 'adk-context.db'}")
    try:
        yield service
    finally:
        await service.close()


async def create_adk(service, owner=OWNER, *, app="drive_agent", shared=False):
    state = {"private": "SYNTHETIC_ADK_CONTEXT", "user:language": "Vietnamese"}
    if shared:
        state["app:canary"] = "SYNTHETIC_SHARED_CONTEXT"
    session = await service.create_session(app_name=app, user_id=owner, session_id=str(uuid4()),
                                           state=state)
    await service.append_event(session, Event(author="assistant", content=types.Content(
        role="model", parts=[types.Part(text="SYNTHETIC_ADK_EVENT")],
    )))
    return session


async def test_adk_inventory_is_readonly_deterministic_complete_and_content_free(adk):
    own = await create_adk(adk)
    await create_adk(adk, app="drive_compiler")
    other = await create_adk(adk, OTHER)
    async with async_sessionmaker(adk.db_engine)() as db:
        inventory = await adk_context_inventory(db, OWNER, namespace=None)
        assert inventory == await adk_context_inventory(db, OWNER, namespace=None)
        assert inventory.scope == "adk:local"
        assert inventory.row_count == 6
        assert inventory.table_counts == (("events", 2), ("sessions", 2), ("user_states", 2))
        assert all(secret not in repr(inventory) for secret in (
            "SYNTHETIC_ADK", own.id, other.id, "Vietnamese",
        ))
        assert not db.new and not db.dirty and not db.deleted
    assert (await adk.get_session(app_name="drive_agent", user_id=OWNER,
                                  session_id=own.id)).state["private"] == "SYNTHETIC_ADK_CONTEXT"


async def test_reset_adk_rolls_back_then_removes_all_fresh_owned_context_and_sdk_recreates(adk):
    own = await create_adk(adk)
    other = await create_adk(adk, OTHER)
    async with async_sessionmaker(adk.db_engine)() as db:
        inventory = await adk_context_inventory(db, OWNER, namespace=None)
    for commit in (False, True):
        async with async_sessionmaker(adk.db_engine)() as db:
            assert await reset_adk_context(db, OWNER, inventory.digest, namespace=None) == 3
            if commit:
                await db.commit()
            else:
                await db.rollback()
        current = await adk.get_session(app_name="drive_agent", user_id=OWNER, session_id=own.id)
        assert (current is None) is commit
        preserved = await adk.get_session(app_name="drive_agent", user_id=OTHER,
                                          session_id=other.id)
        assert preserved.state["private"] == "SYNTHETIC_ADK_CONTEXT"
        assert len(preserved.events) == 1
    async with async_sessionmaker(adk.db_engine)() as db:
        assert (await adk_context_inventory(db, OWNER, namespace=None)).row_count == 0
        assert await db.scalar(text("SELECT count(*) FROM app_states")) == 1
        assert await db.scalar(text("SELECT count(*) FROM adk_internal_metadata")) >= 1
    # Exercise the pinned SDK, not just an empty raw table. A recreated user and
    # even the former exact session ID can receive new events after reset.
    recreated = await adk.create_session(app_name="drive_agent", user_id=OWNER,
                                          session_id=own.id,
                                          state={"private": "FRESH_AFTER_CONTEXT_RESET"})
    await adk.append_event(recreated, Event(author="assistant", content=types.Content(
        role="model", parts=[types.Part(text="NEW_EVENT_AFTER_CONTEXT_RESET")],
    )))
    current = await adk.get_session(app_name="drive_agent", user_id=OWNER, session_id=own.id)
    assert current.state == {"private": "FRESH_AFTER_CONTEXT_RESET"}
    assert len(current.events) == 1


async def test_new_event_changed_state_or_wrong_owner_invalidates_whole_context_approval(adk):
    own = await create_adk(adk)
    await create_adk(adk, OTHER)
    async with async_sessionmaker(adk.db_engine)() as db:
        inventory = await adk_context_inventory(db, OWNER, namespace=None)
        with pytest.raises(RetentionPolicyError, match="preview_changed"):
            await reset_adk_context(db, OTHER, inventory.digest, namespace=None)
        await db.rollback()
        with pytest.raises(RetentionPolicyError, match="invalid_retention_context_digest"):
            await reset_adk_context(db, OWNER, "raw-user-content", namespace=None)
        await db.rollback()
    await adk.append_event(own, Event(author="assistant", content=types.Content(
        role="model", parts=[types.Part(text="NEW_EVENT_AFTER_PREVIEW")],
    )))
    async with async_sessionmaker(adk.db_engine)() as db:
        with pytest.raises(RetentionPolicyError, match="preview_changed"):
            await reset_adk_context(db, OWNER, inventory.digest, namespace=None)
        await db.rollback()
        changed = await adk_context_inventory(db, OWNER, namespace=None)
        tables = await db.run_sync(_tables, None)
        # A content change with the original row count and time is still caught.
        table = tables["user_states"]
        await db.execute(update(table).where(table.c.user_id == OWNER).values(
            state=json.dumps({"language": "SYNTHETIC_CHANGED_WITHOUT_CLOCK"}),
        ))
        await db.commit()
        with pytest.raises(RetentionPolicyError, match="preview_changed"):
            await reset_adk_context(db, OWNER, changed.digest, namespace=None)
        await db.rollback()
    assert len((await adk.get_session(app_name="drive_agent", user_id=OWNER,
                                     session_id=own.id)).events) == 2


async def test_shared_state_and_unknown_apps_fail_before_reset(adk):
    own = await create_adk(adk)
    async with async_sessionmaker(adk.db_engine)() as db:
        inventory = await adk_context_inventory(db, OWNER, namespace=None)
    await create_adk(adk, shared=True)
    async with async_sessionmaker(adk.db_engine)() as db:
        for action in (
            adk_context_inventory(db, OWNER, namespace=None),
            reset_adk_context(db, OWNER, inventory.digest, namespace=None),
        ):
            with pytest.raises(RetentionPolicyError, match="unattributed_framework_state"):
                await action
            await db.rollback()
    assert await adk.get_session(app_name="drive_agent", user_id=OWNER, session_id=own.id)


async def test_unknown_owned_app_empty_placeholders_namespace_and_owner(adk):
    await adk.create_session(app_name="drive_agent", user_id=OWNER, session_id=str(uuid4()))
    async with async_sessionmaker(adk.db_engine)() as db:
        inventory = await adk_context_inventory(db, OWNER, namespace=None)
        assert inventory.table_counts == (("events", 0), ("sessions", 1), ("user_states", 1))
        with pytest.raises(RetentionPolicyError, match="invalid_framework_namespace"):
            await adk_context_inventory(db, OWNER, namespace="public")
        with pytest.raises(RetentionPolicyError, match="invalid_retention_owner"):
            await adk_context_inventory(db, "", namespace=None)
    await create_adk(adk, app="unsupported-app")
    async with async_sessionmaker(adk.db_engine)() as db:
        with pytest.raises(RetentionPolicyError, match="unsupported_framework_app"):
            await reset_adk_context(db, OWNER, inventory.digest, namespace=None)
        await db.rollback()


@pytest.fixture
async def app_store(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'context-app.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        db.add_all([User(id=OWNER, email="a@example.invalid", display_name="A"),
                    User(id=OTHER, email="b@example.invalid", display_name="B")])
        await db.commit()
        db.add_all([
            ChatSession(id="canonical-chat", user_id=OWNER, title="Canonical recent work"),
            GraphCheckpoint(id="own-context", user_id=OWNER, thread_id=f"{OWNER}:canonical-chat",
                            state_json='{"canary":"SYNTHETIC_GRAPH_CONTEXT"}'),
            GraphCheckpoint(id="other-context", user_id=OTHER, thread_id=f"{OTHER}:other-chat",
                            state_json='{"canary":"OTHER_GRAPH_CONTEXT"}'),
        ])
        await db.commit()
        db.add(Message(id="canonical-message", session_id="canonical-chat", user_id=OWNER,
                       role="user", content="RECENT_CANONICAL_MESSAGE"))
        await db.commit()
    try:
        yield factory
    finally:
        await engine.dispose()


async def test_graph_reset_preserves_other_owner_and_canonical_messages(app_store):
    async with app_store() as db:
        inventory = await graph_context_inventory(db, OWNER)
        assert inventory.row_count == 1
        assert "SYNTHETIC_GRAPH_CONTEXT" not in repr(inventory)
        with pytest.raises(RetentionPolicyError, match="preview_changed"):
            await reset_graph_context(db, OTHER, inventory.digest)
        await db.rollback()
        assert await reset_graph_context(db, OWNER, inventory.digest) == 1
        await db.rollback()
        assert (await graph_context_inventory(db, OWNER)) == inventory
        assert await reset_graph_context(db, OWNER, inventory.digest) == 1
        await db.commit()
        assert (await graph_context_inventory(db, OWNER)).row_count == 0
        assert await db.scalar(select(func.count()).select_from(GraphCheckpoint).where(
            GraphCheckpoint.user_id == OTHER,
        )) == 1
        assert await db.get(ChatSession, "canonical-chat") is not None
        assert (await db.get(Message, "canonical-message")).content == "RECENT_CANONICAL_MESSAGE"


async def test_graph_new_content_with_same_count_and_timestamp_invalidates_digest(app_store):
    async with app_store() as db:
        inventory = await graph_context_inventory(db, OWNER)
        await db.execute(update(GraphCheckpoint).where(GraphCheckpoint.user_id == OWNER).values(
            state_json='{"canary":"CHANGED_GRAPH_CONTEXT"}',
        ))
        await db.commit()
        with pytest.raises(RetentionPolicyError, match="preview_changed"):
            await reset_graph_context(db, OWNER, inventory.digest)
        await db.rollback()
        assert (await graph_context_inventory(db, OWNER)).row_count == 1


async def test_database_errors_never_expose_driver_parameters_or_document_content(
    app_store, monkeypatch,
):
    async with app_store() as db:
        async def fail_stream(*_args, **_kwargs):
            raise OperationalError("SELECT private_content", {"private": "SYNTHETIC_PRIVATE"},
                                   RuntimeError("SYNTHETIC_PRIVATE_DRIVER_ERROR"))

        monkeypatch.setattr(db, "stream", fail_stream)
        with pytest.raises(RetentionPolicyError) as rejected:
            await graph_context_inventory(db, OWNER)
        assert str(rejected.value) == "retention_context_store_unavailable"
        assert "SYNTHETIC_PRIVATE" not in str(rejected.value)


def test_postgres_graph_reflection_names_private_schema_in_probe_and_table(monkeypatch):
    from app.services import retention_context

    connection = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    calls = []
    inspector = SimpleNamespace(has_table=lambda name, *, schema: calls.append(
        ("probe", name, schema),
    ) or True)
    monkeypatch.setattr(retention_context, "inspect", lambda actual: inspector)

    def reflect(name, metadata, *, schema, autoload_with, resolve_fks):
        assert autoload_with is connection and resolve_fks is False
        calls.append(("reflect", name, schema))
        return GraphCheckpoint.__table__.to_metadata(metadata, schema=schema)

    monkeypatch.setattr(retention_context, "Table", reflect)
    result = _graph_table(SimpleNamespace(connection=lambda: connection))
    assert result.schema == "veridra_private"
    assert calls == [("probe", "graph_checkpoints", "veridra_private"),
                     ("reflect", "graph_checkpoints", "veridra_private")]


class CounterState(TypedDict):
    value: int


@pytest.fixture
async def langgraph(tmp_path):
    path = tmp_path / "langgraph-context.db"
    async with AsyncSqliteSaver.from_conn_string(str(path)) as saver:
        builder = StateGraph(CounterState)
        builder.add_node("increment", lambda state: {"value": state["value"] + 1})
        builder.add_edge(START, "increment")
        builder.add_edge("increment", END)
        graph = builder.compile(checkpointer=saver)
        await graph.ainvoke({"value": 1}, {"configurable": {"thread_id": f"{OWNER}:session"}})
        await graph.ainvoke({"value": 8}, {"configurable": {"thread_id": f"{OTHER}:session"}})
        engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
        try:
            yield saver, graph, async_sessionmaker(engine)
        finally:
            await engine.dispose()


async def test_real_langgraph_context_exact_reset_and_sdk_recreation(langgraph):
    saver, graph, factory = langgraph
    config = {"configurable": {"thread_id": f"{OWNER}:session"}}
    other_config = {"configurable": {"thread_id": f"{OTHER}:session"}}
    async with factory() as db:
        inventory = await langgraph_context_inventory(db, OWNER)
        assert inventory.row_count > 2
        assert inventory == await langgraph_context_inventory(db, OWNER)
        assert "session" not in repr(inventory) and "synthetic-owner" not in repr(inventory)
        with pytest.raises(RetentionPolicyError, match="preview_changed"):
            await reset_langgraph_context(db, OTHER, inventory.digest)
        await db.rollback()
        assert await reset_langgraph_context(db, OWNER, inventory.digest) == inventory.row_count
        await db.rollback()
        assert await saver.aget_tuple(config) is not None
        assert await reset_langgraph_context(db, OWNER, inventory.digest) == inventory.row_count
        await db.commit()
        assert (await langgraph_context_inventory(db, OWNER)).row_count == 0
    assert await saver.aget_tuple(config) is None
    assert (await saver.aget_tuple(other_config)).checkpoint["channel_values"]["value"] == 9
    assert (await graph.ainvoke({"value": 40}, config))["value"] == 41


async def test_langgraph_detects_new_checkpoint_since_preview(langgraph):
    saver, graph, factory = langgraph
    config = {"configurable": {"thread_id": f"{OWNER}:session"}}
    async with factory() as db:
        inventory = await langgraph_context_inventory(db, OWNER)
    await graph.ainvoke({"value": 4}, config)
    async with factory() as db:
        with pytest.raises(RetentionPolicyError, match="preview_changed"):
            await reset_langgraph_context(db, OWNER, inventory.digest)
        await db.rollback()
    assert (await saver.aget_tuple(config)).checkpoint["channel_values"]["value"] == 5


async def test_langgraph_opaque_payloads_are_not_deserialized_and_sql_wildcards_are_literal(
    langgraph, monkeypatch,
):
    _saver, _graph, factory = langgraph
    literal_owner = "synthetic-%_owner"
    async with factory() as db:
        for owner in (literal_owner, "synthetic-OTHER-owner"):
            await db.execute(text(
                "INSERT INTO checkpoints "
                "(thread_id,checkpoint_ns,checkpoint_id,type,checkpoint,metadata) "
                "VALUES (:thread,'','opaque','pickle',:value,:value)"
            ), {"thread": f"{owner}:session", "value": b"MALFORMED_SYNTHETIC_PICKLE_CANARY"})
        await db.commit()
        monkeypatch.setattr(pickle, "loads", lambda *_args, **_kwargs: pytest.fail(
            "Opaque framework payloads must not be deserialized",
        ))
        inventory = await langgraph_context_inventory(db, literal_owner)
        assert inventory.row_count == 1
        assert "PICKLE_CANARY" not in repr(inventory)
        await db.execute(text(
            "UPDATE checkpoints SET checkpoint=:value WHERE thread_id=:thread"
        ), {"thread": f"{literal_owner}:session", "value": b"CHANGED_OPAQUE_CANARY"})
        await db.commit()
        with pytest.raises(RetentionPolicyError, match="preview_changed"):
            await reset_langgraph_context(db, literal_owner, inventory.digest)
        await db.rollback()
        changed = await langgraph_context_inventory(db, literal_owner)
        assert changed.row_count == inventory.row_count
        assert changed.digest != inventory.digest
        assert await reset_langgraph_context(db, literal_owner, changed.digest) == 1
        await db.commit()
        assert (await langgraph_context_inventory(db, "synthetic-OTHER-owner")).row_count == 1


async def test_langgraph_malformed_owned_thread_and_unknown_schema_fail_closed(langgraph):
    _saver, _graph, factory = langgraph
    async with factory() as db:
        await db.execute(text(
            "INSERT INTO checkpoints "
            "(thread_id,checkpoint_ns,checkpoint_id,type,checkpoint,metadata) "
            "VALUES (:thread,'','invalid','bytes',:value,:value)"
        ), {"thread": f"{OWNER}:", "value": b"synthetic"})
        await db.commit()
        with pytest.raises(RetentionPolicyError, match="context_thread_invalid"):
            await langgraph_context_inventory(db, OWNER)
        with pytest.raises(RetentionPolicyError, match="invalid_retention_context_owner"):
            await langgraph_context_inventory(db, "owner:ambiguous")
        await db.rollback()
        await db.execute(text("CREATE TABLE unknown_future_content (value BLOB)"))
        await db.commit()
        with pytest.raises(RetentionPolicyError, match="langgraph_schema_incomplete"):
            await langgraph_context_inventory(db, OTHER)


async def test_langgraph_age_fails_closed_for_unknown_checkpoint_id(langgraph):
    _saver, _graph, factory = langgraph
    async with factory() as db:
        await db.execute(text(
            "INSERT INTO checkpoints "
            "(thread_id,checkpoint_ns,checkpoint_id,type,checkpoint,metadata) "
            "VALUES (:thread,'','legacy-unknown','bytes',:value,:value)"
        ), {"thread": f"{OWNER}:legacy", "value": b"SYNTHETIC_OPAQUE_BYTES"})
        await db.commit()
        with pytest.raises(RetentionPolicyError, match="checkpoint_age_unknown"):
            await langgraph_context_oldest_at(db, OWNER)


@pytest.mark.parametrize("kind", ["adk", "graph", "langgraph"])
async def test_missing_local_file_is_not_created_and_missing_schema_is_not_empty(tmp_path, kind):
    path = tmp_path / f"missing-{kind}.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    factory = async_sessionmaker(engine)
    action = {"adk": lambda db: adk_context_inventory(db, OWNER, namespace=None),
              "graph": lambda db: graph_context_inventory(db, OWNER),
              "langgraph": lambda db: langgraph_context_inventory(db, OWNER)}[kind]
    try:
        async with factory() as db:
            with pytest.raises(RetentionPolicyError, match="store_unavailable"):
                await action(db)
        assert not path.exists()
        async with engine.begin():
            pass  # Deliberately create only this disposable fixture file.
        async with factory() as db:
            with pytest.raises(RetentionPolicyError, match="marker_missing|schema_incomplete"):
                await action(db)
    finally:
        await engine.dispose()
