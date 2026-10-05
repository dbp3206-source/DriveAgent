import json
from datetime import datetime
from time import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import scheduler
from app.core.config import Settings
from app.db.models import Base, ChatSession, Message, ScheduledJob, User
from app.services.premeeting_briefing import PreMeetingBriefingService
from app.services.scheduled_jobs import _claim, _finish, enqueue_for_invited_users, execute_one


@pytest.fixture
async def scheduled_store(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'scheduled.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield engine, factory
    await engine.dispose()


def test_scheduler_bearer_is_required_and_secret_safe(monkeypatch):
    settings = Settings(_env_file=None, scheduler_bearer_token="s" * 40)
    monkeypatch.setattr(scheduler, "get_settings", lambda: settings)
    with pytest.raises(HTTPException) as missing:
        scheduler._authorize(None)
    assert missing.value.status_code == 401
    with pytest.raises(HTTPException):
        scheduler._authorize("Bearer wrong")
    scheduler._authorize(f"Bearer {'s' * 40}")
    assert "s" * 40 not in repr(settings)


@pytest.mark.asyncio
async def test_schedule_enqueue_is_owner_bounded_idempotent_and_leased(scheduled_store):
    _engine, factory = scheduled_store
    settings = Settings(_env_file=None, environment="development")
    async with factory() as db:
        db.add_all(
            [
                User(
                    email="ready@example.com",
                    display_name="Ready",
                    encrypted_google_credentials="ciphertext",
                ),
                User(email="no-oauth@example.com", display_name="No OAuth"),
            ]
        )
        await db.commit()
        first = await enqueue_for_invited_users(
            db, settings, kind="morning", dedupe_key="morning:2026-09-30"
        )
        second = await enqueue_for_invited_users(
            db, settings, kind="morning", dedupe_key="morning:2026-09-30"
        )
    assert first == {"eligible_users": 1, "created": 1, "existing": 0}
    assert second == {"eligible_users": 1, "created": 0, "existing": 1}
    now = time()
    claimed = await _claim(factory, now=now)
    assert claimed and claimed["kind"] == "morning"
    assert await _claim(factory, now=now + 1) is None
    await _finish(factory, claimed, result={"session_id": "session"}, error=None)
    async with factory() as db:
        row = await db.scalar(select(ScheduledJob))
        assert row.status == "completed"
        assert "session" in row.checkpoint_json


@pytest.mark.asyncio
async def test_premeeting_preview_combines_calendar_mail_and_cited_web(scheduled_store):
    _engine, factory = scheduled_store
    settings = Settings(_env_file=None)
    async with factory() as db:
        user = User(
            email="owner@example.com",
            display_name="Owner",
            encrypted_google_credentials="ciphertext",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        class Registry:
            async def execute(self, name, _payload, _context):
                if name == "calendar_list_upcoming":
                    return SimpleNamespace(
                        events=[
                            SimpleNamespace(
                                id="event-1",
                                title="FPT planning",
                                start="2026-10-01T09:00:00+07:00",
                                location="Online",
                            )
                        ]
                    )
                if name == "gmail_list_messages":
                    return SimpleNamespace(
                        messages=[
                            SimpleNamespace(
                                sender="customer@example.com",
                                subject="FPT agenda",
                                date="2026-09-30",
                            )
                        ]
                    )
                return SimpleNamespace(
                    summary="Thông tin đã kiểm chứng [S1].",
                    sources=[SimpleNamespace(title="Official", url="https://example.com")],
                )

        service = PreMeetingBriefingService(settings, Registry())
        service._now = lambda: datetime.fromisoformat("2026-10-01T08:30:00+07:00")
        result = await service.generate(user, db, request_id="scheduled-test")
        assert result["meeting_count"] == 1
        assert result["source_count"] == 1
        job_session = await db.get(ChatSession, result["session_id"])
        assert job_session.title.startswith("Chuẩn bị cuộc họp")


def meeting(**overrides):
    fields = dict(
        id="meeting-1",
        title="Customer planning",
        start="2026-10-01T09:00:00+07:00",
        end="2026-10-01T10:00:00+07:00",
        all_day=False,
        location="Online",
        status="confirmed",
        updated="2026-09-30T08:00:00Z",
        etag='"revision-1"',
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_premeeting_filters_exact_lead_window_timezone_and_unsafe_events():
    service = PreMeetingBriefingService(Settings(_env_file=None, pre_meeting_lead_minutes=30), None)
    now = datetime.fromisoformat("2026-10-01T08:30:00+07:00")
    inside = meeting(id="inside", start="2026-10-01T01:45:00Z")
    boundary = meeting(id="boundary")
    events = [
        boundary,
        inside,
        meeting(start="2026-10-01T08:29:00+07:00"),
        meeting(start=now.isoformat()),
        meeting(start="2026-10-01T09:00:01+07:00"),
        meeting(all_day=True),
        meeting(status="cancelled"),
        meeting(start="2026-10-01"),
        meeting(start="2026-10-01T09:00:00"),
        meeting(start="invalid"),
        meeting(id=""),
    ]
    assert service._due_events(events, now) == [inside, boundary]
    original = service.event_identity(boundary)
    assert original != service.event_identity(meeting(etag='"revision-2"'))
    fallback = meeting(etag=None, updated=None)
    assert service.event_identity(fallback) != service.event_identity(
        meeting(etag=None, updated=None, title="Changed title")
    )


@pytest.mark.parametrize("change", ["changed", "cancelled", "past", "removed"])
async def test_event_version_queue_dedupe_and_stale_execution_readback(
    scheduled_store, monkeypatch, change
):
    _engine, factory = scheduled_store
    settings = Settings(_env_file=None)
    now = datetime.fromisoformat("2026-10-01T08:30:00+07:00")
    monkeypatch.setattr(PreMeetingBriefingService, "_now", lambda self: now)

    async def runtime(_db, _user_id, _settings):
        return settings

    monkeypatch.setattr("app.services.scheduled_jobs.user_runtime_settings", runtime)

    class Registry:
        events = [meeting()]
        calls = []

        async def execute(self, name, _payload, _context):
            self.calls.append((name, _context.user.id))
            if name == "calendar_list_upcoming":
                return SimpleNamespace(events=self.events)
            if name == "gmail_list_messages":
                return SimpleNamespace(messages=[])
            assert name == "web_research"
            return SimpleNamespace(summary="Verified summary", sources=[])

    registry = Registry()
    async with factory() as db:
        user = User(
            email="owner@example.com",
            display_name="Owner",
            encrypted_google_credentials="ciphertext",
        )
        db.add(user)
        await db.commit()
        owner_id = user.id
        first = await enqueue_for_invited_users(
            db, settings, kind="pre_meeting", dedupe_key="first-hour", registry=registry
        )
        second = await enqueue_for_invited_users(
            db, settings, kind="pre_meeting", dedupe_key="different-hour", registry=registry
        )
        assert first["created"] == 1
        assert second["created"] == 0 and second["existing"] == 1
        if change == "changed":
            registry.events = [meeting(etag='"revision-2"', title="Changed agenda")]
        elif change == "cancelled":
            registry.events = [meeting(status="cancelled")]
        elif change == "past":
            registry.events = [meeting(start="2026-10-01T08:00:00+07:00")]
        else:
            registry.events = []
        latest = await enqueue_for_invited_users(
            db, settings, kind="pre_meeting", dedupe_key="first-hour", registry=registry
        )
        assert latest["created"] == (1 if change == "changed" else 0)
    registry.calls.clear()
    assert await execute_one(factory, settings, registry)
    assert registry.calls == [("calendar_list_upcoming", owner_id)]
    async with factory() as db:
        messages = (await db.scalars(select(Message))).all()
        assert messages == []
        first_job = await db.scalar(select(ScheduledJob).order_by(ScheduledJob.created_at))
        assert first_job.status == "completed"
        assert "event_not_due_or_changed" in first_job.checkpoint_json
    if change == "changed":
        assert await execute_one(factory, settings, registry)
        assert [name for name, _owner in registry.calls] == [
            "calendar_list_upcoming",
            "calendar_list_upcoming",
            "gmail_list_messages",
            "web_research",
        ]
        async with factory() as db:
            messages = (await db.scalars(select(Message))).all()
            assert len(messages) == 1
            assert "Changed agenda" in messages[0].content
            assert messages[0].user_id == owner_id
    assert not await execute_one(factory, settings, registry)


async def test_no_due_event_creates_no_conversation_or_source_work(scheduled_store, monkeypatch):
    _engine, factory = scheduled_store
    monkeypatch.setattr(
        PreMeetingBriefingService,
        "_now",
        lambda self: datetime.fromisoformat("2026-10-01T08:30:00+07:00"),
    )

    class Registry:
        calls = []

        async def execute(self, name, _payload, _context):
            self.calls.append(name)
            return SimpleNamespace(events=[meeting(start="2026-10-02T09:00:00+07:00")])

    registry = Registry()
    async with factory() as db:
        user = User(email="owner@example.com", display_name="Owner")
        db.add(user)
        await db.commit()
        result = await PreMeetingBriefingService(Settings(_env_file=None), registry).generate(
            user, db, request_id="no-due-event"
        )
        assert result["meeting_count"] == 0
        assert await db.scalar(select(ChatSession)) is None
    assert registry.calls == ["calendar_list_upcoming"]


async def test_same_event_queue_remains_owner_scoped_and_payload_survives_reclaim(
    scheduled_store, monkeypatch
):
    _engine, factory = scheduled_store
    settings = Settings(_env_file=None)
    monkeypatch.setattr(
        PreMeetingBriefingService,
        "_now",
        lambda self: datetime.fromisoformat("2026-10-01T08:30:00+07:00"),
    )

    async def runtime(_db, _user_id, _settings):
        return settings

    monkeypatch.setattr("app.services.scheduled_jobs.user_runtime_settings", runtime)

    class Registry:
        owners = []

        async def execute(self, name, _payload, context):
            assert name == "calendar_list_upcoming"
            self.owners.append(context.user.id)
            return SimpleNamespace(events=[meeting()])

    registry = Registry()
    async with factory() as db:
        db.add_all(
            [
                User(
                    email=f"owner-{i}@example.com",
                    display_name=f"Owner {i}",
                    encrypted_google_credentials="ciphertext",
                )
                for i in range(2)
            ]
        )
        await db.commit()
        result = await enqueue_for_invited_users(
            db, settings, kind="pre_meeting", dedupe_key="ignored-hour", registry=registry
        )
        assert result["eligible_users"] == 2 and result["created"] == 2
        assert result["failed_users"] == 0 and result["status"] == "accepted"
        rows = (await db.scalars(select(ScheduledJob))).all()
        assert {row.user_id for row in rows} == set(registry.owners)
        assert len({row.dedupe_key for row in rows}) == 1
    first = await _claim(factory, now=time())
    # Complete the other owner's queued job so the reclaimed job is selected.
    second = await _claim(factory, now=time())
    assert second["user_id"] != first["user_id"]
    await _finish(factory, second, result={}, error=None)
    reclaimed = await _claim(factory, now=time() + 301)
    assert reclaimed["id"] == first["id"]
    assert reclaimed["payload_json"] == first["payload_json"]
    assert json.loads(reclaimed["payload_json"])["event"] == (
        PreMeetingBriefingService.event_identity(meeting())
    )


async def test_legacy_hour_slot_job_without_event_fails_before_source_calls(
    scheduled_store, monkeypatch
):
    _engine, factory = scheduled_store
    settings = Settings(_env_file=None)

    async def runtime(_db, _user_id, _settings):
        return settings

    monkeypatch.setattr("app.services.scheduled_jobs.user_runtime_settings", runtime)

    class Registry:
        async def execute(self, *_args):
            pytest.fail("Legacy job must not read sources or call a model")

    async with factory() as db:
        user = User(email="owner@example.com", display_name="Owner")
        db.add(user)
        await db.flush()
        db.add(ScheduledJob(user_id=user.id, kind="pre_meeting", dedupe_key="old-hour"))
        await db.commit()
    assert await execute_one(factory, settings, Registry())
    async with factory() as db:
        row = await db.scalar(select(ScheduledJob))
        assert row.status == "failed"
        assert row.error_code == "scheduled_event_identity_missing"
        assert await db.scalar(select(ChatSession)) is None


async def test_calendar_failure_is_isolated_and_summary_has_no_owner_or_secret(
    scheduled_store, monkeypatch
):
    _engine, factory = scheduled_store
    settings = Settings(_env_file=None)
    monkeypatch.setattr(
        PreMeetingBriefingService,
        "_now",
        lambda self: datetime.fromisoformat("2026-10-01T08:30:00+07:00"),
    )

    async def runtime(_db, _user_id, _settings):
        return settings

    monkeypatch.setattr("app.services.scheduled_jobs.user_runtime_settings", runtime)

    class Registry:
        calls = []

        async def execute(self, name, _payload, context):
            assert name == "calendar_list_upcoming"
            self.calls.append(context.user.id)
            if context.user.email == "failed@example.com":
                raise RuntimeError("failed@example.com provider-private-secret")
            return SimpleNamespace(events=[meeting()])

    registry = Registry()
    async with factory() as db:
        failed = User(
            email="failed@example.com",
            display_name="Failed",
            encrypted_google_credentials="ciphertext",
        )
        ready = User(
            email="ready@example.com",
            display_name="Ready",
            encrypted_google_credentials="ciphertext",
        )
        db.add_all([failed, ready])
        await db.commit()
        result = await enqueue_for_invited_users(
            db, settings, kind="pre_meeting", dedupe_key="slot", registry=registry
        )
        assert result == {
            "eligible_users": 2,
            "created": 1,
            "existing": 0,
            "failed_users": 1,
            "status": "partial_failure",
            "failures": [{"code": "calendar_read_failed", "count": 1}],
        }
        assert registry.calls == [failed.id, ready.id]
        rows = (await db.scalars(select(ScheduledJob))).all()
        assert len(rows) == 1 and rows[0].user_id == ready.id
        assert "provider-private-secret" not in json.dumps(result)
        assert "@example.com" not in json.dumps(result)


@pytest.mark.parametrize("corrupt", ['{"private-secret":', "[]", "null", '"private-secret"'])
async def test_corrupt_payload_fails_durably_without_replay_or_stranding_next_job(
    scheduled_store, monkeypatch, corrupt, caplog
):
    _engine, factory = scheduled_store
    settings = Settings(_env_file=None)
    runtime_calls = []

    async def runtime(_db, user_id, _settings):
        runtime_calls.append(user_id)
        return settings

    async def morning(_self, user, _db, *, request_id):
        return {"owner": user.id, "request_id": request_id}

    monkeypatch.setattr("app.services.scheduled_jobs.user_runtime_settings", runtime)
    monkeypatch.setattr(
        "app.services.scheduled_jobs.MorningBriefingService.generate_brief", morning
    )
    async with factory() as db:
        user = User(email="owner@example.com", display_name="Owner")
        db.add(user)
        await db.flush()
        bad = ScheduledJob(
            user_id=user.id, kind="pre_meeting", dedupe_key="corrupt", payload_json=corrupt
        )
        db.add(bad)
        await db.commit()
        bad_id = bad.id
    assert await execute_one(factory, settings, None)
    assert runtime_calls == []
    async with factory() as db:
        bad = await db.get(ScheduledJob, bad_id)
        assert bad.status == "failed" and bad.attempts == 1
        assert bad.error_code == "scheduled_payload_invalid"
        assert json.loads(bad.checkpoint_json) == {"error_code": "scheduled_payload_invalid"}
        assert bad.lease_until is None and bad.lease_token is None
        db.add(ScheduledJob(user_id=bad.user_id, kind="morning", dedupe_key="good"))
        await db.commit()
    assert await execute_one(factory, settings, None)
    assert len(runtime_calls) == 1
    assert not await execute_one(factory, settings, None)
    assert "private-secret" not in caplog.text
