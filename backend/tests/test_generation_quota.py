"""Offline proof of bounded admission; no provider requests or quota resets."""

import asyncio
from threading import Event
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from app.services import quota
from app.services.quota import QuotaGuard, request_quota_deadline, reserve_generation_quota
from app.services.relational_quota import RelationalQuotaGuard
from app.tools.contracts import ToolError


@pytest.fixture
def clock(monkeypatch):
    value = {"seconds": 1000.0, "sleeps": []}
    original_sleep = asyncio.sleep

    async def sleep(seconds):
        value["sleeps"].append(seconds)
        value["seconds"] += seconds
        await original_sleep(0)

    monkeypatch.setattr(quota, "time", SimpleNamespace(
        monotonic=lambda: value["seconds"], time=lambda: value["seconds"],
    ))
    monkeypatch.setattr(quota.asyncio, "sleep", sleep)
    return value


async def test_generation_minute_admission_waits_for_real_slot_once(tmp_path, clock):
    guard = QuotaGuard(tmp_path / "rolling.db")
    for _ in range(5):
        guard.reserve("flash", 100, now=944)

    reservation = await reserve_generation_quota(guard, 200)

    assert reservation["reserved_tokens"] == 200
    assert clock["seconds"] == 1004
    assert sum(clock["sleeps"]) == 4
    assert guard.daily_count("flash", now=1004) == 6
    assert guard.snapshot("flash", now=1004)["minute_used"] == 1


async def test_generation_minute_wait_is_at_most_fifteen_seconds(tmp_path, clock):
    guard = QuotaGuard(tmp_path / "bounded.db")
    for _ in range(5):
        guard.reserve("flash", 100, now=1000)

    with pytest.raises(ToolError) as caught:
        await reserve_generation_quota(guard, 200, max_wait_seconds=1000)

    assert caught.value.code == "quota_minute_exhausted"
    assert sum(clock["sleeps"]) == 15
    assert guard.daily_count("flash", now=1015) == 5


async def test_generation_wait_leaves_provider_runway_and_resets_context(tmp_path, clock):
    guard = QuotaGuard(tmp_path / "deadline.db")
    for _ in range(5):
        guard.reserve("flash", 100, now=1000)

    with request_quota_deadline(24):
        with request_quota_deadline(60):
            with pytest.raises(ToolError) as caught:
                await reserve_generation_quota(guard, 200, generation_runway_seconds=20)
    assert caught.value.code == "quota_minute_exhausted"
    assert sum(clock["sleeps"]) == 4
    assert quota._request_deadline.get() is None
    assert quota._reservation_cancelled.get() is None
    assert guard.daily_count("flash", now=1004) == 5


@pytest.mark.parametrize("code", ["quota_daily_exhausted", "context_budget", "invalid_spec"])
async def test_generation_policy_errors_never_wait_or_retry(clock, code):
    class Guard:
        calls = 0

        def reserve(self, bucket, tokens):
            self.calls += 1
            raise ToolError("blocked", code=code)

    guard = Guard()
    with pytest.raises(ToolError) as caught:
        await reserve_generation_quota(guard, 100)
    assert caught.value.code == code
    assert guard.calls == 1
    assert clock["sleeps"] == []


async def test_generation_oversize_cannot_be_fixed_by_waiting(clock):
    class Guard:
        def reserve(self, *args):
            pytest.fail("oversized generation must not touch the ledger")

    with pytest.raises(ToolError) as caught:
        await reserve_generation_quota(Guard(), quota.quota_limits()["flash"].tpm + 1)
    assert caught.value.code == "quota_minute_exhausted"
    assert clock["sleeps"] == []


async def test_cancelled_waiter_stops_polling_and_never_calls_provider():
    sleep_started = Event()
    calls = []

    class Guard:
        def reserve(self, bucket, tokens):
            calls.append("reserve")
            sleep_started.set()
            raise ToolError("wait", code="quota_minute_exhausted")

    async def run():
        await reserve_generation_quota(Guard(), 100)
        calls.append("provider")

    pending = asyncio.create_task(run())
    assert await asyncio.to_thread(sleep_started.wait, 2)
    # Cancellation is processed at the in-flight worker/sleep boundary.
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    await asyncio.sleep(0.05)
    assert calls == ["reserve"]


