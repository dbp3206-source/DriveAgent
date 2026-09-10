from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.services.sheet_creator import (
    SpreadsheetCreator,
    SpreadsheetSpec,
    entered_value,
    spreadsheet_body,
    verify_spreadsheet,
)
from app.tools.contracts import ToolError


def spec():
    return SpreadsheetSpec(
        title="Chi tiêu",
        tabs=[
            {
                "title": "Tháng 9",
                "headers": ["Mục", "Số tiền"],
                "rows": [["Sách", 120], ["Xe buýt", 30]],
                "chart": {"title": "Chi tiêu theo mục", "label_column": 0, "value_column": 1},
            }
        ],
    )


def test_grid_and_chart_use_same_verified_source():
    source = spec()
    body = spreadsheet_body(source)
    assert body["sheets"][0]["properties"]["gridProperties"]["frozenRowCount"] == 1
    chart = body["sheets"][0]["charts"][0]
    series = chart["spec"]["basicChart"]["series"][0]["series"]["sourceRange"]["sources"][0]
    assert series["endRowIndex"] == 3 and series["startColumnIndex"] == 1
    verify_spreadsheet(source, body)


def test_text_is_not_formula_and_boolean_is_not_number():
    assert entered_value('=IMPORTXML("https://example.com", "//x")') == {
        "stringValue": '=IMPORTXML("https://example.com", "//x")',
    }
    assert entered_value(True) == {"boolValue": True}
    assert entered_value(None) == {}


@pytest.mark.parametrize(
    "mutation",
    [
        lambda b: b["sheets"][0]["data"][0]["rowData"][1]["values"][1].update(
            userEnteredValue={"numberValue": 999}
        ),
        lambda b: b["sheets"][0].update(charts=[]),
        lambda b: b["sheets"][0]["charts"][0]["spec"]["basicChart"].update(chartType="LINE"),
        lambda b: b["properties"].update(title="Wrong"),
    ],
)
def test_readback_detects_mismatch(mutation):
    source = spec()
    body = spreadsheet_body(source)
    mutation(body)
    with pytest.raises(ToolError, match="kiểm tra"):
        verify_spreadsheet(source, body)


def test_readback_accepts_server_assigned_chart_id():
    source = spec()
    body = spreadsheet_body(source)
    body["sheets"][0]["charts"][0]["chartId"] = 987654
    verify_spreadsheet(source, body)


def test_formula_requires_evaluated_result():
    source = SpreadsheetSpec(
        title="Sum",
        tabs=[
            {
                "title": "Totals",
                "headers": ["Values"],
                "rows": [
                    [10],
                    [20],
                    [{"function": "SUM", "column": 0, "start_row": 0, "end_row": 2}],
                ],
            }
        ],
    )
    body = spreadsheet_body(source)
    cell = body["sheets"][0]["data"][0]["rowData"][3]["values"][0]
    assert cell["userEnteredValue"] == {"formulaValue": "=SUM(A2:A3)"}
    with pytest.raises(ToolError):
        verify_spreadsheet(source, body)
    cell["effectiveValue"] = {"numberValue": 30}
    verify_spreadsheet(source, body)
    cell["effectiveValue"] = {"numberValue": 300}
    with pytest.raises(ToolError):
        verify_spreadsheet(source, body)
    cell["effectiveValue"] = {"errorValue": {"type": "ERROR"}}
    with pytest.raises(ToolError):
        verify_spreadsheet(source, body)


@pytest.mark.parametrize(
    "rows",
    [
        [[1, 2]],
        [[float("nan")]],
        [[float("inf")]],
        [[10**16]],
        [[{"function": "IMPORTXML", "column": 0, "start_row": 0, "end_row": 1}]],
        [[{"function": "SUM", "column": 0, "start_row": 0, "end_row": 1}]],
        [["not a number"], [{"function": "SUM", "column": 0, "start_row": 0, "end_row": 1}]],
    ],
)
def test_reject_invalid_or_circular_formula_before_google(rows):
    with pytest.raises(ValidationError):
        SpreadsheetSpec(title="Test", tabs=[{"title": "Data", "headers": ["A"], "rows": rows}])


def test_duplicate_sheet_names_rejected():
    source = spec().model_dump()
    source["tabs"].append(deepcopy(source["tabs"][0]))
    with pytest.raises(ValidationError):
        SpreadsheetSpec.model_validate(source)


@pytest.mark.parametrize("broken", [False, True])
def test_create_checkpoints_before_read_and_never_retries(broken):
    source = spec()
    saved, writes = [], []

    def response(value):
        def execute(num_retries):
            assert num_retries == 0
            return value

        return SimpleNamespace(execute=execute)

    def create(body):
        writes.append(body)
        return response({"spreadsheetId": "sheet123"})

    def get(**kwargs):
        assert saved == ["sheet123"]
        assert kwargs == {"spreadsheetId": "sheet123", "includeGridData": True}
        return response({} if broken else spreadsheet_body(source))

    service = SimpleNamespace(spreadsheets=lambda: SimpleNamespace(create=create, get=get))
    if broken:
        with pytest.raises(ToolError):
            SpreadsheetCreator(service).create(source, saved.append)
    else:
        assert SpreadsheetCreator(service).create(source, saved.append)["verified"]
    assert saved == ["sheet123"] and len(writes) == 1
