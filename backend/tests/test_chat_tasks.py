import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from time import time
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agent.orchestrator import AgentRunResult
from app.api.chat_tasks import SubmitTask, cancel, enqueue, get_task
from app.db.models import AuditEvent, Base, ChatTask, Message, User
from app.services.chat_tasks import claim, execute_one, fence


@pytest_asyncio.fixture
async def queue(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'queue.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        owner = User(email="queue@example.com", display_name="Queue", role="editor")
        other = User(email="other@example.com", display_name="Other", role="editor")
        db.add_all([owner, other])
        await db.commit()
    yield factory, owner, other
    await engine.dispose()


async def submit(queue):
    factory, owner, _ = queue
    payload = SubmitTask(message="synthetic queued question", client_key=str(uuid4()))
    async with factory() as db:
        return await enqueue(payload, owner, db), payload


async def test_enqueue_idempotency_owner_isolation_and_request_retention(queue):
    factory, owner, other = queue
    task, payload = await submit(queue)
    async with factory() as db:
        assert (await enqueue(payload, owner, db))["id"] == task["id"]
        assert await db.scalar(select(func.count()).select_from(Message)) == 1
        with pytest.raises(HTTPException) as error:
            await get_task(task["id"], other, db)
        assert error.value.status_code == 404
        with pytest.raises(HTTPException) as error:
            await enqueue(payload.model_copy(update={"message": "different"}), owner, db)
        assert error.value.status_code == 409
        with pytest.raises(HTTPException) as error:
            await enqueue(payload.model_copy(update={"client_key": str(uuid4())}), owner, db)
        assert error.value.status_code == 409


async def test_expired_lease_reclaims_with_fencing_and_max_attempts(queue):
    factory, _, _ = queue
    task, _ = await submit(queue)
    first = await claim(factory, now=time())
    assert await claim(factory, now=time()) is None
    second = await claim(factory, now=time() + 121)
    assert first["id"] == second["id"] == task["id"]
    async with factory() as db:
        with pytest.raises(asyncio.CancelledError):
            await fence(db, first["id"], first["token"], first["attempt"], status="completed")
        await db.rollback()
    assert (await claim(factory, now=time() + 242))["attempt"] == 3
    assert await claim(factory, now=time() + 363) is None
    async with factory() as db:
        assert (await db.get(ChatTask, task["id"])).status == "failed"
        assert (await db.scalar(select(Message))).status == "failed"


async def test_worker_checkpoints_answer_and_does_not_duplicate_after_reopen(queue):
    factory, owner, _ = queue
    task, _ = await submit(queue)

    class Model:
        calls = 0

        async def run(self, **kwargs):
            self.calls += 1
            return AgentRunResult(answer="Synthetic answer", plan=[], trace=[], citations=[])

    model = Model()
    app = SimpleNamespace(state=SimpleNamespace(orchestrator=model))
    assert await execute_one(factory, app)
    # A fresh worker/database session sees the checkpoint, not a pending task.
    assert not await execute_one(factory, app)
    async with factory() as db:
        snapshot = await get_task(task["id"], owner, db)
        assert snapshot["status"] == "completed"
        assert snapshot["result"]["answer"] == "Synthetic answer"
        assert model.calls == 1
        assert await db.scalar(select(func.count()).select_from(Message)) == 2


async def test_cancel_prevents_publication_and_preserves_user_turn(queue):
    factory, owner, _ = queue
    task, _ = await submit(queue)
    claimed = await claim(factory, now=time())
    async with factory() as db:
        assert (await cancel(task["id"], owner, db))["status"] == "cancelled"
    async with factory() as db:
        with pytest.raises(asyncio.CancelledError):
            await fence(db, claimed["id"], claimed["token"], claimed["attempt"],
                        status="completed", result_json=json.dumps({"answer": "stale"}))
        await db.rollback()
        assert (await db.scalar(select(Message))).status == "cancelled"


async def test_process_interruption_keeps_lease_for_restart_without_duplicate_user(queue):
    factory, owner, _ = queue
    task, _ = await submit(queue)

    class Interrupted:
        async def run(self, **kwargs):
            raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await execute_one(
            factory, SimpleNamespace(state=SimpleNamespace(orchestrator=Interrupted())))
    async with factory() as db:
        row = await db.get(ChatTask, task["id"])
        assert row.status == "running"
        row.lease_until = 0
        await db.commit()

    class Recovered:
        async def run(self, **kwargs):
            return AgentRunResult(answer="Resumed read-only turn", plan=[], trace=[], citations=[])

    assert await execute_one(
        factory, SimpleNamespace(state=SimpleNamespace(orchestrator=Recovered())))
    async with factory() as db:
        snapshot = await get_task(task["id"], owner, db)
        assert snapshot["status"] == "completed"
        assert snapshot["attempts"] == 2
        assert await db.scalar(select(func.count()).select_from(Message)) == 2


async def test_ambiguous_memory_write_is_not_replayed_after_restart(queue):
    factory, owner, _ = queue
    task, _ = await submit(queue)
    await claim(factory, now=time())
    async with factory() as db:
        row = await db.get(ChatTask, task["id"])
        row.lease_until = 0
        db.add(AuditEvent(request_id=task["id"], user_id=owner.id,
                          tool_name="memory_save", status="success"))
        await db.commit()
    assert await claim(factory, now=time()) is None
    async with factory() as db:
        row = await get_task(task["id"], owner, db)
        assert row["status"] == "failed"
        assert "Bộ nhớ" in row["error"]


async def test_parallel_duplicate_enqueue_serializes_without_duplicate_messages(queue):
    factory, owner, _ = queue
    payload = SubmitTask(message="duplicate retry", client_key=str(uuid4()))

    async def send():
        async with factory() as db:
            return await enqueue(payload, owner, db)

    tasks = await asyncio.gather(*(send() for _ in range(4)))
    assert len({task["id"] for task in tasks}) == 1
    async with factory() as db:
        assert await db.scalar(select(func.count()).select_from(Message)) == 1


async def test_cancellation_of_completed_task_does_not_erase_checkpoint(queue):
    factory, owner, _ = queue
    task, _ = await submit(queue)
    async with factory() as db:
        row = await db.get(ChatTask, task["id"])
        row.status = "completed"
        row.result_json = json.dumps({"answer": "done"})
        await db.commit()
        response = await cancel(task["id"], owner, db)
        assert response["status"] == "completed"
        assert response["result"]["answer"] == "done"


async def test_real_worker_process_crash_and_fresh_process_recovery(queue, tmp_path):
    """Kill only the disposable fixture worker; never a live user app/provider."""
    factory, owner, _ = queue
    task, _ = await submit(queue)
    code = r'''
import asyncio, os, sys
from types import SimpleNamespace
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.agent.orchestrator import AgentRunResult
from app.services.chat_tasks import execute_one
class Model:
    async def run(self, **kwargs):
        if sys.argv[2] == "crash":
            os._exit(74)
        return AgentRunResult(
            answer="Recovered from process crash", plan=[], trace=[], citations=[])
async def main():
    engine = create_async_engine("sqlite+aiosqlite:///" + sys.argv[1])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await execute_one(factory, SimpleNamespace(state=SimpleNamespace(orchestrator=Model())))
    await engine.dispose()
asyncio.run(main())
'''
    environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    crash = await asyncio.to_thread(subprocess.run,
        [sys.executable, "-c", code, str(tmp_path / "queue.db"), "crash"],
        env=environment, capture_output=True, timeout=30, **options)
    assert crash.returncode == 74, crash.stderr.decode(errors="replace")
    async with factory() as db:
        row = await db.get(ChatTask, task["id"])
        assert row.status == "running"
        assert row.attempts == 1
        # Advance lease eligibility without making the test sleep for 120s.
        row.lease_until = 0
        await db.commit()
    recovered = await asyncio.to_thread(subprocess.run,
        [sys.executable, "-c", code, str(tmp_path / "queue.db"), "recover"],
        env=environment, capture_output=True, timeout=30, **options)
    assert recovered.returncode == 0, recovered.stderr.decode(errors="replace")
    async with factory() as db:
        snapshot = await get_task(task["id"], owner, db)
        assert snapshot["status"] == "completed"
        assert snapshot["attempts"] == 2
        assert snapshot["result"]["answer"] == "Recovered from process crash"
        assert await db.scalar(select(func.count()).select_from(Message)) == 2


async def test_cancel_interrupts_inflight_worker_without_publishing_or_killing_worker(queue):
    factory, owner, _ = queue
    task, _ = await submit(queue)
    entered, interrupted = asyncio.Event(), asyncio.Event()

    class WaitingModel:
        async def run(self, **kwargs):
            entered.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                interrupted.set()
                raise

    execution = asyncio.create_task(execute_one(
        factory, SimpleNamespace(state=SimpleNamespace(orchestrator=WaitingModel()))))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        async with factory() as db:
            await cancel(task["id"], owner, db)
        assert await asyncio.wait_for(execution, timeout=5)
        assert interrupted.is_set()
        async with factory() as db:
            assert (await get_task(task["id"], owner, db))["status"] == "cancelled"
            assert await db.scalar(select(func.count()).select_from(Message)) == 1
    finally:
        execution.cancel()
