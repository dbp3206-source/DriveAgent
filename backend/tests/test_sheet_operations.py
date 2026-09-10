from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from app.services.operations import OperationStore
from app.tools.contracts import ToolError
from app.tools.documents import DocumentApproval
from app.tools.sheets import SpreadsheetPrepare, sheets_execute, sheets_prepare


@pytest.mark.parametrize("failure", [False, True])
async def test_approved_sheet_has_one_attempt_and_durable_result(tmp_path, monkeypatch, failure):
    context = SimpleNamespace(
        user=SimpleNamespace(id="alice"),
        db=None,
        settings=SimpleNamespace(data_dir=tmp_path),
    )
    payload = SpreadsheetPrepare(
        request_key="test-sheet-key",
        spreadsheet={
            "title": "Budget",
            "tabs": [{"title": "Data", "headers": ["Value"], "rows": [[10]]}],
        },
    )
    prepared = (await sheets_prepare(payload, context)).data
    approval = DocumentApproval(
        operation_id=prepared["operation_id"], approved_digest=prepared["digest"]
    )
    attempts = []

    async def refresh(*args):
        return object()

    class Creator:
        def __init__(self, service):
            pass

        def create(self, spec, checkpoint):
            attempts.append(spec.title)
            checkpoint("created-sheet")
            if failure:
                raise ToolError("Raw provider detail must not persist", code="verification_failed")
            return {"spreadsheet_id": "created-sheet", "verified": True}

    monkeypatch.setattr("app.tools.sheets.refresh_and_store_if_needed", refresh)
    monkeypatch.setattr("app.tools.sheets.build", lambda *args, **kwargs: nullcontext(object()))
    monkeypatch.setattr("app.tools.sheets.SpreadsheetCreator", Creator)
    if failure:
        with pytest.raises(ToolError):
            await sheets_execute(approval, context)
    else:
        assert (await sheets_execute(approval, context)).data["verified"]
    store = OperationStore(tmp_path / "operations.db")
    row = store.get("alice", approval.operation_id)
    assert row["resource_id"] == "created-sheet"
    assert row["state"] == ("uncertain" if failure else "succeeded")
    assert "Raw provider" not in str(row)
    with pytest.raises(ToolError) as repeated:
        await sheets_execute(approval, context)
    assert repeated.value.code == "operation_already_claimed"
    assert attempts == ["Budget"]
    with pytest.raises(ToolError) as wrong_user:
        store.get("bob", approval.operation_id)
    assert wrong_user.value.code == "operation_not_found"
