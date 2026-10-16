"""Owner-scoped shared/exclusive admission for this single-process app profile.

Normal requests may run together. A confirmed cleanup survives restarts in SQL
and blocks new work; exclusive cleanup drains existing work before deleting.
Child tasks hold their own reader count, even when they inherit a parent context.
This is not a distributed lock: the packaged runtime is explicitly one worker.
"""

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.db.models import CleanupJob
from app.services.cleanup_jobs import OPEN
from app.tools.contracts import ToolError


class AdmissionError(ToolError):
    def __init__(self, code="data_cleanup_pending"):
        messages = {
            "data_cleanup_pending": "Dữ liệu đang được dọn. Hãy đợi hoàn tất rồi thử lại.",
            "data_cleanup_busy": "Còn việc đang xử lý. Hãy đợi xong trước khi dọn dữ liệu.",
            "data_cleanup_unavailable": "Chưa kiểm được trạng thái dọn dữ liệu. Hãy thử lại sau.",
        }
        super().__init__(messages[code], code=code, retryable=True)


@dataclass
class _State:
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    readers: int = 0
    exclusive: bool = False
    waiting: int = 0


@dataclass
class _Lease:
    gate: object
    owner: str
    readonly: bool = False
    active: bool = True


_lease: ContextVar[_Lease | None] = ContextVar("veridra_owner_admission", default=None)


def work_owner_available(column):
    """Core SQL workers do not claim or age retries for an owner being cleaned."""
    return column.not_in(select(CleanupJob.user_id).where(CleanupJob.status.in_(OPEN)))


async def joined_thread(function, *args, wait_on_cancel=False, **kwargs):
    """Keep an independent admission until a producer thread actually stops.

    With an admission, cancellation returns promptly to the request, but the
    reserved child stays alive and prevents cleanup. Without a gate, join the
    thread on cancellation rather than falsely claiming it has stopped.
    """
    parent = _lease.get()
    if parent is not None and parent.active and not wait_on_cancel:
        gate = parent.gate

        async def reserved():
            async with gate.shared(parent.owner, readonly=parent.readonly):
                return await asyncio.to_thread(function, *args, **kwargs)

        operation = asyncio.create_task(reserved())
        gate._threads.add(operation)

        def completed(task):
            gate._threads.discard(task)
            if not task.cancelled():
                task.exception()  # Do not log a possibly private producer error.

        operation.add_done_callback(completed)
        return await asyncio.shield(operation)
    operation = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    cancelled = False
    while not operation.done():
        try:
            await asyncio.shield(operation)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            if not cancelled:
                raise
            break
    if cancelled:
        # Retrieve any exception without printing its potentially private text.
        if not operation.cancelled():
            operation.exception()
        raise asyncio.CancelledError
    return operation.result()


class OwnerAdmission:
    def __init__(self, factory):
        self.factory = factory
        self._states: dict[str, _State] = {}
        self._threads: set[asyncio.Task] = set()

    async def drain_threads(self):
        """Lifespan must drain detached writers before closing their DB engines."""
        while self._threads:
            await asyncio.shield(asyncio.gather(*tuple(self._threads), return_exceptions=True))

    def _state(self, owner):
        if not isinstance(owner, str) or not owner or len(owner) > 200:
            raise AdmissionError("data_cleanup_unavailable")
        return self._states.setdefault(owner, _State())

    async def pending_owners(self):
        try:
            async with self.factory() as db:
                return set(await db.scalars(select(CleanupJob.user_id).where(
                    CleanupJob.status.in_(OPEN),
                )))
        except SQLAlchemyError:
            raise AdmissionError("data_cleanup_unavailable") from None

    async def _check_pending(self, owner, *, db=None, readonly=False):
        async def check(session):
            query = select(CleanupJob.sql_completed_at).where(
                CleanupJob.user_id == owner, CleanupJob.status.in_(OPEN),
            )
            # A scalar None cannot distinguish no job from a pre-SQL job.
            row = (await session.execute(query)).first()
            if row is not None and (not readonly or row[0] is None):
                raise AdmissionError()

        try:
            if db is not None:
                await check(db)
            else:
                async with self.factory() as session:
                    await check(session)
        except SQLAlchemyError:
            raise AdmissionError("data_cleanup_unavailable") from None

    @asynccontextmanager
    async def shared(self, owner, *, db=None, readonly=False):
        state = self._state(owner)
        parent = _lease.get()
        inherited = (parent is not None and parent.active and parent.gate is self
                     and parent.owner == owner)
        async with state.condition:
            if state.exclusive or state.waiting and not inherited:
                raise AdmissionError()
            state.readers += 1
        current = _Lease(self, owner, readonly=readonly)
        token = _lease.set(current)
        try:
            # A nested reader still reserves its own lifetime. Only avoid the
            # redundant SQL lookup while the inherited parent is actually alive.
            if not inherited or parent.readonly and not readonly:
                await self._check_pending(owner, db=db, readonly=readonly)
            yield
        finally:
            current.active = False
            _lease.reset(token)
            async with state.condition:
                state.readers -= 1
                state.condition.notify_all()

    @asynccontextmanager
    async def exclusive(self, owner, *, timeout=2):
        state = self._state(owner)
        acquired = False
        async with state.condition:
            state.waiting += 1
            try:
                async with asyncio.timeout(timeout):
                    await state.condition.wait_for(
                        lambda: not state.exclusive and not state.readers,
                    )
                state.exclusive = True
                acquired = True
            except TimeoutError:
                raise AdmissionError("data_cleanup_busy") from None
            finally:
                state.waiting -= 1
                state.condition.notify_all()
        try:
            yield
        finally:
            if acquired:
                async with state.condition:
                    state.exclusive = False
                    state.condition.notify_all()


def guarded_agent_run(function):
    """All orchestrators enter here, including protocol/background invocations."""
    @wraps(function)
    async def wrapped(self, *args, **kwargs):
        gate = getattr(self.registry, "admission_gate", None)
        if gate is None:
            return await function(self, *args, **kwargs)
        async with gate.shared(kwargs["user"].id):
            return await function(self, *args, **kwargs)
    return wrapped


class OwnerAdmissionMiddleware:
    """Install INSIDE SessionMiddleware; hold through the final streaming body."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        gate = getattr(scope.get("app").state, "retention_gate", None) if scope.get("app") else None
        path = scope.get("path", "")
        owner = scope.get("session", {}).get("user_id")
        exempt = (not path.startswith("/api/") or path.startswith(("/api/retention/", "/api/auth/"))
                  or path.startswith(("/api/mcp", "/api/a2a"))
                  or path in {"/api/health", "/api/health/ready"})
        if scope["type"] != "http" or gate is None or not owner or exempt:
            return await self.app(scope, receive, send)
        started = False

        async def tracked_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            readonly = scope.get("method") in {"GET", "HEAD", "OPTIONS"}
            async with gate.shared(owner, readonly=readonly):
                await self.app(scope, receive, tracked_send)
        except AdmissionError as error:
            if started:
                raise
            await JSONResponse(status_code=503, content={"detail": str(error), "code": error.code},
                               headers={"Retry-After": "2", "Cache-Control": "no-store"})(
                                   scope, receive, send)
