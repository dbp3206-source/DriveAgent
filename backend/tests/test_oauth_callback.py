import os
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from requests.exceptions import ConnectionError as GoogleConnectionError
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth
from app.api.dependencies import get_current_user
from app.auth.google_oauth import build_flow, configure_oauthlib
from app.core.config import Settings, get_settings
from app.db.session import get_db


def test_closed_beta_invites_fail_closed_and_normalize_email():
    local = Settings(_env_file=None, environment="development")
    assert local.beta_email_allowed("anyone@example.com")
    beta = Settings(
        _env_file=None,
        environment="production",
        beta_invited_emails=" Owner@Example.com, invited@example.com ",
    )
    assert beta.beta_email_allowed("owner@example.com")
    assert beta.beta_email_allowed(" INVITED@EXAMPLE.COM ")
    assert not beta.beta_email_allowed("outsider@example.com")
    assert not Settings(_env_file=None, environment="production").beta_email_allowed(
        "owner@example.com"
    )


@pytest.mark.asyncio
async def test_closed_beta_revokes_existing_session_when_invite_removed():
    class Db:
        async def get(self, model, user_id):
            assert user_id == "existing-user"
            return SimpleNamespace(email="former@example.com", role="editor", is_active=True)

    request = SimpleNamespace(session={"user_id": "existing-user"})
    settings = Settings(
        _env_file=None,
        environment="production",
        beta_invited_emails=["invited@example.com"],
    )
    with pytest.raises(HTTPException) as error:
        await get_current_user(request, Db(), settings)
    assert error.value.status_code == 403
    assert request.session == {}


def test_oauth_callback_rejects_uninvited_account_before_database_write(monkeypatch):
    settings = Settings(
        _env_file=None,
        environment="production",
        app_secret="test-only-secret-that-is-long-enough",
        beta_invited_emails=["invited@example.com"],
    )
    seen = {}

    def factory(*args, **kwargs):
        flow = SimpleNamespace(
            code_verifier="test-verifier", credentials=SimpleNamespace(token="test-token")
        )

        def authorize(**options):
            seen["state"] = options["state"]
            return "https://accounts.google.com/", options["state"]

        flow.authorization_url = authorize
        flow.fetch_token = lambda **options: None
        return flow

    async def profile(token):
        assert token == "test-token"
        return {"email": "outsider@example.com", "email_verified": True}

    class GuardDb:
        async def scalar(self, *args, **kwargs):
            raise AssertionError("Uninvited user must not reach database lookup")

        async def commit(self):
            raise AssertionError("Uninvited user must not be persisted")

    monkeypatch.setattr(auth, "build_flow", factory)
    monkeypatch.setattr(auth, "fetch_google_profile", profile)
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key=settings.app_secret)
    app.include_router(auth.router)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = lambda: GuardDb()
    with TestClient(app) as client:
        client.get("/api/auth/google", follow_redirects=False)
        response = client.get(
            "/api/auth/google/callback", params={"state": seen["state"], "code": "test-code"}
        )
        assert response.status_code == 403
        assert "chưa được mời" in response.text


