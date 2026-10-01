from types import SimpleNamespace

import pytest
from fastapi import Response
from fastapi.testclient import TestClient

from app import main
from app.api.gmail_remote import _confirmation_page
from app.core.config import Settings


def _production_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="production",
        frontend_origin="https://veridra.example",
        public_base_url="https://veridra.example",
    )


def test_public_session_writes_require_exact_browser_origin(monkeypatch):
    monkeypatch.setattr(main, "settings", _production_settings())
    client = TestClient(main.app)
    assert client.post("/api/auth/logout").status_code == 403
    assert client.post(
        "/api/auth/logout", headers={"Origin": "https://veridra.example.evil.test"}
    ).status_code == 403
    assert client.post(
        "/api/auth/logout", headers={"X-Requested-With": "XMLHttpRequest"}
    ).status_code == 403
    assert client.post(
        "/api/auth/logout", headers={"Origin": "https://veridra.example"}
    ).status_code == 204
    # Non-authenticated writes are also stopped before any route handler.
    assert client.post("/api/chat", json={"message": "hello"}).status_code == 403
    assert client.post("/api/memory", json={"content": "secret"}).status_code == 403
    assert client.patch("/api/admin/users/other/role", json={"role": "owner"}).status_code == 403


def test_public_origin_gate_keeps_signed_remote_flow_separate(monkeypatch):
    monkeypatch.setattr(main, "settings", _production_settings())
    client = TestClient(main.app)
    assert client.post("/api/gmail/remote/action", json={"token": "short"}).status_code == 422
    assert client.post("/api/gmail/remote/webhook").status_code == 501
    # The confirmation form is browser-initiated even though its action token
    # is signed: a foreign site must not submit it using a victim's browser.
    assert client.post(
        "/api/gmail/remote/action/confirm", data={"token": "invalid-token"}
    ).status_code == 403
    # The token-bearing preview never leaks its complete URL in Referer.
    preview = _confirmation_page("signed-token", "Review", "Safe")
    assert preview.headers["Referrer-Policy"] == "origin"
    assert b'<meta name="referrer" content="origin">' in preview.body


@pytest.mark.asyncio
async def test_global_security_headers_preserve_stricter_route_headers():
    async def route_response(_request):
        return Response(
            headers={
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'none'; sandbox",
            }
        )

    request = SimpleNamespace(url=SimpleNamespace(path="/api/gmail/messages/attachment"))
    response = await main.security_headers_middleware(request, route_response)
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Content-Security-Policy"] == "default-src 'none'; sandbox"
