"""T07 API chain with real validation/registry/ledger and a fake Google boundary.

No OAuth, model, real Google write or live-user authentication is exercised here.
"""

import json
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import documents
from app.api.dependencies import get_current_user
from app.core.config import Settings
from app.db.models import Base, User
from app.db.session import get_db
from app.services.operations import OperationStore
from app.services.relational_operations import RelationalOperationStore
from app.tools import documents as document_tools
from app.tools.contracts import ToolError
from app.tools.documents import DRIVE_FILE_SCOPE, document_tool_definitions
from app.tools.registry import ToolRegistry


@pytest.mark.parametrize("ledger_kind", ["native", "relational-sqlite"])
async def test_changed_preview_requires_its_own_approval_and_never_replays_write(
    tmp_path, monkeypatch, ledger_kind,
):
    settings = Settings(
        _env_file=None,
        _env_prefix="VERIDRA_ISOLATED_APPROVAL_TEST_",
        environment="development",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}",
        frontend_origin="http://127.0.0.1:5173",
        gemini_api_key="",
        google_oauth_client_file=tmp_path / "not-configured.json",
    )
    assert not settings.gemini_is_configured and not settings.oauth_is_configured
    engine = create_async_engine(settings.resolved_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        users = [User(
            email=f"approval-{index}@example.invalid", display_name="Synthetic QA",
            role="owner", oauth_scopes_json=json.dumps([DRIVE_FILE_SCOPE]),
        ) for index in range(2)]
        db.add_all(users)
        await db.commit()

    ledger_engine = None
    if ledger_kind == "native":
        store = OperationStore(tmp_path / "operations.db")
    else:
        ledger_engine = create_engine(f"sqlite:///{tmp_path / 'operations-relational.db'}")
        RelationalOperationStore.create_schema(ledger_engine)
        store = RelationalOperationStore(ledger_engine)

    monkeypatch.setattr(documents, "get_settings", lambda: settings)
    monkeypatch.setattr(documents, "operation_store_for", lambda _: store)
    monkeypatch.setattr(document_tools, "operation_store", lambda _: store)
    monkeypatch.setattr(
        document_tools, "refresh_and_store_if_needed", AsyncMock(return_value=SimpleNamespace()),
    )
    fake_writes = []

    class FakeCreator:
        def __init__(self, _service):
            pass

        def create(self, document, checkpoint):
            fake_writes.append(document.model_dump(mode="json"))
            checkpoint("synthetic-doc-one")
            # Only a fake adapter result; not evidence of Google read-back.
            return {"document_id": "synthetic-doc-one", "verified": True}

    monkeypatch.setattr(document_tools, "build", lambda *a, **k: nullcontext(object()))
    monkeypatch.setattr(document_tools, "DocumentCreator", FakeCreator)
    app = FastAPI()
    app.include_router(documents.router)
    app.state.registry = ToolRegistry()
    for definition in document_tool_definitions():
        app.state.registry.register(definition)
    active_user = [users[0]]
    # Authentication is explicitly replaced; real schema, origin, RBAC, scope,
    # registry and ledger checks remain in the chain. T09 is not closed by this.
    app.dependency_overrides[get_current_user] = lambda: active_user[0]

    async def database():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db] = database

    @app.exception_handler(ToolError)
    async def tool_error(_request, error):
        return JSONResponse({"code": error.code}, status_code=400)

    preview_a = {
        "request_key": "synthetic-preview-a", "action": "create",
        "document": {"title": "Bản A", "blocks": [{"text": "Nội dung giả lập A"}]},
    }
    preview_b = deepcopy(preview_a)
    preview_b["request_key"] = "synthetic-preview-b"
    preview_b["document"] = {
        "title": "Bản B đã sửa", "blocks": [{"text": "Nội dung giả lập B"}],
    }
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://approval.test",
            headers={"Origin": settings.frontend_origin},
        ) as client:
            first = await client.post("/api/documents/prepare", json=preview_a)
            assert first.status_code == 200
            a = first.json()["data"]
            original_spec = store.get(users[0].id, a["operation_id"])["spec"]
            approval_a = {"operation_id": a["operation_id"], "approved_digest": a["digest"]}
            assert not fake_writes

            # Approval cannot carry a replacement body or destination.
            for extra in ({"document": preview_b["document"]}, {"document_id": "other-doc"}):
                denied = await client.post("/api/documents/approve", json={**approval_a, **extra})
                assert denied.status_code == 422
            foreign_origin = await client.post(
                "/api/documents/approve", json=approval_a,
                headers={"Origin": "https://foreign.example.invalid"},
            )
            assert foreign_origin.status_code == 403
            changed_same_key = {**preview_b, "request_key": preview_a["request_key"]}
            conflict = await client.post("/api/documents/prepare", json=changed_same_key)
            assert conflict.status_code == 400
            assert store.get(users[0].id, a["operation_id"])["spec"] == original_spec
            assert json.loads(store.get(users[0].id, a["operation_id"])["spec"])[
                "document"
            ]["title"] == "Bản A"

            second = await client.post("/api/documents/prepare", json=preview_b)
            assert second.status_code == 200
            b = second.json()["data"]
            assert a["operation_id"] != b["operation_id"] and a["digest"] != b["digest"]
            stale = await client.post("/api/documents/approve", json={
                "operation_id": b["operation_id"], "approved_digest": a["digest"],
            })
            assert stale.status_code == 400 and stale.json()["code"] == "approval_mismatch"
            approval_b = {"operation_id": b["operation_id"], "approved_digest": b["digest"]}
            active_user[0] = users[1]
            wrong_owner = await client.post("/api/documents/approve", json=approval_b)
            assert wrong_owner.status_code == 400
            assert wrong_owner.json()["code"] == "operation_not_found"
            assert not fake_writes

            active_user[0] = users[0]
            approved = await client.post("/api/documents/approve", json=approval_b)
            assert approved.status_code == 200
            assert len(fake_writes) == 1
            assert fake_writes[0]["title"] == "Bản B đã sửa"
            assert fake_writes[0]["blocks"][0]["text"] == "Nội dung giả lập B"
            repeated = await client.post("/api/documents/approve", json=approval_b)
            assert repeated.status_code == 400
            assert repeated.json()["code"] == "operation_already_claimed"
            status = await client.get(f"/api/documents/operations/{b['operation_id']}")
            assert status.status_code == 200 and status.json()["state"] == "succeeded"
            assert len(fake_writes) == 1
    finally:
        await engine.dispose()
        if ledger_engine is not None:
            ledger_engine.dispose()
