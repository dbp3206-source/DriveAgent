"""Actual retention HTTP/auth boundaries over strictly isolated synthetic stores."""

import base64
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
import test_retention_coordinator as coordinator_tests
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from itsdangerous import TimestampSigner
from sqlalchemy import func, select, update
from starlette.middleware.sessions import SessionMiddleware

from app.api import retention
from app.auth.sessions import establish_session
from app.core.config import get_settings
from app.db.models import CleanupJob, GraphCheckpoint, LongTermMemory, User
from app.db.session import get_db
from app.services.owner_admission import OwnerAdmissionMiddleware
from app.services.protocols import KnowledgeBridge, token_signer
from app.tools.contracts import ToolAccessDeniedError

runtime = coordinator_tests.runtime
BODY = coordinator_tests.BODY

PUBLIC_ORIGIN = "https://veridra.example.invalid"
SESSION_SECRET = "synthetic-http-session-signing-secret-not-for-production"


def signed_cookie(payload):
    encoded = base64.b64encode(json.dumps(payload).encode())
    return TimestampSigner(SESSION_SECRET).sign(encoded).decode()


@pytest.fixture
async def api(runtime, monkeypatch):
    """No app.main, dependency-user bypass, provider client, or personal DB path."""
    data = runtime
    assert data.settings.data_dir.resolve() == data.tmp_path.resolve()
    assert data.settings.resolved_qdrant_path.is_relative_to(data.tmp_path)
    sessions, emails = {}, []
    async with data.factory() as db:
        for label, identity in (("owner", data.owner), ("other", data.other)):
            user = await db.get(User, identity)
            session = {}
            establish_session(session, user)
            sessions[label] = session
            emails.append(user.email)
        await db.commit()
    settings = data.settings.model_copy(update={
        "environment": "production", "public_base_url": PUBLIC_ORIGIN,
        "frontend_origin": PUBLIC_ORIGIN, "beta_invited_emails": emails,
        "beta_owner_email": emails[0], "app_secret": SESSION_SECRET,
    })
    app = FastAPI()
    app.state.retention_coordinator = data.coordinator
    app.state.retention_gate = data.gate
    app.include_router(retention.router)
    app.add_middleware(OwnerAdmissionMiddleware)
    app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, https_only=True)

    async def database():
        async with data.factory() as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_settings] = lambda: settings
    # service() also calls this function directly, not through Depends.
    monkeypatch.setattr(retention, "get_settings", lambda: settings)

    async def request(method, path, *, actor="owner", cookie=None, headers=None, **kwargs):
        outgoing = dict(headers or {})
        if actor is not None:
            outgoing["Cookie"] = "session=" + (cookie or signed_cookie(sessions[actor]))
        # A fresh client per request avoids implicit cookie carry-over in tests
        # that deliberately omit authentication or swap to another owner.
        async with AsyncClient(transport=ASGITransport(app=app), base_url=PUBLIC_ORIGIN) as client:
            return await client.request(method, path, headers=outgoing, **kwargs)

    yield SimpleNamespace(
        request=request, data=data, app=app, sessions=sessions, settings=settings,
    )


async def assert_no_cleanup(data):
    async with data.factory() as db:
        assert await db.scalar(select(func.count()).select_from(CleanupJob)) == 0
        assert (await db.get(LongTermMemory, data.old)).content == BODY


def assert_private(response):
    assert "no-store" in response.headers.get("Cache-Control", "")


async def preview(api):
    response = await api.request("GET", "/api/retention/preview")
    assert response.status_code == 200, response.text
    assert_private(response)
    return response.json()


async def confirm(api, token, *, actor="owner", headers=None, payload=None):
    return await api.request(
        "POST", "/api/retention/confirm", actor=actor,
        headers={"Origin": PUBLIC_ORIGIN} if headers is None else headers,
        json=payload if payload is not None else {"token": token, "confirmed": True},
    )


async def test_preview_and_latest_are_readonly_and_hide_content(api):
    first = await preview(api)
    second = await preview(api)
    assert first["selected_count"] == second["selected_count"] == 1
    assert first["reset_context_count"] == second["reset_context_count"] == 1
    assert first["retention_days"] == 30 and first["token"]
    for forbidden in (BODY, "FRESH_CANARY", "FOREIGN_CANARY", "FRESH_CHAT"):
        assert forbidden not in json.dumps(first)
    latest = await api.request("GET", "/api/retention/status")
    assert latest.status_code == 200 and latest.json() == {"job": None}
    assert_private(latest)
    await assert_no_cleanup(api.data)


