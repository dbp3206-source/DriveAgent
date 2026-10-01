"""Credential-pinned Gemini client with durable, privacy-safe circuit state."""

from __future__ import annotations

import asyncio
import sqlite3
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from google import genai

from app.services.quota import quota_namespace
from app.tools.contracts import ToolError


class RequestPinningGate:
    """Let active requests finish before a hot credential switch is published."""

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._active = 0
        self._active_by_user: dict[str, int] = {}
        self._switching = False
        self._retired_by_user: dict[str, list[Callable[[], Awaitable[None]]]] = {}

    @asynccontextmanager
    async def request(self, user_id: str = ""):
        async with self._condition:
            await self._condition.wait_for(lambda: not self._switching)
            self._active += 1
            self._active_by_user[user_id] = self._active_by_user.get(user_id, 0) + 1
        try:
            yield
        finally:
            retired: list[Callable[[], Awaitable[None]]] = []
            async with self._condition:
                self._active -= 1
                remaining = self._active_by_user[user_id] - 1
                if remaining:
                    self._active_by_user[user_id] = remaining
                else:
                    del self._active_by_user[user_id]
                    retired = self._retired_by_user.pop(user_id, [])
                self._condition.notify_all()
            if retired:
                await asyncio.shield(
                    asyncio.gather(*(close() for close in retired), return_exceptions=True)
                )

    async def retire(self, user_id: str, close: Callable[[], Awaitable[None]]) -> None:
        """Retire an old runtime once all requests that may hold it have finished."""

        async with self._condition:
            if self._active_by_user.get(user_id, 0):
                self._retired_by_user.setdefault(user_id, []).append(close)
                return
        await close()

    @asynccontextmanager
    async def switch(self, timeout: float = 3.0):
        async with self._condition:
            self._switching = True
            try:
                await asyncio.wait_for(
                    self._condition.wait_for(lambda: self._active == 0),
                    timeout=timeout,
                )
            except TimeoutError as exc:
                self._switching = False
                self._condition.notify_all()
                raise TimeoutError("Active inference has not drained") from exc
        try:
            yield
        finally:
            async with self._condition:
                self._switching = False
                self._condition.notify_all()


def provider_error_class(exc: Exception) -> tuple[str, int, bool]:
    """Return a bounded class, cooldown seconds and whether the failure is transient."""

    code = int(getattr(exc, "code", 0) or 0)
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if code in {401, 403}:
        return "authentication", 0, False
    if code == 429 or "resource_exhausted" in message or "quota" in message:
        return "quota", 60, True
    if code in {500, 502, 503, 504} or any(
        value in name for value in ("timeout", "connection", "transport")
    ):
        return "availability", 30, True
    return "provider", 0, False