def test_closed_beta_first_invited_user_cannot_claim_admin(monkeypatch):
    settings = Settings(
        _env_file=None,
        environment="production",
        app_secret="test-only-secret-that-is-long-enough",
        beta_invited_emails=["invited@example.com", "owner@example.com"],
        beta_owner_email="owner@example.com",
    )
    seen = {}
    profiles = iter(("invited@example.com", "owner@example.com"))

    def factory(*_args, **_kwargs):
        flow = SimpleNamespace(
            code_verifier="test-verifier",
            credentials=SimpleNamespace(token="test-token", granted_scopes=[], scopes=[]),
        )

        def authorize(**options):
            seen["state"] = options["state"]
            return "https://accounts.google.com/", options["state"]

        flow.authorization_url = authorize
        flow.fetch_token = lambda **_options: None
        return flow

    async def profile(_token):
        email = next(profiles)
        return {"email": email, "email_verified": True, "name": email}

    class Db:
        def __init__(self):
            self.users = []

        async def scalar(self, *_args, **_kwargs):
            return None

        def add(self, user):
            self.users.append(user)

        async def commit(self):
            for index, user in enumerate(self.users):
                user.id = f"user-{index}"

    db = Db()
    monkeypatch.setattr(auth, "build_flow", factory)
    monkeypatch.setattr(auth, "fetch_google_profile", profile)
    monkeypatch.setattr(auth, "credentials_to_dict", lambda _credentials: {})
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key=settings.app_secret)
    app.include_router(auth.router)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        for expected_role in ("editor", "super_admin"):
            client.get("/api/auth/google", follow_redirects=False)
            response = client.get(
                "/api/auth/google/callback",
                params={"state": seen["state"], "code": "test-code"},
                follow_redirects=False,
            )
            assert response.status_code == 307
            assert db.users[-1].role == expected_role


def test_oauth_provider_exception_does_not_expose_secret(monkeypatch, caplog):
    settings = Settings(_env_file=None, app_secret="test-only-secret-that-is-long-enough")
    seen = {}

    def factory(*_args, **_kwargs):
        flow = SimpleNamespace(code_verifier=None)

        def authorize(**options):
            seen["state"] = options["state"]
            return "https://accounts.google.com/", options["state"]

        def exchange(**_options):
            raise RuntimeError("private-auth-code-should-not-appear")

        flow.authorization_url = authorize
        flow.fetch_token = exchange
        return flow

    monkeypatch.setattr(auth, "build_flow", factory)
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key=settings.app_secret)
    app.include_router(auth.router)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = lambda: None
    with TestClient(app) as client:
        client.get("/api/auth/google", follow_redirects=False)
        response = client.get(
            "/api/auth/google/callback", params={"state": seen["state"], "code": "test-code"}
        )
    assert response.status_code == 400
    assert "private-auth-code" not in response.text + caplog.text


@pytest.mark.asyncio
async def test_non_owner_super_admin_session_is_rejected():
    class Db:
        async def get(self, _model, _user_id):
            return SimpleNamespace(
                email="invited@example.com", role="super_admin", is_active=True
            )

    request = SimpleNamespace(session={"user_id": "migrated-user"})
    settings = Settings(
        _env_file=None,
        environment="production",
        beta_invited_emails=["invited@example.com", "owner@example.com"],
        beta_owner_email="owner@example.com",
    )
    with pytest.raises(HTTPException) as error:
        await get_current_user(request, Db(), settings)
    assert error.value.status_code == 403
    assert request.session == {}


def test_callback_restores_pkce_and_hides_provider_secrets(monkeypatch, caplog):
    settings = Settings(_env_file=None, app_secret="test-only-secret-that-is-long-enough")
    seen = {}

    def factory(*args, **kwargs):
        flow = SimpleNamespace(code_verifier=None)

        def authorize(**options):
            flow.code_verifier = "test-verifier-from-login"
            seen["state"] = options["state"]
            seen["include_granted_scopes"] = options["include_granted_scopes"]
            return "https://accounts.google.com/", options["state"]

        def exchange(**options):
            seen["verifier"] = flow.code_verifier
            seen["timeout"] = options["timeout"]
            raise GoogleConnectionError("private-token-should-never-be-logged")

        flow.authorization_url = authorize
        flow.fetch_token = exchange
        return flow

    monkeypatch.setattr(auth, "build_flow", factory)
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key=settings.app_secret)
    app.include_router(auth.router)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = lambda: None
    with TestClient(app) as client:
        client.get("/api/auth/google", follow_redirects=False)
        assert seen["include_granted_scopes"] == "false"
        response = client.get(
            "/api/auth/google/callback", params={"state": seen["state"], "code": "test-code"}
        )
        assert response.status_code == 503
        assert seen["verifier"] == "test-verifier-from-login"
        assert seen["timeout"] == 20
        assert "private-token" not in response.text + caplog.text
        replay = client.get("/api/auth/google/callback", params={"state": seen["state"]})
        assert replay.status_code == 400
        # Direct navigation without any query params redirects to frontend
        direct = client.get("/api/auth/google/callback", follow_redirects=False)
        assert direct.status_code == 307
        assert direct.headers["location"] == f"{settings.frontend_origin}/"