@pytest.mark.parametrize("case", ["absent", "unsigned", "tampered", "stale", "missing_user"])
async def test_real_signed_session_and_current_auth_version_are_required(api, case):
    payload = dict(api.sessions["owner"])
    actor, cookie = "owner", None
    if case == "absent":
        actor = None
    elif case == "unsigned":
        cookie = base64.b64encode(json.dumps(payload).encode()).decode()
    elif case == "tampered":
        cookie = signed_cookie(payload) + "tampered"
    elif case == "stale":
        cookie = signed_cookie({**payload, "auth_version": "synthetic-stale-version"})
    else:
        cookie = signed_cookie({**payload, "user_id": str(uuid4())})
    response = await api.request("GET", "/api/retention/preview", actor=actor, cookie=cookie)
    assert response.status_code == 401
    assert_private(response)
    await assert_no_cleanup(api.data)


@pytest.mark.parametrize("headers", [
    {},
    {"Origin": "https://evil.invalid"},
    {"Origin": "null"},
    {"Origin": PUBLIC_ORIGIN + ".evil.invalid"},
    {"Origin": PUBLIC_ORIGIN + "/fake-path"},
    {"Origin": PUBLIC_ORIGIN.replace("https://", "http://")},
    {"Origin": "https://evil.invalid", "Referer": PUBLIC_ORIGIN + "/#/local"},
    {"X-Requested-With": "XMLHttpRequest", "Sec-Fetch-Site": "same-origin"},
])
async def test_public_mutation_needs_real_trusted_browser_origin(api, headers):
    data = await preview(api)
    response = await confirm(api, data["token"], headers=headers)
    assert response.status_code == 403
    assert_private(response)
    assert data["token"] not in response.text
    await assert_no_cleanup(api.data)


@pytest.mark.parametrize("confirmation", [None, False, 0, 1, "true", "false", [], {}])
async def test_confirmation_is_required_true_boolean_not_coerced(api, confirmation):
    data = await preview(api)
    payload = {"token": data["token"]}
    if confirmation is not None:
        payload["confirmed"] = confirmation
    response = await confirm(api, data["token"], payload=payload)
    assert response.status_code == 422
    assert_private(response)
    await assert_no_cleanup(api.data)


async def test_browser_cannot_expand_scope_or_select_another_owner_in_body(api):
    data = await preview(api)
    response = await confirm(api, data["token"], payload={
        "token": data["token"], "confirmed": True, "owner_id": api.data.other,
        "source": "api", "delete_all": True,
    })
    assert response.status_code == 422
    assert_private(response)
    await assert_no_cleanup(api.data)


@pytest.mark.parametrize("token", ["x", "synthetic-not-a-signed-retention-approval"])
async def test_malformed_token_never_enqueues_or_deletes(api, token):
    response = await confirm(api, token)
    assert response.status_code == (422 if len(token) < 10 else 409)
    assert_private(response)
    await assert_no_cleanup(api.data)


async def test_another_real_authenticated_owner_cannot_use_or_read_approval(api):
    data = await preview(api)
    foreign = await confirm(api, data["token"], actor="other")
    assert foreign.status_code == 409
    assert_private(foreign)
    await assert_no_cleanup(api.data)
    own = await confirm(api, data["token"])
    assert own.status_code == 202
    identity = own.json()["id"]
    foreign_status = await api.request("GET", f"/api/retention/jobs/{identity}", actor="other")
    assert foreign_status.status_code == 404
    assert_private(foreign_status)
    assert identity not in foreign_status.text
    latest = await api.request("GET", "/api/retention/status", actor="other")
    assert latest.json() == {"job": None}
    for operation in ("cancel", "retry"):
        response = await api.request(
            "POST", f"/api/retention/jobs/{identity}/{operation}", actor="other",
            headers={"Origin": PUBLIC_ORIGIN},
        )
        assert response.status_code == 409
        assert_private(response)
    async with api.data.factory() as db:
        assert (await db.get(CleanupJob, identity)).status == "queued"
        assert await db.get(LongTermMemory, api.data.old) is not None