class ProviderCircuitStore:
    """SQLite circuit state scoped to a one-way credential namespace."""

    def __init__(self, path: Path, credential: str):
        self.path = path
        self.namespace = quota_namespace(credential)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS provider_circuits (
                namespace TEXT NOT NULL, capability TEXT NOT NULL,
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                opened_until REAL, last_error_class TEXT, updated_at REAL NOT NULL,
                PRIMARY KEY(namespace, capability))"""
            )

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def before_request(self, capability: str, *, now: float | None = None) -> None:
        stamp = time.time() if now is None else now
        with self._connect() as db:
            row = db.execute(
                "SELECT opened_until,last_error_class FROM provider_circuits "
                "WHERE namespace=? AND capability=?",
                (self.namespace, capability),
            ).fetchone()
        if row and row[0] and float(row[0]) > stamp:
            wait = max(1, int(float(row[0]) - stamp + 0.999))
            raise ToolError(
                f"Gemini đang tạm nghỉ sau lỗi {row[1] or 'provider'}; thử lại sau {wait} giây. "
                "Các chức năng local vẫn dùng được.",
                code="gemini_circuit_open",
                retryable=True,
            )

    def success(self, capability: str, *, now: float | None = None) -> None:
        stamp = time.time() if now is None else now
        with self._connect() as db:
            db.execute(
                "INSERT INTO provider_circuits(namespace,capability,consecutive_failures,"
                "opened_until,last_error_class,updated_at) VALUES(?,?,0,NULL,NULL,?) "
                "ON CONFLICT(namespace,capability) DO UPDATE SET consecutive_failures=0,"
                "opened_until=NULL,last_error_class=NULL,updated_at=excluded.updated_at",
                (self.namespace, capability, stamp),
            )

    def failure(self, capability: str, exc: Exception, *, now: float | None = None) -> str:
        stamp = time.time() if now is None else now
        error_class, cooldown, transient = provider_error_class(exc)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT consecutive_failures FROM provider_circuits "
                "WHERE namespace=? AND capability=?",
                (self.namespace, capability),
            ).fetchone()
            failures = int(row[0] if row else 0) + 1
            should_open = error_class == "quota" or (transient and failures >= 3)
            opened_until = stamp + cooldown if should_open and cooldown else None
            db.execute(
                "INSERT INTO provider_circuits(namespace,capability,consecutive_failures,"
                "opened_until,last_error_class,updated_at) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(namespace,capability) DO UPDATE SET "
                "consecutive_failures=excluded.consecutive_failures,"
                "opened_until=excluded.opened_until,last_error_class=excluded.last_error_class,"
                "updated_at=excluded.updated_at",
                (
                    self.namespace,
                    capability,
                    failures,
                    opened_until,
                    error_class,
                    stamp,
                ),
            )
        return error_class

    def snapshot(self, *, now: float | None = None) -> list[dict[str, Any]]:
        stamp = time.time() if now is None else now
        with self._connect() as db:
            rows = db.execute(
                "SELECT capability,consecutive_failures,opened_until,last_error_class "
                "FROM provider_circuits WHERE namespace=? ORDER BY capability",
                (self.namespace,),
            ).fetchall()
        return [
            {
                "capability": row[0],
                "consecutive_failures": int(row[1]),
                "circuit_open": bool(row[2] and float(row[2]) > stamp),
                "retry_after_seconds": max(0, int(float(row[2]) - stamp)) if row[2] else 0,
                "last_error_class": row[3],
            }
            for row in rows
        ]


class _AsyncModels:
    def __init__(
        self, models: Any, circuit: ProviderCircuitStore, capability: str = "generate"
    ):
        self._models = models
        self._circuit = circuit
        self._capability = capability

    async def generate_content(self, *args: Any, **kwargs: Any) -> Any:
        await asyncio.to_thread(self._circuit.before_request, self._capability)
        try:
            result = await self._models.generate_content(*args, **kwargs)
        except Exception as exc:
            await asyncio.to_thread(self._circuit.failure, self._capability, exc)
            raise
        await asyncio.to_thread(self._circuit.success, self._capability)
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._models, name)


class _AsyncClient:
    def __init__(
        self, aio: Any, circuit: ProviderCircuitStore, capability: str = "generate"
    ):
        self._aio = aio
        self.models = _AsyncModels(aio.models, circuit, capability)

    async def aclose(self) -> None:
        await self._aio.aclose()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._aio, name)


class _SyncModels:
    def __init__(self, models: Any, circuit: ProviderCircuitStore):
        self._models = models
        self._circuit = circuit

    def embed_content(self, *args: Any, **kwargs: Any) -> Any:
        self._circuit.before_request("embedding")
        try:
            result = self._models.embed_content(*args, **kwargs)
        except Exception as exc:
            self._circuit.failure("embedding", exc)
            raise
        self._circuit.success("embedding")
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._models, name)


class InferenceGatewayClient:
    """Shape-compatible proxy around google.genai.Client."""

    def __init__(
        self,
        client: Any,
        circuit: ProviderCircuitStore,
        *,
        async_capability: str = "generate",
    ):
        self._client = client
        self.aio = _AsyncClient(client.aio, circuit, async_capability)
        if hasattr(client, "models"):
            self.models = _SyncModels(client.models, circuit)

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close:
            close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def create_inference_client(
    *,
    api_key: str,
    data_dir: Path,
    client_factory: Any = genai.Client,
    async_capability: str = "generate",
    settings: Any = None,
    **kwargs: Any,
) -> Any:
    """Build one credential-pinned client; plaintext never enters circuit storage."""

    raw = client_factory(api_key=api_key, **kwargs)
    if settings is None:
        circuit = ProviderCircuitStore(data_dir / "provider_state.db", api_key)
    else:
        from app.services.relational_circuit import circuit_store

        circuit = circuit_store(settings, api_key)
    return InferenceGatewayClient(
        raw, circuit, async_capability=async_capability
    )
