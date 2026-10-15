"""Real pinned ADK session store, synthetic data, no model/OAuth/network."""

from uuid import uuid4

import pytest
from google.adk.events import Event
from google.adk.sessions import DatabaseSessionService
from google.genai import types
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.retention_framework import adk_inventory
from app.services.retention_policy import RetentionPolicyError


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
