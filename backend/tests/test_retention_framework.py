"""Real pinned ADK session store, synthetic data, no model/OAuth/network."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from google.adk.events import Event
from google.adk.sessions import DatabaseSessionService
from google.genai import types
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.retention_framework import _tables, adk_inventory, purge_adk
from app.services.retention_policy import (
    REQUIRED_INVENTORIES,
    RetentionPolicy,
    RetentionPolicyError,
)

OLD = datetime(2026, 9, 1, 12, tzinfo=UTC)
NOW = OLD + timedelta(days=45)


@pytest.fixture
async def adk(tmp_path):
    service = DatabaseSessionService(db_url=f"sqlite+aiosqlite:///{tmp_path / 'adk.db'}")
    try:
        yield service
    finally:
        await service.close()


async def create(service, owner, *, shared=False):
    state = {"case": "SYNTHETIC_PRIVATE_CONTEXT", "user:language": "Vietnamese"}
    if shared:
        state["app:shared_case"] = "SYNTHETIC_SHARED_CONTEXT"
    session = await service.create_session(
        app_name="drive_agent", user_id=owner, session_id=str(uuid4()), state=state,
    )
    await service.append_event(session, Event(
        author="assistant", content=types.Content(
            role="model", parts=[types.Part(text="SYNTHETIC_PRIVATE_EVENT")],
        ),
    ))
    return session


async def test_real_adk_inventory_has_only_owner_records_and_no_content(adk):
    own = await create(adk, "synthetic-owner-a")
    other = await create(adk, "synthetic-owner-b")
    async with async_sessionmaker(adk.db_engine, expire_on_commit=False)() as db:
        result = await adk_inventory(db, "synthetic-owner-a", namespace=None)
        assert len(result.candidates) == 3  # Session, one event and user state.
        assert all(item.owner_id == "synthetic-owner-a" for item in result.candidates)
        assert "SYNTHETIC_PRIVATE" not in repr(result) and other.id not in repr(result)
        assert await adk_inventory(db, "synthetic-owner-a", namespace=None) == result
        assert not db.new and not db.dirty and not db.deleted
    reopened = await adk.get_session(
        app_name="drive_agent", user_id="synthetic-owner-a", session_id=own.id,
    )
    assert reopened.state["case"] == "SYNTHETIC_PRIVATE_CONTEXT"
    assert len(reopened.events) == 1  # Inventory did not clear or change state.


async def test_nonempty_shared_state_is_not_silently_attributed_or_deleted(adk):
    session = await create(adk, "synthetic-owner-a", shared=True)
    async with async_sessionmaker(adk.db_engine)() as db:
        with pytest.raises(RetentionPolicyError, match="unattributed_framework_state"):
            await adk_inventory(db, "synthetic-owner-a", namespace=None)
    reopened = await adk.get_session(
        app_name="drive_agent", user_id="synthetic-owner-a", session_id=session.id,
    )
    assert reopened.state["app:shared_case"] == "SYNTHETIC_SHARED_CONTEXT"


async def test_missing_framework_marker_or_table_never_looks_like_empty_inventory(adk, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'explicit-empty-test.db'}")
    try:
        async with async_sessionmaker(engine)() as db:
            with pytest.raises(RetentionPolicyError, match="marker_missing"):
                await adk_inventory(db, "synthetic-owner", namespace=None)
    finally:
        await engine.dispose()
    await create(adk, "synthetic-owner")
    async with adk.db_engine.begin() as db:
        await db.execute(text("DROP TABLE events"))  # Disposable test DB only.
    async with async_sessionmaker(adk.db_engine)() as db:
        with pytest.raises(RetentionPolicyError, match="schema_incomplete"):
            await adk_inventory(db, "synthetic-owner", namespace=None)


async def test_invalid_namespace_or_owner_cannot_expand_the_read(adk):
    await create(adk, "synthetic-owner")
    async with async_sessionmaker(adk.db_engine)() as db:
        with pytest.raises(RetentionPolicyError, match="invalid_framework_namespace"):
            await adk_inventory(db, "synthetic-owner", namespace="public")
        with pytest.raises(RetentionPolicyError, match="invalid_retention_owner"):
            await adk_inventory(db, "", namespace=None)


async def test_unknown_owned_app_is_not_silently_skipped(adk):
    await adk.create_session(app_name="unknown_synthetic_app", user_id="synthetic-owner",
                             session_id=str(uuid4()), state={"case": "Synthetic"})
    async with async_sessionmaker(adk.db_engine)() as db:
        with pytest.raises(RetentionPolicyError, match="unsupported_framework_app"):
            await adk_inventory(db, "synthetic-owner", namespace=None)


async def age_adk(service, owner, when, namespace=None):
    """Age disposable SDK rows only; never points at a user's configured DB."""
    async with async_sessionmaker(service.db_engine)() as db:
        tables = await db.run_sync(_tables, namespace)
        for name in ("sessions", "events", "user_states"):
            table = tables[name]
            field = "timestamp" if name == "events" else "update_time"
            await db.execute(update(table).where(table.c.user_id == owner).values({
                field: when.replace(tzinfo=None),
            }))
        await db.commit()


async def approved_adk(service, owner):
    async with async_sessionmaker(service.db_engine)() as db:
        rows = (await adk_inventory(db, owner, namespace=None)).candidates
    policy = RetentionPolicy("synthetic-adk-retention-key-not-production")
    coverage = dict.fromkeys(REQUIRED_INVENTORIES, True)
    preview = policy.prepare(owner_id=owner, candidates=list(rows), inventories=coverage, now=NOW)
    return policy.validate(token=preview.token, owner_id=owner, current=list(rows),
                           inventories=coverage, now=NOW).items


