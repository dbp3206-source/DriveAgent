from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.operations import OperationStore
from app.tools.contracts import ToolError


def test_approval_bound_to_user_and_exact_spec(tmp_path):
    store = OperationStore(tmp_path / "operations.db")
    row = store.prepare("a", "request", "docs_create", {"title": "Hello"})
    assert store.prepare("a", "request", "docs_create", {"title": "Hello"})["id"] == row["id"]
    for user, digest in [("b", row["digest"]), ("a", "wrong")]:
        with pytest.raises(ToolError):
            store.claim(user, row["id"], digest)
    with pytest.raises(ToolError):
        store.prepare("a", "request", "docs_create", {"title": "Changed"})
    assert store.get("a", row["id"])["state"] == "pending"


def test_only_one_claim_and_restart_does_not_retry(tmp_path):
    path = tmp_path / "operations.db"
    store = OperationStore(path)
    row = store.prepare("a", "request", "docs_create", {})

    def claim(_):
        try:
            store.claim("a", row["id"], row["digest"])
            return True
        except ToolError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(claim, range(8))) == 1
    store.checkpoint("a", row["id"], "doc-id")
    reopened = OperationStore(path)
    with pytest.raises(ToolError):
        reopened.claim("a", row["id"], row["digest"])
    reopened.uncertain("a", row["id"], "google_connection_error")
    assert reopened.get("a", row["id"])["resource_id"] == "doc-id"


def test_success_is_durable_and_cannot_be_overwritten(tmp_path):
    store = OperationStore(tmp_path / "operations.db")
    row = store.prepare("a", "request", "docs_create", {})
    store.claim("a", row["id"], row["digest"])
    store.finish("a", row["id"], {"verified": True})
    assert store.get("a", row["id"])["state"] == "succeeded"
    with pytest.raises(ToolError):
        store.uncertain("a", row["id"], "late-error")
