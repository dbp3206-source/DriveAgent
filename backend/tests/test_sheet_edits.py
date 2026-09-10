from types import SimpleNamespace

import pytest

from app.services.sheet_creator import (
    SpreadsheetCreator,
    SpreadsheetEditIntent,
    SpreadsheetPatchSpec,
)
from app.tools.contracts import ToolError


def response(value):
    return SimpleNamespace(execute=lambda num_retries=0: value)


def test_sheet_patch_is_conflict_checked_raw_batched_and_verified():
    stored = {"values": [["Old", 1]]}
    calls = []
    api = SimpleNamespace(
        get=lambda **kwargs: response(stored),
        batchUpdate=lambda **kwargs: (
            calls.append(kwargs)
            or stored.update(values=kwargs["body"]["data"][0]["values"])
            or response({})
        ),
        batchGet=lambda **kwargs: response({"valueRanges": [stored]}),
    )
    root = SimpleNamespace(spreadsheets=lambda: SimpleNamespace(values=lambda: api))
    spec = SpreadsheetPatchSpec(
        spreadsheet_id="sheet123",
        patches=[
            {
                "sheet_title": "Data",
                "range_a1": "A1:B1",
                "expected_values": [["Old", 1]],
                "new_values": [["=not-a-formula", 2]],
            }
        ],
    )
    result = SpreadsheetCreator(root).apply_patch(spec)
    assert result["verified"] and calls[0]["body"]["valueInputOption"] == "RAW"


def test_sheet_patch_rejects_stale_values():
    api = SimpleNamespace(get=lambda **kwargs: response({"values": [["Changed"]]}))
    root = SimpleNamespace(spreadsheets=lambda: SimpleNamespace(values=lambda: api))
    spec = SpreadsheetPatchSpec(
        spreadsheet_id="sheet123",
        patches=[
            {
                "sheet_title": "Data",
                "range_a1": "A1:A1",
                "expected_values": [["Old"]],
                "new_values": [["New"]],
            }
        ],
    )
    with pytest.raises(ToolError) as error:
        SpreadsheetCreator(root).preview_patch(spec)
    assert error.value.code == "revision_conflict"


def test_sheet_edit_intent_is_bound_to_current_values():
    api = SimpleNamespace(get=lambda **kwargs: response({"values": [["Current", 4]]}))
    root = SimpleNamespace(spreadsheets=lambda: SimpleNamespace(values=lambda: api))
    patch = SpreadsheetCreator(root).prepare_patch(
        SpreadsheetEditIntent(
            spreadsheet_id="sheet123",
            sheet_title="Data",
            range_a1="A1:B1",
            new_values=[["Updated", 5]],
        )
    )
    assert patch.patches[0].expected_values == [["Current", 4]]
    assert patch.patches[0].new_values == [["Updated", 5]]
