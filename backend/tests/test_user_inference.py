import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import Base, ProviderCredential, User
from app.services.inference_gateway import RequestPinningGate
from app.services.provider_credentials import encrypt_provider_secret
from app.services.user_inference import UserInferencePool, runtime_settings, user_runtime_settings
from app.tools.contracts import ToolError


@pytest.mark.asyncio
async def test_four_concurrent_api_users_receive_only_their_credential(monkeypatch):
    from app.api import drive

    settings = Settings(_env_file=None, environment="beta", gemini_api_key="owner-only")
    monkeypatch.setattr(drive, "get_settings", lambda: settings)

    async def effective(_db, user_id, _settings):
        return f"credential-{user_id}", f"private-{user_id}", False

    monkeypatch.setattr("app.services.user_inference.effective_gemini_key", effective)
    seen = {}

    async def execute(_tool, _arguments, context):
        await asyncio.sleep(0)
        seen[context.user.id] = context.settings.gemini_api_key
        return {"ok": True}

    request = SimpleNamespace(state=SimpleNamespace(request_id="four-api-users"),
                              app=SimpleNamespace(state=SimpleNamespace(
                                  registry=SimpleNamespace(execute=execute))))
    await asyncio.gather(*(drive.execute(request, SimpleNamespace(id=f"u{i}"), None,
                                        "rag_search", {}) for i in range(4)))
    assert seen == {f"u{i}": f"private-u{i}" for i in range(4)}
    assert settings.gemini_api_key == "owner-only"


@pytest.mark.asyncio
async def test_hosted_keyless_user_never_uses_environment_key(monkeypatch):
    monkeypatch.setattr("app.services.user_inference.effective_gemini_key",
                        AsyncMock(return_value=None))
    settings = Settings(_env_file=None, environment="beta", gemini_api_key="owner-only")
    scoped = await user_runtime_settings(None, "visitor", settings)
    assert scoped.gemini_api_key == "" and settings.gemini_api_key == "owner-only"
    pool = UserInferencePool(settings=settings, registry=None, factory=AsyncMock(),
                             environment_orchestrator=SimpleNamespace())
    with pytest.raises(ToolError) as caught:
        await pool.get(None, "visitor")
    assert caught.value.code == "model_not_configured"


@pytest.mark.asyncio
async def test_api_settings_use_current_user_key_without_mutating_global(monkeypatch):
    monkeypatch.setattr("app.services.user_inference.effective_gemini_key",
                        AsyncMock(return_value=("visitor-credential", "visitor-key", False)))
    settings = Settings(_env_file=None, gemini_api_key="owner-only")
    scoped = await user_runtime_settings(None, "visitor", settings)
    assert scoped.gemini_api_key == "visitor-key"
    assert settings.gemini_api_key == "owner-only"


