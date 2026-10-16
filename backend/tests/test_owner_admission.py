"""Real SQL, async lifetimes and signed-session ASGI; no AI or live-data calls."""

import asyncio
from contextvars import Context
from datetime import timedelta
from functools import partial
from pathlib import Path
from tempfile import mkstemp
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.applications import Starlette
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route
from test_cleanup_jobs import NOW, STAMP, plan

from app.db.models import (
    AuditEvent,
    Base,
    ChatSession,
    ChatTask,
    CleanupJob,
    Message,
    PdfIngestionJob,
    ScheduledJob,
    User,
)
from app.services import cleanup_jobs
from app.services.durable_evaluation import EvaluationQueue
from app.services.owner_admission import (
    AdmissionError,
    OwnerAdmission,
    OwnerAdmissionMiddleware,
    guarded_agent_run,
    joined_thread,
)
from app.services.scheduled_jobs import enqueue_for_invited_users
from app.tools.registry import ToolRegistry


@pytest.fixture
async def admission(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'admission.db'}")
    try:
        async with engine.begin() as db:
            await db.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as db:
            owners = [User(email=f"{name}@example.invalid", display_name="Synthetic",
                           encrypted_google_credentials="SYNTHETIC_NOT_A_CREDENTIAL")
                      for name in ("admission-a", "admission-b")]
            db.add_all(owners)
            await db.commit()
        yield OwnerAdmission(factory), factory, owners[0].id, owners[1].id
    finally:
        await engine.dispose()


async def queued(admission):
    gate, factory, owner, _other = admission
    identity = await cleanup_jobs.enqueue(factory, owner, plan(owner), now=STAMP)
    return gate, identity


async def test_parallel_readers_other_owner_and_exclusive_draining(admission):
    gate, _factory, owner, other = admission
    ready, finish = asyncio.Event(), asyncio.Event()

    async def producer():
        async with gate.shared(owner):
            ready.set()
            await finish.wait()
            # Existing work may finish its nested tools while cleanup is waiting.
            async with gate.shared(owner):
                pass

    task = asyncio.create_task(producer())
    await asyncio.wait_for(ready.wait(), 2)
    async with gate.shared(owner):
        async with gate.exclusive(other):
            pass
    with pytest.raises(AdmissionError, match="Còn việc đang xử lý"):
        async with gate.exclusive(owner, timeout=0.02):
            pass
    finish.set()
    await asyncio.wait_for(task, 2)
    async with gate.exclusive(owner):
        with pytest.raises(AdmissionError):
            async with gate.shared(owner):
                pass
        async with gate.shared(other):
            pass
    async with gate.shared(owner):
        pass


async def test_waiting_cleanup_blocks_new_readers_not_existing_nested_work(admission):
    gate, _factory, owner, _other = admission
    request_release, cleanup_started, cleanup_release = (asyncio.Event() for _ in range(3))

    async def cleanup():
        cleanup_started.set()
        async with gate.exclusive(owner):
            request_release.set()
            await cleanup_release.wait()

    async with gate.shared(owner):
        worker = asyncio.create_task(cleanup())
        await cleanup_started.wait()
        await asyncio.sleep(0)
        # This task already owns an admission; its tool is not a new request.
        async with gate.shared(owner):
            pass

        async def outsider():
            # A separate, clean context is tested after clearing the parent's
            # lease by scheduling it only once this request has exited below.
            async with gate.shared(owner):
                pass

        with pytest.raises(AdmissionError):
            await asyncio.create_task(outsider(), context=Context())
    await asyncio.wait_for(request_release.wait(), 2)
    with pytest.raises(AdmissionError):
        await outsider()
    cleanup_release.set()
    await asyncio.wait_for(worker, 2)


