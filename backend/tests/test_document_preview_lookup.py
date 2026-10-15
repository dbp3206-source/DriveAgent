from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from starlette.middleware.sessions import SessionMiddleware

from app.api import documents
from app.services.operations import OperationStore
from app.services.relational_operations import RelationalOperationStore


@pytest.fixture(params=["native", "relational"])
def store(request, tmp_path):
    if request.param == "native":
        yield OperationStore(tmp_path / "operations.db")
    else:
        engine = create_engine(f"sqlite:///{tmp_path / 'relational.db'}")
        RelationalOperationStore.create_schema(engine)
        yield RelationalOperationStore(engine)
        engine.dispose()


def test_lookup_uses_owner_and_request_key_without_mutation(store):
    row = store.prepare("owner-a", "same-request-key", "docs_create", {
        "document": {"title": "Tên người dùng chọn", "blocks": [{"text": "private body"}]},
    })
    assert store.get_by_request_key("owner-a", "same-request-key") == row
    assert store.get_by_request_key("owner-b", "same-request-key") is None
    assert store.get_by_request_key("owner-a", "absent-key") is None
    assert store.get_by_request_key("owner-a", "' OR 1=1 --") is None
    store.claim("owner-a", row["id"], row["digest"])
    store.uncertain("owner-a", row["id"], "offline")
    assert store.get_by_request_key("owner-a", "same-request-key")["state"] == "uncertain"
    assert store.get("owner-a", row["id"])["digest"] == row["digest"]


@pytest.mark.asyncio
async def test_api_returns_only_locked_doc_metadata_and_no_other_owner_or_body(store, monkeypatch):
    monkeypatch.setattr(documents, "operation_store_for", lambda _: store)
    monkeypatch.setattr(documents, "get_settings", lambda: None)
    row = store.prepare("owner-a", "named-request-key", "docs_create", {
        "document": {"title": "Tên đã duyệt", "blocks": [{"text": "private body"}]},
    })
    result = await documents.prepared_preview("named-request-key", SimpleNamespace(id="owner-a"))
    assert result == {"data": {
        "operation_id": row["id"], "digest": row["digest"], "state": "pending",
        "title": "Tên đã duyệt",
    }}
    assert "private body" not in str(result)
    other_owner = await documents.prepared_preview(
        "named-request-key", SimpleNamespace(id="owner-b"),
    )
    assert other_owner == {"data": None}
    store.prepare("owner-a", "other-request-key", "gmail_draft_create", {"subject": "Private"})
    other_kind = await documents.prepared_preview(
        "other-request-key", SimpleNamespace(id="owner-a"),
    )
    assert other_kind == {"data": None}


def test_preview_route_retains_auth_dependency():
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="isolated-test-only-not-a-credential")
    app.include_router(documents.router)
    with TestClient(app) as client:
        result = client.get("/api/documents/previews/named-request-key")
    assert result.status_code == 401


def test_authenticated_lookup_validates_key_and_keeps_owner_scope(store, monkeypatch):
    from app.api.dependencies import get_current_user

    monkeypatch.setattr(documents, "operation_store_for", lambda _: store)
    monkeypatch.setattr(documents, "get_settings", lambda: None)
    own = store.prepare("alice", "shared-preview-key", "docs_create", {
        "document": {"title": "Alice", "blocks": [{"text": "Not returned"}]},
    })
    store.prepare("bob", "shared-preview-key", "docs_create", {
        "document": {"title": "Bob"},
    })
    app = FastAPI()
    app.include_router(documents.router)
    # Isolate route serialization from sign-in; unauthenticated access is tested above.
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="alice")
    with TestClient(app) as client:
        result = client.get("/api/documents/previews/shared-preview-key")
        assert result.status_code == 200
        assert result.json()["data"]["operation_id"] == own["id"]
        assert result.json()["data"]["title"] == "Alice"
        assert "Not returned" not in result.text
        assert client.get("/api/documents/previews/missing-preview-key").json() == {"data": None}
        assert client.get("/api/documents/previews/a").status_code == 422