@pytest.mark.asyncio
async def test_pool_isolates_user_credentials_and_invalidates_only_owner(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'isolation.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(
        _env_file=None,
        app_secret="user-inference-isolation-secret-long-enough",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'isolation.db'}",
        gemini_api_key="environment-key",
        gemini_fallback_model="gemini-3.5-flash-lite",
    )
    created = []

    async def make(runtime, _registry):
        instance = SimpleNamespace(settings=runtime, close=AsyncMock())
        created.append(instance)
        return instance

    environment = SimpleNamespace(settings=settings, close=AsyncMock())
    pool = UserInferencePool(
        settings=settings,
        registry=object(),
        factory=make,
        environment_orchestrator=environment,
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            first = User(email="first@example.test", display_name="First", role="editor")
            second = User(email="second@example.test", display_name="Second", role="editor")
            db.add_all([first, second])
            await db.flush()
            for user, key, fingerprint in (
                (first, "first-private-key", "1" * 20),
                (second, "second-private-key", "2" * 20),
            ):
                db.add(
                    ProviderCredential(
                        user_id=user.id,
                        provider="gemini",
                        display_name=user.display_name,
                        fingerprint=fingerprint,
                        encrypted_secret=encrypt_provider_secret(key, settings),
                        is_active=True,
                    )
                )
            await db.commit()

            first_runtime = await pool.get(db, first.id)
            second_runtime = await pool.get(db, second.id)
            assert first_runtime is not second_runtime
            assert first_runtime.settings.gemini_api_key == "first-private-key"
            assert second_runtime.settings.gemini_api_key == "second-private-key"
            assert settings.gemini_api_key == "environment-key"
            assert first_runtime.settings.gemini_fallback_model != settings.gemini_chat_model

            await pool.invalidate(first.id)
            assert first_runtime.close.await_count == 1
            assert second_runtime.close.await_count == 0
            assert await pool.get(db, second.id) is second_runtime
    finally:
        await pool.close()
        await engine.dispose()


def test_runtime_settings_never_mutates_global_settings():
    settings = Settings(
        _env_file=None,
        gemini_api_key="original",
        gemini_chat_model="gemini-3.5-flash-lite",
        gemini_fallback_model="gemini-3.5-flash-lite",
    )
    scoped = runtime_settings(settings, "user-key")
    assert scoped.gemini_api_key == "user-key"
    assert scoped.gemini_fallback_model == "gemini-3.6-flash"
    assert settings.gemini_api_key == "original"
    assert settings.gemini_fallback_model == "gemini-3.5-flash-lite"


@pytest.mark.asyncio
async def test_key_activation_retains_in_flight_runtime_until_request_finishes(monkeypatch):
    current = ["first-id", "first-key"]

    async def effective(_db, _user_id, _settings):
        return current[0], current[1], False

    monkeypatch.setattr("app.services.user_inference.effective_gemini_key", effective)
    gate = RequestPinningGate()
    settings = Settings(_env_file=None, gemini_api_key="environment-key")

    async def make(runtime, _registry):
        return SimpleNamespace(settings=runtime, close=AsyncMock())

    pool = UserInferencePool(
        settings=settings,
        registry=object(),
        factory=make,
        environment_orchestrator=SimpleNamespace(close=AsyncMock()),
        retire=gate.retire,
    )
    try:
        async with gate.request("owner"):
            old = await pool.get(None, "owner")
            current[:] = ["second-id", "second-key"]
            await pool.invalidate("owner")
            old.close.assert_not_awaited()
            new = await pool.get(None, "owner")
            assert new.settings.gemini_api_key == "second-key"
            old.close.assert_not_awaited()
        old.close.assert_awaited_once()
        new.close.assert_not_awaited()
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_pool_can_switch_once_to_distinct_opted_in_alternate(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'alternate.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(
        _env_file=None,
        app_secret="user-inference-alternate-secret-long-enough",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'alternate.db'}",
        data_dir=tmp_path,
        gemini_api_key="environment-key",
    )

    async def make(runtime, _registry):
        return SimpleNamespace(settings=runtime, close=AsyncMock())

    pool = UserInferencePool(
        settings=settings,
        registry=object(),
        factory=make,
        environment_orchestrator=SimpleNamespace(close=AsyncMock()),
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            user = User(email="alternate@example.test", display_name="Alt", role="editor")
            db.add(user)
            await db.flush()
            db.add_all(
                [
                    ProviderCredential(
                        user_id=user.id,
                        provider="gemini",
                        display_name="Primary",
                        fingerprint="a" * 20,
                        encrypted_secret=encrypt_provider_secret("primary-key", settings),
                        is_active=True,
                        failover_enabled=True,
                        status="ready",
                    ),
                    ProviderCredential(
                        user_id=user.id,
                        provider="gemini",
                        display_name="Alternate",
                        fingerprint="b" * 20,
                        encrypted_secret=encrypt_provider_secret("alternate-key", settings),
                        is_active=False,
                        failover_enabled=True,
                        status="ready",
                    ),
                ]
            )
            await db.commit()

            primary = await pool.get(db, user.id)
            alternate = await pool.get_alternate(db, user.id)

            assert primary.settings.gemini_api_key == "primary-key"
            assert primary.model_fallback_enabled is True
            assert alternate is not None
            assert alternate.settings.gemini_api_key == "alternate-key"
            assert alternate.model_fallback_enabled is True
            assert primary.close.await_count == 1
    finally:
        await pool.close()
        await engine.dispose()