async def test_child_reader_outlives_parent_and_inactive_lease_cannot_bypass_sql(admission):
    gate, _factory, owner, _other = admission
    started, release = asyncio.Event(), asyncio.Event()

    async def child():
        async with gate.shared(owner):
            started.set()
            await release.wait()

    async with gate.shared(owner):
        task = asyncio.create_task(child())
        await started.wait()
    with pytest.raises(AdmissionError):
        async with gate.exclusive(owner, timeout=0.02):
            pass
    release.set()
    await task
    delayed = asyncio.Event()

    async def late_child():
        await delayed.wait()
        async with gate.shared(owner):
            pass

    async with gate.shared(owner):
        task = asyncio.create_task(late_child())
    await queued(admission)
    delayed.set()
    with pytest.raises(AdmissionError):
        await task


async def test_durable_job_survives_new_gate_and_readonly_cannot_upgrade_to_mutation(admission):
    _gate, factory, owner, other = admission
    gate, identity = await queued(admission)
    reopened = OwnerAdmission(factory)
    for current in (gate, reopened):
        with pytest.raises(AdmissionError):
            async with current.shared(owner, readonly=True):
                pass
        async with current.shared(other):
            pass
    async with factory() as db:
        await db.execute(update(CleanupJob).where(CleanupJob.id == identity).values(
            status="purging", sql_completed_at=NOW,
        ))
        await db.commit()
    async with gate.shared(owner, readonly=True):
        with pytest.raises(AdmissionError):
            async with gate.shared(owner):
                pass
    async with factory() as db:
        await db.execute(update(CleanupJob).where(CleanupJob.id == identity).values(
            status="succeeded",
        ))
        await db.commit()
    async with reopened.shared(owner):
        pass


async def test_cancelled_producer_thread_holds_admission_until_it_actually_stops(admission):
    gate, _factory, owner, _other = admission
    started, release, finished = Event(), Event(), Event()

    def write():
        started.set()
        assert release.wait(3)
        finished.set()

    async def producer():
        async with gate.shared(owner):
            await joined_thread(write)

    task = asyncio.create_task(producer())
    try:
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 0.2)
        with pytest.raises(AdmissionError):
            async with gate.exclusive(owner, timeout=0.02):
                pass
        assert not finished.is_set()
    finally:
        release.set()
    await asyncio.wait_for(gate.drain_threads(), 2)
    assert finished.is_set()
    async with gate.exclusive(owner):
        pass


@pytest.mark.parametrize("kind", ["skill", "file"])
async def test_actual_persistence_calls_keep_their_child_admission_on_cancel(
    admission, tmp_path, monkeypatch, kind,
):
    from app.services.object_storage import LocalPdfObjectStorage
    from app.services.skills import SkillSpec, SkillStore
    from app.tools.skills import SkillSave, save

    gate, _factory, owner, other = admission
    started, release = Event(), Event()
    store = SkillStore(tmp_path / "skills")
    storage = LocalPdfObjectStorage(tmp_path / "objects")
    if kind == "skill":
        original = store.save

        def delayed(*args, **kwargs):
            started.set()
            assert release.wait(3)
            return original(*args, **kwargs)

        monkeypatch.setattr(store, "save", delayed)
        monkeypatch.setattr("app.tools.skills.skill_store", lambda _settings: store)
    else:
        original = Path.write_bytes

        def delayed(path, data):
            started.set()
            assert release.wait(3)
            return original(path, data)

        monkeypatch.setattr(Path, "write_bytes", delayed)

    async def producer():
        async with gate.shared(owner):
            if kind == "file":
                await storage.put(owner, "synthetic-job", b"SYNTHETIC_PDF_BYTES")
            else:
                await save(SkillSave(skill=SkillSpec(
                    name="synthetic_report", title="Synthetic report", description="Synthetic only",
                    goal="Read {input}", procedure=["Read {input}", "Summarize"],
                    output_format="Markdown",
                )), SimpleNamespace(user=SimpleNamespace(id=owner), settings=None))

    task = asyncio.create_task(producer())
    try:
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 0.2)
        with pytest.raises(AdmissionError):
            async with gate.exclusive(owner, timeout=0.02):
                pass
        async with gate.exclusive(other):
            pass
    finally:
        release.set()
        await asyncio.wait_for(gate.drain_threads(), 2)
    if kind == "file":
        assert await storage.get(owner, "synthetic-job") == b"SYNTHETIC_PDF_BYTES"
    else:
        assert store.run(owner, "synthetic_report", {"input": "SYNTHETIC"})["goal"] == (
            "Read SYNTHETIC")


