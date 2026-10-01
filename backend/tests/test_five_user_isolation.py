"""Five concurrent local users must not read one another's private records.

This exercises HTTP authorization boundaries with test-only identity injection;
it does not claim to test Google OAuth or a deployed multi-user server.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.artifacts import router as artifacts_router
from app.api.chat import router as chat_router
from app.api.dependencies import get_current_user
from app.api.local_sources import router as sources_router
from app.api.memory import router as memory_router
from app.core.config import Settings
from app.db.models import (
    Base,
    ChatSession,
    LocalSource,
    LongTermMemory,
    Message,
    ProviderCredential,
    SavedArtifact,
    User,
    UserRole,
)
from app.db.session import get_db
from app.services.provider_credentials import encrypt_provider_secret
from app.services.user_inference import UserInferencePool


@pytest.mark.asyncio
async def test_five_users_cannot_read_each_others_chat_local_memory_or_export(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'five-users.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    users: dict[str, User] = {}
    records: dict[str, dict[str, str]] = {}
    async with factory() as db:
        for number in range(5):
            label = f"user-{number}"
            user = User(
                email=f"{label}@example.invalid",
                display_name=label,
                role=UserRole.EDITOR.value,
            )
            db.add(user)
            await db.flush()
            session = ChatSession(user_id=user.id, title=f"Private chat {label}")
            artifact = SavedArtifact(
                user_id=user.id,
                creation_key=str(uuid4()),
                title=f"Private report {label}",
                kind="report",
                content=f"# Private report {label}",
            )
            source = LocalSource(
                user_id=user.id,
                name=f"{label}.md",
                content=f"Private source {label}",
                content_hash=f"{number:064x}",
            )
            memory = LongTermMemory(
                user_id=user.id,
                kind="fact",
                content=f"Private memory {label}",
                normalized_hash=f"{number + 10:064x}",
            )
            db.add_all([session, artifact, source, memory])
            await db.flush()
            db.add(Message(
                session_id=session.id,
                user_id=user.id,
                role="user",
                content=f"Private message {label}",
            ))
            users[label] = user
            records[label] = {
                "session": session.id,
                "artifact": artifact.id,
                "source": source.id,
            }
        await db.commit()

    app = FastAPI()
    for router in (chat_router, sources_router, memory_router, artifacts_router):
        app.include_router(router)

    async def current_user(request: Request):
        return users[request.headers["x-qa-user"]]

    async def session_dependency():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db] = session_dependency
    transport = ASGITransport(app=app)

    async def verify(label: str):
        own = records[label]
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"x-qa-user": label},
        ) as client:
            sessions = await client.get("/api/chat/sessions")
            assert sessions.status_code == 200
            assert [row["id"] for row in sessions.json()] == [own["session"]]

            messages = await client.get(f"/api/chat/sessions/{own['session']}/messages")
            assert messages.status_code == 200
            assert [row["content"] for row in messages.json()] == [f"Private message {label}"]

            sources = await client.get("/api/local-sources")
            assert sources.status_code == 200
            assert [row["id"] for row in sources.json()] == [own["source"]]

            memories = await client.get("/api/memories")
            assert memories.status_code == 200
            assert [row["content"] for row in memories.json()["memories"]] == [
                f"Private memory {label}"
            ]

            exported = await client.get(f"/api/artifacts/{own['artifact']}/export")
            assert exported.status_code == 200
            assert f"Private report {label}" in exported.text

            for other, foreign in records.items():
                if other == label:
                    continue
                for path in (
                    f"/api/chat/sessions/{foreign['session']}/messages",
                    f"/api/local-sources/{foreign['source']}/text",
                    f"/api/artifacts/{foreign['artifact']}/export",
                ):
                    denied = await client.get(path)
                    assert denied.status_code == 404, (label, other, path, denied.status_code)

    try:
        await asyncio.gather(*(verify(label) for label in users))
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_five_users_get_distinct_byok_runtimes_even_when_one_rotates(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'five-keys.db'}"
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(
        _env_file=None,
        app_secret="five-user-isolation-secret-long-enough",
        database_url=database_url,
        data_dir=tmp_path,
        gemini_api_key="operator-environment-key",
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    user_ids = []
    async with factory() as db:
        for number in range(5):
            user = User(
                email=f"byok-{number}@example.invalid",
                display_name=f"BYOK {number}",
                role=UserRole.EDITOR.value,
            )
            db.add(user)
            await db.flush()
            user_ids.append(user.id)
            db.add(ProviderCredential(
                user_id=user.id,
                provider="gemini",
                display_name=f"Private key {number}",
                fingerprint=f"{number + 1:020x}",
                encrypted_secret=encrypt_provider_secret(f"private-key-{number}", settings),
                is_active=True,
                status="ready",
            ))
        await db.commit()

    async def make(runtime_settings, _registry):
        return SimpleNamespace(settings=runtime_settings, close=AsyncMock())

    pool = UserInferencePool(
        settings=settings,
        registry=object(),
        factory=make,
        environment_orchestrator=SimpleNamespace(close=AsyncMock()),
    )

    async def get_runtime(user_id):
        async with factory() as db:
            return await pool.get(db, user_id)

    try:
        runtimes = await asyncio.gather(*(get_runtime(user_id) for user_id in user_ids))
        assert len({id(runtime) for runtime in runtimes}) == 5
        assert [runtime.settings.gemini_api_key for runtime in runtimes] == [
            f"private-key-{number}" for number in range(5)
        ]
        assert settings.gemini_api_key == "operator-environment-key"

        async with factory() as db:
            own_credentials = await db.get(ProviderCredential, runtimes[0]._provider_credential_id)
            own_credentials.is_active = False
            db.add(ProviderCredential(
                user_id=user_ids[0],
                provider="gemini",
                display_name="Rotated private key",
                fingerprint="f" * 20,
                encrypted_secret=encrypt_provider_secret("rotated-private-key", settings),
                is_active=True,
                status="ready",
            ))
            await db.commit()

        await pool.invalidate(user_ids[0])
        rotated = await get_runtime(user_ids[0])
        assert rotated.settings.gemini_api_key == "rotated-private-key"
        assert runtimes[0].close.await_count == 1
        others_after = await asyncio.gather(*(get_runtime(user_id) for user_id in user_ids[1:]))
        assert all(
            before is after
            for before, after in zip(runtimes[1:], others_after, strict=True)
        )
        assert all(runtime.close.await_count == 0 for runtime in runtimes[1:])
    finally:
        await pool.close()
        await engine.dispose()
