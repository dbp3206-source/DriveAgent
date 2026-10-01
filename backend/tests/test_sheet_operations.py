from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from app.services.operations import OperationStore
from app.services.sheet_creator import SpreadsheetSpec, spreadsheet_body
from app.tools.contracts import ToolError
from app.tools.documents import DocumentApproval
from app.tools.sheets import (
    SpreadsheetPrepare,
    sheets_execute,
    sheets_prepare,
    sheets_reconcile,
)


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


async def test_uncertain_sheet_reconciliation_only_reads_checkpointed_file(
    tmp_path, monkeypatch
):
    context = SimpleNamespace(
        user=SimpleNamespace(id="alice"),
        db=None,
        settings=SimpleNamespace(data_dir=tmp_path),
    )
    spec = SpreadsheetSpec(
        title="QA budget",
        tabs=[{"title": "Data", "headers": ["Mục", "Số"], "rows": [["Sách", 120]]}],
    )
    store = OperationStore(tmp_path / "operations.db")
    row = store.prepare(
        "alice",
        "reconcile-sheet-key",
        "sheets_create",
        SpreadsheetPrepare(
            request_key="reconcile-sheet-key", spreadsheet=spec
        ).model_dump(mode="json"),
    )
    store.claim("alice", row["id"], row["digest"])
    store.checkpoint("alice", row["id"], "sheet-checkpoint")
    store.uncertain("alice", row["id"], "verification_failed")

    async def credentials(*_args):
        return object()

    def response(value):
        return SimpleNamespace(execute=lambda num_retries: value)

    spreadsheets = SimpleNamespace(
        get=lambda **kwargs: response(spreadsheet_body(spec)),
        create=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("Reconciliation must never create a second file")
        ),
    )
    service = SimpleNamespace(spreadsheets=lambda: spreadsheets)
    monkeypatch.setattr("app.tools.sheets.refresh_and_store_if_needed", credentials)
    monkeypatch.setattr(
        "app.tools.sheets.build", lambda *_args, **_kwargs: nullcontext(service)
    )

    result = await sheets_reconcile(row["id"], context)
    assert result.data["verified"] is True
    assert result.data["reconciled"] is True
    finished = store.get("alice", row["id"])
    assert finished["state"] == "succeeded"
    assert finished["error_code"] is None


async def test_uncertain_sheet_edit_reconciliation_only_reads_reviewed_ranges(
    tmp_path, monkeypatch
):
    context = SimpleNamespace(
        user=SimpleNamespace(id="alice"),
        db=None,
        settings=SimpleNamespace(data_dir=tmp_path),
    )
    prepared_spec = SpreadsheetPrepare(
        request_key="reconcile-edit-key",
        action="edit",
        patch={
            "spreadsheet_id": "sheet-checkpoint",
            "patches": [
                {
                    "sheet_title": "Data",
                    "range_a1": "A1:B1",
                    "expected_values": [["Old", 1]],
                    "new_values": [["New", 2]],
                }
            ],
        },
    )
    store = OperationStore(tmp_path / "operations.db")
    row = store.prepare(
        "alice",
        "reconcile-edit-key",
        "sheets_edit",
        prepared_spec.model_dump(mode="json", exclude={"edit"}),
    )
    store.claim("alice", row["id"], row["digest"])
    store.checkpoint("alice", row["id"], "sheet-checkpoint")
    store.uncertain("alice", row["id"], "google_execution_uncertain")

    async def credentials(*_args):
        return object()

    reads = []

    def response(value):
        return SimpleNamespace(execute=lambda num_retries=0: value)

    values = SimpleNamespace(
        batchGet=lambda **kwargs: (
            reads.append(kwargs) or response({"valueRanges": [{"values": [["New", 2]]}]})
        ),
        batchUpdate=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("Reconciliation must never repeat an edit")
        ),
    )
    service = SimpleNamespace(
        spreadsheets=lambda: SimpleNamespace(values=lambda: values)
    )
    monkeypatch.setattr("app.tools.sheets.refresh_and_store_if_needed", credentials)
    monkeypatch.setattr(
        "app.tools.sheets.build", lambda *_args, **_kwargs: nullcontext(service)
    )

    result = await sheets_reconcile(row["id"], context)
    assert result.data["verified"] is True
    assert result.data["ranges_updated"] == 1
    assert reads[0]["spreadsheetId"] == "sheet-checkpoint"
    assert store.get("alice", row["id"])["state"] == "succeeded"


async def test_sheet_edit_checkpoints_target_before_external_write(tmp_path, monkeypatch):
    context = SimpleNamespace(
        user=SimpleNamespace(id="alice"),
        db=None,
        settings=SimpleNamespace(data_dir=tmp_path),
    )
    spec = SpreadsheetPrepare(
        request_key="edit-checkpoint-key",
        action="edit",
        patch={
            "spreadsheet_id": "sheet123",
            "patches": [
                {
                    "sheet_title": "Data",
                    "range_a1": "A1:A1",
                    "expected_values": [["Old"]],
                    "new_values": [["New"]],
                }
            ],
        },
    )
    prepared = OperationStore(tmp_path / "operations.db").prepare(
        "alice",
        "edit-checkpoint-key",
        "sheets_edit",
        spec.model_dump(mode="json", exclude={"edit"}),
    )

    async def credentials(*_args):
        return object()

    class Creator:
        def __init__(self, _service):
            pass

        def apply_patch(self, _spec):
            row = OperationStore(tmp_path / "operations.db").get(
                "alice", prepared["id"]
            )
            assert row["resource_id"] == "sheet123"
            raise ToolError("uncertain", code="google_execution_uncertain")

    monkeypatch.setattr("app.tools.sheets.refresh_and_store_if_needed", credentials)
    monkeypatch.setattr("app.tools.sheets.build", lambda *_args, **_kwargs: nullcontext(object()))
    monkeypatch.setattr("app.tools.sheets.SpreadsheetCreator", Creator)

    with pytest.raises(ToolError):
        await sheets_execute(
            DocumentApproval(
                operation_id=prepared["id"], approved_digest=prepared["digest"]
            ),
            context,
        )
    row = OperationStore(tmp_path / "operations.db").get("alice", prepared["id"])
    assert row["state"] == "uncertain"
    assert row["resource_id"] == "sheet123"