async def test_cancelled_thread_error_is_collected_and_releases_owner(admission):
    gate, _factory, owner, _other = admission
    started, release = Event(), Event()

    def fail():
        started.set()
        assert release.wait(3)
        raise ValueError("SYNTHETIC_PRIVATE_ERROR_MUST_NOT_BE_LOGGED")

    async def producer():
        async with gate.shared(owner):
            await joined_thread(fail)

    task = asyncio.create_task(producer())
    try:
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 0.2)
    finally:
        release.set()
        await asyncio.wait_for(gate.drain_threads(), 2)
    assert not gate._threads
    async with gate.exclusive(owner):
        pass


async def test_temporary_pdf_cleanup_joins_the_write_before_unlink(
    admission, tmp_path, monkeypatch,
):
    from app.services.object_storage import PdfObjectStorage

    gate, _factory, owner, _other = admission
    started, release = Event(), Event()
    original = Path.write_bytes

    def delayed(path, data):
        started.set()
        assert release.wait(3)
        return original(path, data)

    class SyntheticStorage(PdfObjectStorage):
        async def get(self, owner, job_id):
            return b"SYNTHETIC_ONLY"

    monkeypatch.setattr(Path, "write_bytes", delayed)
    monkeypatch.setattr("app.services.object_storage.mkstemp", partial(mkstemp, dir=tmp_path))

    async def producer():
        async with gate.shared(owner):
            await SyntheticStorage().processing_path(owner, "synthetic-job")

    task = asyncio.create_task(producer())
    try:
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        with pytest.raises(AdmissionError):
            async with gate.exclusive(owner, timeout=0.02):
                pass
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
    assert not list(tmp_path.glob("veridra-pdf-*.pdf"))


async def test_all_actual_orchestrators_and_registry_stop_before_model_tool_or_audit(admission):
    from app.agent.adk_orchestrator import AdkOrchestrator
    from app.agent.compiler import CompilerOrchestrator
    from app.agent.orchestrator import AgentOrchestrator

    gate, factory, owner, _other = admission
    await queued(admission)
    registry = ToolRegistry()
    registry.admission_gate = gate
    for kind in (AdkOrchestrator, CompilerOrchestrator, AgentOrchestrator):
        orchestrator = object.__new__(kind)
        orchestrator.registry = registry
        with pytest.raises(AdmissionError):
            await orchestrator.run(user=SimpleNamespace(id=owner), session_id="synthetic",
                                   request_id="synthetic", user_message="SYNTHETIC_INPUT")
    async with factory() as db:
        with pytest.raises(AdmissionError):
            await registry.execute("must-not-resolve-a-tool", {"body": "SYNTHETIC_INPUT"},
                                   SimpleNamespace(user=SimpleNamespace(id=owner), db=db))
        assert await db.scalar(select(func.count()).select_from(AuditEvent)) == 0


async def test_agent_decorator_holds_admission_across_await_and_releases_on_error(admission):
    gate, _factory, owner, _other = admission
    started, release = asyncio.Event(), asyncio.Event()

    class Agent:
        registry = SimpleNamespace(admission_gate=gate)

        @guarded_agent_run
        async def run(self, *, user):
            started.set()
            await release.wait()
            raise ValueError("SYNTHETIC_PRIVATE_ERROR")

    task = asyncio.create_task(Agent().run(user=SimpleNamespace(id=owner)))
    await started.wait()
    with pytest.raises(AdmissionError):
        async with gate.exclusive(owner, timeout=0.02):
            pass
    release.set()
    with pytest.raises(ValueError):
        await task
    async with gate.exclusive(owner):
        pass


