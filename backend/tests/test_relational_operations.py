from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.services.relational_operations import (
    RelationalOperationStore,
    operations,
)
from app.tools.contracts import ToolError


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'portable-operations.db'}")
    RelationalOperationStore.create_schema(engine)
    yield RelationalOperationStore(engine)
    engine.dispose()


def test_owner_idempotency_redaction_and_reconciliation(store):
    row = store.prepare(
        "alice",
        "request-one",
        "docs_create",
        {"title": "Private", "content": "Do not expose"},
    )
    assert store.prepare(
        "alice", "request-one", "docs_create", {"title": "Private", "content": "Do not expose"}
    )["id"] == row["id"]
    with pytest.raises(ToolError) as conflict:
        store.prepare("alice", "request-one", "docs_create", {"title": "Changed"})
    assert conflict.value.code == "idempotency_conflict"
    with pytest.raises(ToolError) as hidden:
        store.get("bob", row["id"])
    assert hidden.value.code == "operation_not_found"

    claimed = store.claim("alice", row["id"], row["digest"])
    assert claimed["state"] == "pending"
    store.checkpoint("alice", row["id"], "doc-id")
    store.uncertain("alice", row["id"], "verification_failed")
    status = store.list_status("alice")
    assert status["attention_count"] == 1
    assert status["items"][0]["reconcilable"] is True
    assert "Private" not in str(status)
    assert "Do not expose" not in str(status)
    store.finish_reconciliation("alice", row["id"], {"verified": True})
    assert store.get("alice", row["id"])["state"] == "succeeded"


def test_parallel_claim_allows_one_external_attempt(store):
    row = store.prepare("alice", "request-two", "gmail_draft_create", {"subject": "Hello"})

    def claim(_):
        try:
            store.claim("alice", row["id"], row["digest"])
            return "claimed"
        except ToolError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(claim, range(8)))
    assert results.count("claimed") == 1
    assert results.count("operation_already_claimed") == 7
    store.fail("alice", row["id"], "provider_rejected_before_write")
    with pytest.raises(ToolError):
        store.claim("alice", row["id"], row["digest"])


def test_relational_operation_schema_is_postgres_portable():
    ddl = str(CreateTable(operations).compile(dialect=postgresql.dialect()))
    assert "PRAGMA" not in ddl
    assert "user_id" in ddl
    assert "resource_id" in ddl


def test_reopen_preserves_ambiguous_write_checkpoint(tmp_path):
    url = f"sqlite:///{tmp_path / 'persistent-operations.db'}"
    engine = create_engine(url)
    RelationalOperationStore.create_schema(engine)
    row = RelationalOperationStore(engine).prepare(
        "alice", "request-three", "sheets_create", {"title": "Report"}
    )
    first = RelationalOperationStore(engine)
    first.claim("alice", row["id"], row["digest"])
    first.checkpoint("alice", row["id"], "sheet-id")
    first.uncertain("alice", row["id"], "readback_timeout")
    engine.dispose()

    reopened_engine = create_engine(url)
    try:
        reopened = RelationalOperationStore(reopened_engine)
        restored = reopened.get("alice", row["id"])
        assert restored["state"] == "uncertain"
        assert restored["resource_id"] == "sheet-id"
        with pytest.raises(ToolError):
            reopened.claim("alice", row["id"], row["digest"])
    finally:
        reopened_engine.dispose()
