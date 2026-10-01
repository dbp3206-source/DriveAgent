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


def test_expired_preview_is_terminal_and_visible(tmp_path):
    store = OperationStore(tmp_path / "operations.db")
    row = store.prepare("a", "expired-request", "gmail_draft_create", {"subject": "Hello"})
    with store.connect() as db:
        db.execute("UPDATE operations SET created=0 WHERE id=?", (row["id"],))

    with pytest.raises(ToolError) as exc_info:
        store.claim("a", row["id"], row["digest"])

    assert exc_info.value.code == "approval_expired"
    assert store.get("a", row["id"])["state"] == "expired"


def test_status_ledger_is_user_scoped_redacted_and_marks_safe_reconciliation(tmp_path):
    store = OperationStore(tmp_path / "operations.db")
    row = store.prepare(
        "user-a",
        "secret-request",
        "sheets_create",
        {"title": "Private budget", "rows": [["Sensitive value"]]},
    )
    store.claim("user-a", row["id"], row["digest"])
    store.checkpoint("user-a", row["id"], "sheet-id")
    store.uncertain("user-a", row["id"], "verification_failed")
    store.prepare("user-b", "other", "docs_create", {"content": "Other tenant"})

    result = store.list_status("user-a")

    assert result["attention_count"] == 1
    assert result["pending_previews"] == 0
    assert len(result["items"]) == 1
    assert result["items"][0]["reconcilable"] is True
    assert set(result["items"][0]) == {
        "id", "capability", "state", "created", "resource_id", "error_code", "reconcilable"
    }
    serialized = str(result)
    assert "Private budget" not in serialized
    assert "Sensitive value" not in serialized
    assert "Other tenant" not in serialized

    store.acknowledge_uncertain("user-a", row["id"])
    reviewed = store.get("user-a", row["id"])
    assert reviewed["state"] == "reviewed"
    assert store.list_status("user-a")["attention_count"] == 0
    with pytest.raises(ToolError):
        store.acknowledge_uncertain("user-a", row["id"])


def test_status_expires_abandoned_preview_and_archive_hides_terminal_work(tmp_path):
    store = OperationStore(tmp_path / "operations.db")
    row = store.prepare("user-a", "old", "docs_create", {"title": "Old"})
    with store.connect() as db:
        db.execute("UPDATE operations SET created=0 WHERE id=?", (row["id"],))

    status = store.list_status("user-a")
    assert status["summary"]["expired"] == 1
    assert status["pending_previews"] == 0
    store.archive("user-a", row["id"])
    assert store.list_status("user-a")["items"] == []


def test_archive_rejects_active_operation(tmp_path):
    store = OperationStore(tmp_path / "operations.db")
    row = store.prepare("user-a", "active", "docs_create", {})
    store.claim("user-a", row["id"], row["digest"])
    with pytest.raises(ToolError, match="đang chạy"):
        store.archive("user-a", row["id"])