async def test_signed_session_asgi_is_held_through_last_stream_chunk_and_pending_blocks(admission):
    gate, _factory, owner, _other = admission
    started, release = asyncio.Event(), asyncio.Event()

    async def login(request):
        request.session["user_id"] = owner
        return JSONResponse({"ok": True})

    async def stream(_request):
        async def body():
            started.set()
            yield b"synthetic-first"
            await release.wait()
            yield b"synthetic-last"
        return StreamingResponse(body())

    app = Starlette(routes=[Route("/api/auth/synthetic", login), Route("/api/stream", stream)])
    app.state.retention_gate = gate
    app.add_middleware(OwnerAdmissionMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="synthetic-signing-key-not-production")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://test") as client:
        assert (await client.get("/api/auth/synthetic")).status_code == 200
        task = asyncio.create_task(client.get("/api/stream"))
        await started.wait()
        with pytest.raises(AdmissionError):
            async with gate.exclusive(owner, timeout=0.02):
                pass
        release.set()
        response = await task
        assert response.content == b"synthetic-firstsynthetic-last"
        await queued(admission)
        response = await client.get("/api/stream")
        assert response.status_code == 503
        assert response.json()["code"] == "data_cleanup_pending"
        assert response.headers["retry-after"] == "2"
        assert response.headers["cache-control"] == "no-store"


async def test_scheduler_defers_busy_owner_without_calendar_reads_or_consuming_slot(admission):
    gate, factory, owner, other = admission
    await queued(admission)
    settings = SimpleNamespace(beta_email_allowed=lambda _email: True)
    async with factory() as db:
        result = await enqueue_for_invited_users(db, settings, kind="morning",
                                                 dedupe_key="synthetic",
                                                 registry=SimpleNamespace(admission_gate=gate))
        assert result["created"] == 1 and result["deferred_users"] == 1
        assert result["status"] == "deferred_cleanup"
        assert await db.scalar(select(func.count()).select_from(ScheduledJob).where(
            ScheduledJob.user_id == owner,
        )) == 0
        assert await db.scalar(select(func.count()).select_from(ScheduledJob).where(
            ScheduledJob.user_id == other,
        )) == 1


def test_native_evaluation_skips_blocked_owners_without_spending_attempts(tmp_path):
    queue = EvaluationQueue(tmp_path)
    own = queue.enqueue("synthetic-owner-a", STAMP)
    other = queue.enqueue("synthetic-owner-b", STAMP)
    assert queue.claim(STAMP, blocked_owners={"synthetic-owner-a"})["id"] == other
    assert queue.claim(STAMP, blocked_owners={"synthetic-owner-a"}) is None
    assert queue.get("synthetic-owner-a", own)["attempts"] == 0
    assert queue.get("synthetic-owner-a", own)["status"] == "queued"


def test_relational_evaluation_skips_blocked_owners_without_spending_attempts(tmp_path):
    from app.services.relational_evaluation import RelationalEvaluationQueue

    engine = create_engine(f"sqlite:///{tmp_path / 'evaluation.db'}")
    try:
        RelationalEvaluationQueue.create_schema(engine)
        queue = RelationalEvaluationQueue(engine)
        own = queue.enqueue("synthetic-owner-a", STAMP)
        other = queue.enqueue("synthetic-owner-b", STAMP)
        assert queue.claim(STAMP, blocked_owners={"synthetic-owner-a"})["id"] == other
        assert queue.claim(STAMP, blocked_owners={"synthetic-owner-a"}) is None
        assert queue.get("synthetic-owner-a", own)["attempts"] == 0
        assert queue.get("synthetic-owner-a", own)["status"] == "queued"
    finally:
        engine.dispose()