def test_flow_normalizes_google_scope_aliases(monkeypatch):
    seen = {}

    def load(*args, **kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(Settings, "oauth_is_configured", property(lambda self: True))
    monkeypatch.setattr("app.auth.google_oauth.Flow.from_client_secrets_file", load)
    build_flow(Settings(_env_file=None))
    assert "https://www.googleapis.com/auth/userinfo.email" in seen["scopes"]
    assert "https://www.googleapis.com/auth/userinfo.profile" in seen["scopes"]
    assert "https://www.googleapis.com/auth/drive.readonly" in seen["scopes"]
    assert "https://www.googleapis.com/auth/gmail.send" not in seen["scopes"]
    base_scopes = list(seen["scopes"])
    build_flow(Settings(_env_file=None), workspace=True)
    assert "https://www.googleapis.com/auth/drive.file" in seen["scopes"]
    assert seen["scopes"].count("https://www.googleapis.com/auth/drive.file") == 1
    assert len(seen["scopes"]) == len(set(base_scopes) | {"https://www.googleapis.com/auth/drive.file"})
    assert "https://www.googleapis.com/auth/drive" not in seen["scopes"]
    build_flow(
        Settings(
            _env_file=None,
            google_drive_scopes=[
                "openid",
                "email",
                "profile",
                "https://www.googleapis.com/auth/gmail.readonly",
            ],
        ),
        gmail_compose=True,
    )
    assert "https://www.googleapis.com/auth/gmail.compose" in seen["scopes"]
    assert "https://www.googleapis.com/auth/gmail.send" not in seen["scopes"]
    build_flow(Settings(_env_file=None), workspace=True, gmail_compose=True)
    assert "https://www.googleapis.com/auth/drive.file" in seen["scopes"]
    assert "https://www.googleapis.com/auth/gmail.compose" in seen["scopes"]


def test_insecure_oauth_transport_is_scoped_to_loopback(monkeypatch):
    monkeypatch.setenv("OAUTHLIB_INSECURE_TRANSPORT", "1")
    monkeypatch.setenv("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
    local = Settings(
        _env_file=None,
        environment="development",
        public_base_url="http://localhost:8000",
        google_redirect_uri="http://localhost:8000/api/auth/google/callback",
    )
    configure_oauthlib(local)
    assert os.environ["OAUTHLIB_INSECURE_TRANSPORT"] == "1"

    production = Settings(
        _env_file=None,
        environment="production",
        public_base_url="https://driveagent.example",
        google_redirect_uri="https://driveagent.example/api/auth/google/callback",
    )
    configure_oauthlib(production)
    assert "OAUTHLIB_INSECURE_TRANSPORT" not in os.environ
    assert "OAUTHLIB_RELAX_TOKEN_SCOPE" not in os.environ


def test_workspace_oauth_requires_login_and_rejects_arbitrary_capability():
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(auth.router)
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    with TestClient(app) as client:
        assert client.get("/api/auth/google?capability=workspace").status_code == 401
        assert client.get("/api/auth/google?capability=gmail").status_code == 401
        assert client.get("/api/auth/google?capability=reconnect").status_code == 401
        assert client.get("/api/auth/google?capability=admin").status_code == 422


def test_google_login_normalizes_loopback_alias_before_setting_oauth_state():
    settings = Settings(
        _env_file=None,
        environment="development",
        public_base_url="http://localhost:8000",
        google_redirect_uri="http://localhost:8000/api/auth/google/callback",
    )
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(auth.router)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.get("/api/auth/google", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "http://localhost:8000/api/auth/google"