@pytest.mark.parametrize("relational", [False, True])
async def test_cancelled_atomic_worker_checks_before_late_reservation(tmp_path, relational):
    entered, release, finished = Event(), Event(), Event()
    engine = None
    if relational:
        engine = create_engine(f"sqlite:///{tmp_path / 'relational.db'}")
        RelationalQuotaGuard.create_schema(engine)
        base, args = RelationalQuotaGuard, [engine]
    else:
        base, args = QuotaGuard, [tmp_path / "sqlite.db"]

    class Guard(base):
        def reserve(self, *args, **kwargs):
            entered.set()
            release.wait(timeout=2)
            try:
                return super().reserve(*args, **kwargs)
            finally:
                finished.set()

    guard = Guard(*args)
    pending = asyncio.create_task(reserve_generation_quota(guard, 100))
    assert await asyncio.to_thread(entered.wait, 2)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    release.set()
    assert await asyncio.to_thread(finished.wait, 2)
    assert guard.daily_count("flash") == 0
    assert quota._reservation_cancelled.get() is None
    if engine is not None:
        engine.dispose()


async def test_expired_request_never_reserves_or_calls_provider(tmp_path, clock):
    guard = QuotaGuard(tmp_path / "expired.db")
    with request_quota_deadline(1):
        clock["seconds"] += 2
        with pytest.raises(TimeoutError):
            await reserve_generation_quota(guard, 100)
    assert guard.daily_count("flash") == 0


async def test_concurrent_cancellation_does_not_cancel_other_request(tmp_path):
    entered, release, finished = Event(), Event(), Event()

    class BlockedGuard(QuotaGuard):
        def reserve(self, *args, **kwargs):
            entered.set()
            release.wait(timeout=2)
            try:
                return super().reserve(*args, **kwargs)
            finally:
                finished.set()

    path = tmp_path / "shared.db"
    first = BlockedGuard(path)
    second = QuotaGuard(path)
    pending = asyncio.create_task(reserve_generation_quota(first, 100))
    assert await asyncio.to_thread(entered.wait, 2)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert (await reserve_generation_quota(second, 100))["reserved_tokens"] == 100
    release.set()
    assert await asyncio.to_thread(finished.wait, 2)
    assert second.daily_count("flash") == 1


async def test_generation_soft_daily_cap_is_not_raised_by_wait(tmp_path, clock):
    guard = QuotaGuard(tmp_path / "daily.db")
    for index in range(16):
        guard.reserve("flash", 100, now=2 + index * 61)
    with pytest.raises(ToolError) as caught:
        await reserve_generation_quota(guard, 100)
    assert caught.value.code == "quota_daily_exhausted"
    assert clock["sleeps"] == []
    assert guard.daily_count("flash") == 16


async def test_generation_keeps_explicit_reserve_call_policy(clock):
    class Guard:
        def reserve(self, bucket, tokens, *, reserve_call=False):
            assert reserve_call is True
            return {"reserved_tokens": tokens}

    assert await reserve_generation_quota(Guard(), 100, reserve_call=True) == {
        "reserved_tokens": 100,
    }


async def test_chat_deadline_reaches_wait_for_task_and_worker_then_resets(tmp_path):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.agent.orchestrator import AgentRunResult
    from app.api.chat import chat
    from app.api.schemas import ChatRequest
    from app.db.models import Base, User

    seen = []

    class Orchestrator:
        async def run(self, **kwargs):
            seen.append(quota._request_deadline.get())
            seen.append(await asyncio.to_thread(quota._request_deadline.get))
            return AgentRunResult(answer="Đã kiểm.", plan=[], trace=[], citations=[])

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat-deadline.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            user = User(email="deadline@example.com", display_name="Test", role="editor")
            db.add(user)
            await db.commit()
            request = SimpleNamespace(
                state=SimpleNamespace(request_id="deadline-request"),
                app=SimpleNamespace(state=SimpleNamespace(orchestrator=Orchestrator())),
            )
            started = quota.time.monotonic()
            response = await chat(ChatRequest(message="Kiểm thời hạn."), request, user, db)
            assert response.answer == "Đã kiểm."
            assert seen[0] == seen[1]
            assert started < seen[0] <= started + 61
            assert quota._request_deadline.get() is None
    finally:
        await engine.dispose()