async def test_adk_purge_rolls_back_then_removes_only_owned_rows_and_never_shared_metadata(adk):
    own = await create(adk, "synthetic-owner-a")
    other = await create(adk, "synthetic-owner-b")
    await age_adk(adk, "synthetic-owner-a", OLD)
    approved = await approved_adk(adk, "synthetic-owner-a")
    assert len(approved) == 3
    for commit in (False, True):
        async with async_sessionmaker(adk.db_engine)() as db:
            assert await purge_adk(db, "synthetic-owner-a", approved, namespace=None,
                                    now=NOW.timestamp()) == 3
            if commit:
                await db.commit()
            else:
                await db.rollback()
        result = await adk.get_session(app_name="drive_agent", user_id="synthetic-owner-a",
                                       session_id=own.id)
        assert (result is None) is commit
        preserved = await adk.get_session(app_name="drive_agent", user_id="synthetic-owner-b",
                                          session_id=other.id)
        assert preserved.state["case"] == "SYNTHETIC_PRIVATE_CONTEXT"
        assert len(preserved.events) == 1
    async with async_sessionmaker(adk.db_engine)() as db:
        assert (await adk_inventory(db, "synthetic-owner-a", namespace=None)).candidates == ()
        assert await db.scalar(text("SELECT count(*) FROM app_states")) == 1
        assert await db.scalar(text("SELECT count(*) FROM adk_internal_metadata")) >= 1


async def test_adk_partial_parent_wrong_owner_and_changed_session_cannot_purge(adk):
    own = await create(adk, "synthetic-owner-a")
    await age_adk(adk, "synthetic-owner-a", OLD)
    approved = await approved_adk(adk, "synthetic-owner-a")
    parent = [item for item in approved if ":sessions:" in item.record_id]
    async with async_sessionmaker(adk.db_engine)() as db:
        with pytest.raises(RetentionPolicyError, match="dependency_not_selected"):
            await purge_adk(db, "synthetic-owner-a", parent, namespace=None, now=NOW.timestamp())
        await db.rollback()
        with pytest.raises(RetentionPolicyError, match="preview_changed"):
            await purge_adk(db, "synthetic-owner-b", approved, namespace=None, now=NOW.timestamp())
        await db.rollback()
    # Aging a fixture invalidates the SDK's exact storage marker. Reload it as
    # production does; do not relax the real stale-session protection.
    own = await adk.get_session(app_name="drive_agent", user_id="synthetic-owner-a",
                                 session_id=own.id)
    await adk.append_event(own, Event(author="assistant", content=types.Content(
        role="model", parts=[types.Part(text="FRESH_SYNTHETIC_EVENT")],
    )))
    async with async_sessionmaker(adk.db_engine)() as db:
        with pytest.raises(RetentionPolicyError, match="preview_changed"):
            await purge_adk(db, "synthetic-owner-a", approved, namespace=None, now=NOW.timestamp())
        await db.rollback()
    assert len((await adk.get_session(app_name="drive_agent", user_id="synthetic-owner-a",
                                      session_id=own.id)).events) == 2


async def test_adk_shared_state_change_stops_purge_without_erasing_own_sessions(adk):
    own = await create(adk, "synthetic-owner-a")
    await age_adk(adk, "synthetic-owner-a", OLD)
    approved = await approved_adk(adk, "synthetic-owner-a")
    await create(adk, "synthetic-owner-a", shared=True)
    async with async_sessionmaker(adk.db_engine)() as db:
        with pytest.raises(RetentionPolicyError, match="unattributed_framework_state"):
            await purge_adk(db, "synthetic-owner-a", approved, namespace=None, now=NOW.timestamp())
        await db.rollback()
    assert await adk.get_session(app_name="drive_agent", user_id="synthetic-owner-a",
                                  session_id=own.id) is not None


async def test_purging_old_user_state_does_not_break_newer_session(adk):
    old = await create(adk, "synthetic-owner-a")
    await age_adk(adk, "synthetic-owner-a", OLD)
    fresh = await adk.create_session(app_name="drive_agent", user_id="synthetic-owner-a",
                                      session_id=str(uuid4()),
                                      state={"case": "FRESH_SESSION_CANARY"})
    async with async_sessionmaker(adk.db_engine)() as db:
        tables = await db.run_sync(_tables, None)
        await db.execute(update(tables["user_states"]).where(
            tables["user_states"].c.user_id == "synthetic-owner-a",
        ).values(update_time=OLD.replace(tzinfo=None)))
        await db.commit()
    approved = await approved_adk(adk, "synthetic-owner-a")
    assert len(approved) == 3
    async with async_sessionmaker(adk.db_engine)() as db:
        assert await purge_adk(db, "synthetic-owner-a", approved, namespace=None,
                                now=NOW.timestamp()) == 3
        await db.commit()
    assert await adk.get_session(app_name="drive_agent", user_id="synthetic-owner-a",
                                  session_id=old.id) is None
    fresh = await adk.get_session(app_name="drive_agent", user_id="synthetic-owner-a",
                                   session_id=fresh.id)
    assert fresh.state == {"case": "FRESH_SESSION_CANARY"}
    await adk.append_event(fresh, Event(author="assistant", content=types.Content(
        role="model", parts=[types.Part(text="NEW_EVENT_AFTER_OLD_STATE_PURGE")],
    )))
    result = await adk.get_session(app_name="drive_agent", user_id="synthetic-owner-a",
                                    session_id=fresh.id)
    assert len(result.events) == 1
    async with async_sessionmaker(adk.db_engine)() as db:
        candidates = (await adk_inventory(db, "synthetic-owner-a", namespace=None)).candidates
        assert len(candidates) == 2 and all(":user_states:" not in item.record_id
                                          for item in candidates)
