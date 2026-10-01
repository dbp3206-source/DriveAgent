from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import provider_credentials
from app.core.config import Settings
from app.core.security import decrypt_json
from app.db.models import Base, ProviderCredential, User
from app.services.provider_credentials import active_gemini_key, list_gemini_credentials


def _request(rotate=None):
    return SimpleNamespace(
        headers={"x-requested-with": "XMLHttpRequest"},
        app=SimpleNamespace(state=SimpleNamespace(rotate_gemini_key=rotate)),
    )


@pytest.mark.asyncio
async def test_provider_key_is_encrypted_redacted_and_hot_activates(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'keys.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(
        _env_file=None,
        app_secret="provider-key-test-secret-that-is-long-enough",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'keys.db'}",
    )
    rotate = AsyncMock()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            user = User(email="owner@example.test", display_name="Owner", role="owner")
            db.add(user)
            await db.commit()
            await db.refresh(user)
            payload = provider_credentials.CredentialCreate(
                display_name="Key chính",
                project_alias="free-project-a",
                api_key="AIza-test-secret-that-must-never-be-returned-123456",
            )
            with (
                patch.object(provider_credentials, "_probe_key", new=AsyncMock()) as probe,
                patch.object(provider_credentials, "get_settings", return_value=settings),
            ):
                created = await provider_credentials.create_credential(
                    payload, _request(rotate), db, user
                )
                assert created.fingerprint and not created.is_active
                assert "secret" not in created.model_dump_json()
                listed = await provider_credentials.list_credentials(db, user)
                assert [item.id for item in listed] == [created.id]
                validated = await provider_credentials.validate_credential(
                    created.id, _request(rotate), db, user
                )
                assert validated.status == "ready"
                row = await db.get(ProviderCredential, created.id)
                assert row is not None
                assert payload.api_key not in row.encrypted_secret
                assert decrypt_json(row.encrypted_secret, settings)["api_key"] == payload.api_key
                activated = await provider_credentials.activate_credential(
                    created.id, _request(rotate), db, user
                )
                assert activated.is_active
                # Create and explicit Validate probe. Activating an already
                # validated, immutable stored key must not wait on Google again.
                assert probe.await_count == 2
                rotate.assert_awaited_once_with(payload.api_key)
                stored_rows = await list_gemini_credentials(db, user.id)
                assert stored_rows[0].is_active
                assert await active_gemini_key(db, user.id, settings) == (
                    created.id,
                    payload.api_key,
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_active_key_cannot_be_deleted(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'delete.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            user = User(email="owner@example.test", display_name="Owner", role="owner")
            db.add(user)
            await db.flush()
            row = ProviderCredential(
                user_id=user.id,
                provider="gemini",
                display_name="Active",
                fingerprint="a" * 20,
                encrypted_secret="ciphertext",
                is_active=True,
            )
            db.add(row)
            await db.commit()
            with pytest.raises(Exception) as caught:
                await provider_credentials.delete_credential(row.id, _request(), db, user)
            assert getattr(caught.value, "status_code", None) == 409
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_probe_key_rejects_invalid_api_key(monkeypatch):
    from fastapi import HTTPException
    from google.genai.errors import ClientError

    class FakeModels:
        def get(self, model):
            raise ClientError(
                400, {"error": {"message": "API key not valid. Please pass a valid API key."}}
            )

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()
            self.aio = SimpleNamespace(aclose=AsyncMock())

        def close(self):
            pass

    monkeypatch.setattr("google.genai.Client", FakeClient)
    with pytest.raises(HTTPException) as exc:
        await provider_credentials._probe_key("bad-key")
    assert exc.value.status_code == 400
    assert "từ chối API key" in exc.value.detail


@pytest.mark.asyncio
async def test_probe_key_accepts_valid_key_when_primary_model_is_overloaded(monkeypatch):
    from google.genai.errors import ServerError

    called_models = []

    class FakeModels:
        def get(self, model):
            called_models.append(model)
            if model == "gemini-3.5-flash-lite":
                raise ServerError(503, {"error": {"message": "The model is overloaded."}})
            return SimpleNamespace(display_name=f"Model {model}")

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()
            self.aio = SimpleNamespace(aclose=AsyncMock())

        def close(self):
            pass

    monkeypatch.setattr("google.genai.Client", FakeClient)
    await provider_credentials._probe_key("valid-key-during-outage")
    assert len(called_models) >= 2
    assert "gemini-3.5-flash-lite" in called_models


@pytest.mark.asyncio
async def test_probe_key_reports_server_overload_honestly_when_all_models_503(monkeypatch):
    from fastapi import HTTPException
    from google.genai.errors import ServerError

    class FakeModels:
        def get(self, model):
            raise ServerError(503, {"error": {"message": "All models overloaded."}})

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()
            self.aio = SimpleNamespace(aclose=AsyncMock())

        def close(self):
            pass

    monkeypatch.setattr("google.genai.Client", FakeClient)
    with pytest.raises(HTTPException) as exc:
        await provider_credentials._probe_key("valid-key-all-overloaded")
    assert exc.value.status_code == 503
    assert "quá tải" in exc.value.detail
    assert "không bị từ chối" in exc.value.detail


@pytest.mark.asyncio
async def test_probe_key_accepts_valid_key_when_primary_model_returns_404(monkeypatch):
    from google.genai.errors import ClientError

    called_models = []

    class FakeModels:
        def get(self, model):
            called_models.append(model)
            if model == "gemini-3.5-flash-lite":
                raise ClientError(
                    404, {"error": {"message": "models/gemini-3.5-flash-lite is not found"}}
                )
            return SimpleNamespace(display_name=f"Model {model}")

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()
            self.aio = SimpleNamespace(aclose=AsyncMock())

        def close(self):
            pass

    monkeypatch.setattr("google.genai.Client", FakeClient)
    await provider_credentials._probe_key("valid-key-with-404-model")
    assert len(called_models) >= 2
    assert "gemini-3.5-flash-lite" in called_models