async def test_confirmation_queues_once_but_does_not_run_purge_synchronously(api):
    data = await preview(api)
    first = await confirm(api, data["token"])
    second = await confirm(api, data["token"])
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json() == {"id": first.json()["id"], "status": "queued"}
    assert_private(first)
    identity = first.json()["id"]
    status = await api.request("GET", f"/api/retention/jobs/{identity}")
    assert status.status_code == 200
    assert_private(status)
    job = status.json()
    assert job["status"] == "queued" and job["attempts"] == 0 and not job["sql_completed"]
    assert "token" not in job and "plan" not in job and "owner_id" not in job
    latest = await api.request("GET", "/api/retention/status")
    assert latest.json() == {"job": job}
    assert_private(latest)
    async with api.data.factory() as db:
        assert await db.scalar(select(func.count()).select_from(CleanupJob)) == 1
        assert (await db.get(LongTermMemory, api.data.old)).content == BODY
        assert await db.scalar(select(func.count()).select_from(GraphCheckpoint).where(
            GraphCheckpoint.user_id == api.data.owner)) == 1


async def test_get_never_consumes_confirmation_and_cancel_preserves_content(api):
    data = await preview(api)
    wrong_method = await api.request("GET", "/api/retention/confirm", params={
        "token": data["token"], "confirmed": "true",
    })
    assert wrong_method.status_code == 405
    assert_private(wrong_method)
    await assert_no_cleanup(api.data)
    queued = await confirm(api, data["token"])
    identity = queued.json()["id"]
    rejected = await api.request("POST", f"/api/retention/jobs/{identity}/cancel")
    assert rejected.status_code == 403
    assert_private(rejected)
    cancelled = await api.request(
        "POST", f"/api/retention/jobs/{identity}/cancel", headers={"Origin": PUBLIC_ORIGIN},
    )
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert_private(cancelled)
    assert not await api.data.coordinator.execute_one()
    async with api.data.factory() as db:
        assert await db.get(LongTermMemory, api.data.old) is not None


async def test_retry_requires_owner_origin_and_retryable_state_without_deleting(api):
    data = await preview(api)
    queued = await confirm(api, data["token"])
    identity = queued.json()["id"]
    path = f"/api/retention/jobs/{identity}/retry"
    state_conflict = await api.request("POST", path, headers={"Origin": PUBLIC_ORIGIN})
    assert state_conflict.status_code == 409
    async with api.data.factory() as db:
        await db.execute(update(CleanupJob).where(CleanupJob.id == identity).values(
            status="needs_attention", attempts=2, error_code="cleanup_store_unavailable",
        ))
        await db.commit()
    foreign_origin = await api.request("POST", path, headers={"Origin": "https://evil.invalid"})
    assert foreign_origin.status_code == 403
    accepted = await api.request("POST", path, headers={"Origin": PUBLIC_ORIGIN})
    assert accepted.status_code == 202 and accepted.json()["status"] == "queued"
    assert_private(accepted)
    async with api.data.factory() as db:
        job = await db.get(CleanupJob, identity)
        assert job.attempts == 0 and job.status == "queued" and job.sql_completed_at is None
        assert await db.get(LongTermMemory, api.data.old) is not None


async def test_read_protocol_token_or_model_instruction_is_not_human_consent(api):
    data = await preview(api)
    bearer = token_signer(api.settings).dumps({"sub": api.data.owner, "scope": "knowledge:read"})
    unauthenticated = await api.request(
        "POST", "/api/retention/confirm", actor=None,
        headers={"Origin": PUBLIC_ORIGIN, "Authorization": "Bearer " + bearer},
        json={"token": data["token"], "confirmed": True},
    )
    assert unauthenticated.status_code == 401
    assert_private(unauthenticated)
    bridge = KnowledgeBridge(api.settings, session_factory=api.data.factory)
    for tool in ("retention_confirm", "cleanup", "/api/retention/confirm"):
        with pytest.raises(ToolAccessDeniedError):
            await bridge.read(tool, {"token": data["token"], "confirmed": True}, api.data.owner)
    await assert_no_cleanup(api.data)


async def test_unavailable_coordinator_fails_closed_without_disclosing_token(api):
    data = await preview(api)
    api.app.state.retention_coordinator = None
    response = await confirm(api, data["token"])
    assert response.status_code == 503
    assert_private(response)
    assert data["token"] not in response.text
    await assert_no_cleanup(api.data)
