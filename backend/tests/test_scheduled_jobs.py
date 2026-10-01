from time import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import scheduler
from app.core.config import Settings
from app.db.models import Base, ChatSession, ScheduledJob, User
from app.services.premeeting_briefing import PreMeetingBriefingService
from app.services.scheduled_jobs import _claim, _finish, enqueue_for_invited_users


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

        result = await PreMeetingBriefingService(settings, Registry()).generate(
            user, db, request_id="scheduled-test"
        )
        assert result["meeting_count"] == 1
        assert result["source_count"] == 1
        job_session = await db.get(ChatSession, result["session_id"])
        assert job_session.title.startswith("Chuẩn bị cuộc họp")
