from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from requests.exceptions import ConnectionError as GoogleConnectionError
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth
from app.auth.google_oauth import build_flow
from app.core.config import Settings, get_settings
from app.db.session import get_db


def test_callback_restores_pkce_and_hides_provider_secrets(monkeypatch, caplog):
    settings = Settings(_env_file=None, app_secret="test-only-secret-that-is-long-enough")
    seen = {}

    def factory(*args, **kwargs):
        flow = SimpleNamespace(code_verifier=None)

        def authorize(**options):
            flow.code_verifier = "test-verifier-from-login"
            seen["state"] = options["state"]
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
        response = client.get(
            "/api/auth/google/callback", params={"state": seen["state"], "code": "test-code"}
        )
        assert response.status_code == 503
        assert seen["verifier"] == "test-verifier-from-login"
        assert seen["timeout"] == 20
        assert "private-token" not in response.text + caplog.text
        replay = client.get("/api/auth/google/callback", params={"state": seen["state"]})
        assert replay.status_code == 400


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
    assert "https://www.googleapis.com/auth/drive.file" not in seen["scopes"]
    build_flow(Settings(_env_file=None), workspace=True)
    assert "https://www.googleapis.com/auth/drive.file" in seen["scopes"]
    assert "https://www.googleapis.com/auth/drive" not in seen["scopes"]


def test_workspace_oauth_requires_login_and_rejects_arbitrary_capability():
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(auth.router)
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    with TestClient(app) as client:
        assert client.get("/api/auth/google?capability=workspace").status_code == 401
        assert client.get("/api/auth/google?capability=admin").status_code == 422