async def test_remote_actions_defer_before_consuming_nonce_and_can_retry_after_cleanup(
    admission, tmp_path, monkeypatch,
):
    from fastapi import FastAPI

    from app.api.gmail_remote import router
    from app.core.config import Settings
    from app.db.session import get_db
    from app.services.gmail_remote import RemoteActionSigner

    gate, factory, owner, _other = admission
    _gate, identity = await queued(admission)
    settings = Settings(_env_file=None, data_dir=tmp_path,
                        database_url=f"sqlite+aiosqlite:///{tmp_path / 'remote.db'}")
    monkeypatch.setattr("app.api.gmail_remote.get_settings", lambda: settings)
    registry = ToolRegistry()
    registry.admission_gate = gate
    registry.execute = AsyncMock(return_value=SimpleNamespace(
        draft_id="synthetic-draft", gmail_draft_url="https://mail.google.com/mail/u/0/#drafts",
    ))
    app = FastAPI()
    app.include_router(router)
    app.state.registry = registry

    async def request_db():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db] = request_db
    token = RemoteActionSigner.sign_action("create_reply_draft", {
        "thread_id": "synthetic-thread", "recipient": "synthetic@example.invalid",
        "source_snippet": "SYNTHETIC_ONLY",
    }, owner, settings.app_secret)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://test") as client:
        for path, body in (("/api/gmail/remote/action", {"json": {"token": token}}),
                           ("/api/gmail/remote/action/confirm", {"data": {"token": token}})):
            response = await client.post(path, **body)
            assert response.status_code == 503
            assert response.headers["retry-after"] == "2"
            assert "no-store" in response.headers["cache-control"]
            assert "Dữ liệu đang được dọn" in response.text
        assert registry.execute.await_count == 0
        async with factory() as db:
            await db.execute(update(CleanupJob).where(CleanupJob.id == identity).values(
                status="succeeded",
            ))
            await db.commit()
        response = await client.post("/api/gmail/remote/action", json={"token": token})
        assert response.status_code == 200
        assert response.json()["draft_id"] == "synthetic-draft"
        assert registry.execute.await_count == 1
        response = await client.post("/api/gmail/remote/action", json={"token": token})
        assert response.status_code == 409
        assert registry.execute.await_count == 1


async def test_trace_maintenance_does_not_change_an_open_cleanup_snapshot(admission):
    from app.services.agentops import expire_run_traces

    _gate, factory, owner, other = admission
    _gate, identity = await queued(admission)
    rows = []
    async with factory() as db:
        for user in (owner, other):
            chat = ChatSession(user_id=user, title="Synthetic")
            db.add(chat)
            await db.flush()
            row = Message(user_id=user, session_id=chat.id, role="assistant",
                          content="SYNTHETIC_ONLY", status="completed",
                          created_at=NOW - timedelta(days=40),
                          trace_json='[{"stage":"usage"}]')
            db.add(row)
            rows.append(row)
        await db.commit()
        assert await expire_run_traces(db, now=NOW) == 1
        await db.commit()
    async with factory() as db:
        assert (await db.get(Message, rows[0].id)).trace_json != "[]"
        assert (await db.get(Message, rows[1].id)).trace_json == "[]"
        await db.execute(update(CleanupJob).where(CleanupJob.id == identity).values(
            status="succeeded",
        ))
        await db.commit()
        assert await expire_run_traces(db, now=NOW) == 1
        await db.commit()


@pytest.mark.parametrize("kind", ["chat", "pdf", "scheduled"])
async def test_core_workers_skip_pending_cleanup_owner_without_consuming_attempts(admission, kind):
    from app.services.chat_tasks import claim as claim_chat
    from app.services.pdf_jobs import claim as claim_pdf
    from app.services.scheduled_jobs import _claim as claim_scheduled

    _gate, factory, owner, other = admission
    await queued(admission)
    rows = []
    async with factory() as db:
        for user in (owner, other):
            if kind == "chat":
                chat = ChatSession(user_id=user, title="Synthetic")
                db.add(chat)
                await db.flush()
                row = ChatTask(user_id=user, session_id=chat.id, client_key="synthetic",
                               payload_json="{}")
            elif kind == "pdf":
                row = PdfIngestionJob(user_id=user, name="synthetic.pdf", content_hash="synthetic",
                                       size_bytes=1)
            else:
                row = ScheduledJob(user_id=user, kind="morning", dedupe_key="synthetic")
            db.add(row)
            rows.append(row)
        await db.commit()
    if kind == "chat":
        selected = await claim_chat(factory, now=STAMP)
        assert selected["owner"] == other
    elif kind == "pdf":
        selected = await claim_pdf(factory, STAMP)
        assert selected[0] == rows[1].id
    else:
        selected = await claim_scheduled(factory, now=STAMP)
        assert selected["user_id"] == other
    async with factory() as db:
        own = await db.get(type(rows[0]), rows[0].id)
        assert own.status == "queued" and own.attempts == 0
