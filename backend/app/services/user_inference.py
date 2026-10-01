"""User-scoped Gemini runtimes for BYOK chat isolation.

The database already scopes credentials by user.  This pool carries that boundary
through to the actual orchestrator/client instead of mutating one process-global
``Settings`` object whenever somebody activates a key.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import APPROVED_GEMINI_MODELS, Settings
from app.services.provider_credentials import (
    alternate_gemini_key,
    effective_gemini_key,
)
from app.tools.contracts import ToolError

OrchestratorFactory = Callable[[Settings, Any], Awaitable[Any]]


def runtime_settings(settings: Settings, api_key: str) -> Settings:
    """Return an isolated settings snapshot with a real alternate model.

    A fallback that equals the primary model is not a fallback.  Preserve an
    explicit distinct configured model; otherwise choose the other approved
    free-tier model.  The original process settings are never mutated.
    """

    fallback = settings.gemini_fallback_model
    if fallback == settings.gemini_chat_model:
        fallback = next(
            model for model in sorted(APPROVED_GEMINI_MODELS)
            if model != settings.gemini_chat_model
        )
    return settings.model_copy(
        deep=True,
        update={"gemini_api_key": api_key.strip(), "gemini_fallback_model": fallback},
    )


async def user_runtime_settings(db: AsyncSession, user_id: str, settings: Settings) -> Settings:
    """API tools receive the same user-owned key policy as Chat.

    Local mode retains its explicit environment key for single-owner development.
    Hosted mode never grants an environment credential to a keyless invitee.
    """
    active = await effective_gemini_key(db, user_id, settings)
    if active is not None:
        return runtime_settings(settings, active[1])
    key = settings.gemini_api_key if settings.is_local_environment else ""
    return runtime_settings(settings, key)


class UserInferencePool:
    """Cache one initialized orchestrator per user and active credential."""

    def __init__(
        self,
        *,
        settings: Settings,
        registry: Any,
        factory: OrchestratorFactory,
        environment_orchestrator: Any,
        retire: Callable[[str, Callable[[], Awaitable[None]]], Awaitable[None]] | None = None,
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.factory = factory
        self.environment_orchestrator = environment_orchestrator
        self._retire = retire
        self._entries: dict[str, tuple[str, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def get(self, db: AsyncSession, user_id: str) -> Any:
        active = await effective_gemini_key(db, user_id, self.settings)
        if active is None:
            if not self.settings.is_local_environment:
                raise ToolError("Hãy thêm Gemini API key của bạn trong Cài đặt.",
                                code="model_not_configured")
            return self.environment_orchestrator
        credential_id, api_key, _is_failover = active
        cached = self._entries.get(user_id)
        if cached and cached[0] == credential_id:
            return cached[1]

        lock = self._locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            cached = self._entries.get(user_id)
            if cached and cached[0] == credential_id:
                return cached[1]
            replacement = await self.factory(
                runtime_settings(self.settings, api_key), self.registry
            )
            replacement.model_fallback_enabled = True
            if hasattr(replacement, "compiler"):
                replacement.compiler.model_fallback_enabled = True
            replacement._provider_credential_id = credential_id
            previous = self._entries.pop(user_id, None)
            self._entries[user_id] = (credential_id, replacement)
            if previous:
                await self._close_or_retire(user_id, previous[1])
            return replacement

    async def _close_or_retire(self, user_id: str, orchestrator: Any) -> None:
        if self._retire is None:
            await orchestrator.close()
        else:
            await self._retire(user_id, orchestrator.close)

    async def invalidate(self, user_id: str) -> None:
        lock = self._locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            previous = self._entries.pop(user_id, None)
            if previous:
                await self._close_or_retire(user_id, previous[1])

    async def get_alternate(
        self,
        db: AsyncSession,
        user_id: str,
        exclude_credential_ids: set[str] | None = None,
    ) -> Any | None:
        """Replace a failed runtime with exactly one distinct opted-in key."""

        current = self._entries.get(user_id)
        if current is None:
            return None
        replacement_key = await alternate_gemini_key(
            db,
            user_id,
            self.settings,
            exclude_credential_ids=set(exclude_credential_ids or ()) | {current[0]},
        )
        if replacement_key is None:
            return None
        credential_id, api_key = replacement_key
        lock = self._locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            replacement = await self.factory(
                runtime_settings(self.settings, api_key), self.registry
            )
            replacement.model_fallback_enabled = True
            if hasattr(replacement, "compiler"):
                replacement.compiler.model_fallback_enabled = True
            replacement._provider_credential_id = credential_id
            previous = self._entries.pop(user_id, None)
            self._entries[user_id] = (credential_id, replacement)
            if previous:
                await self._close_or_retire(user_id, previous[1])
            return replacement

    async def close(self) -> None:
        entries = list(self._entries.values())
        self._entries.clear()
        await asyncio.gather(
            *(orchestrator.close() for _, orchestrator in entries),
            return_exceptions=True,
        )
