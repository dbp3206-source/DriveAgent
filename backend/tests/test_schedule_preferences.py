import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.schedule_preferences import (
    SchedulePreferencesUpdate,
    get_schedule_preferences,
    update_schedule_preferences,
)
from app.core.config import Settings
from app.db.models import Base, ScheduledJob, User
from app.services.scheduled_jobs import enqueue_for_invited_users, execute_one


@pytest.fixture
async def schedule_store(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'schedules.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield engine, factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_recurring_source_reads_are_off_until_user_opts_in(schedule_store):
    _engine, factory = schedule_store
    settings = Settings(_env_file=None, environment="development")

    class Registry:
        async def execute(self, *_args):
            pytest.fail("A disabled schedule must not read any connected source")

    async with factory() as db:
        user = User(
            email="owner@example.com",
            display_name="Owner",
            encrypted_google_credentials="synthetic-ciphertext",
        )
        db.add(user)
        await db.commit()

        preference = await get_schedule_preferences(user)
        assert preference.model_dump() == {
            "morning_enabled": False,
            "pre_meeting_enabled": False,
        }
        result = await enqueue_for_invited_users(
            db, settings, kind="pre_meeting", dedupe_key="slot", registry=Registry()
        )
        assert result["eligible_users"] == 0 and result["created"] == 0
        assert await db.scalar(select(ScheduledJob)) is None


@pytest.mark.asyncio
async def test_disabling_schedule_cancels_waiting_jobs_and_worker_skips_old_claim(
    schedule_store,
):
    _engine, factory = schedule_store
    async with factory() as db:
        user = User(
            email="owner@example.com",
            display_name="Owner",
            scheduled_morning_enabled=True,
            scheduled_pre_meeting_enabled=True,
        )
        db.add(user)
        await db.flush()
        morning = ScheduledJob(user_id=user.id, kind="morning", dedupe_key="morning")
        waiting = ScheduledJob(
            user_id=user.id, kind="pre_meeting", dedupe_key="meeting-waiting"
        )
        stale = ScheduledJob(
            user_id=user.id,
            kind="pre_meeting",
            dedupe_key="meeting-already-claimed",
            status="running",
            lease_until=0,
            lease_token="synthetic-lease",
            payload_json=json.dumps({"event": {"id": "e", "version": "v"}}),
        )
        db.add_all([morning, waiting, stale])
        await db.commit()

        updated = await update_schedule_preferences(
            SchedulePreferencesUpdate(morning_enabled=True, pre_meeting_enabled=False),
            user,
            db,
        )
        assert updated.model_dump() == {
            "morning_enabled": True,
            "pre_meeting_enabled": False,
        }
        assert (await db.get(ScheduledJob, waiting.id)).status == "cancelled"
        assert (await db.get(ScheduledJob, morning.id)).status == "queued"
        (await db.get(ScheduledJob, morning.id)).status = "cancelled"
        await db.commit()

    class Registry:
        async def execute(self, *_args):
            pytest.fail("Worker must re-check consent before reading a source")

    assert await execute_one(factory, Settings(_env_file=None), Registry())
    async with factory() as db:
        skipped = await db.get(ScheduledJob, stale.id)
        assert skipped.status == "completed"
        assert json.loads(skipped.checkpoint_json) == {
            "status": "skipped",
            "reason": "schedule_disabled",
        }
