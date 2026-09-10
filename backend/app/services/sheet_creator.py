"""Deterministic Sheets creation. Text is never implicitly interpreted as a formula.

Formula syntax is deliberately structured: only local numeric aggregates are
allowed, not network imports, scripts or arbitrary expressions from a document.
The caller must obtain approval and checkpoint the new ID before verification.
"""

import math
import re
from collections.abc import Callable
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

from app.tools.contracts import ToolError


class SheetFormula(BaseModel):
    model_config = ConfigDict(extra="forbid")
    function: Literal["SUM", "AVERAGE", "MIN", "MAX", "COUNT"]
    column: int = Field(ge=0, le=25)
    # Zero-based, half-open DATA row range; headers are not counted.
    start_row: int = Field(ge=0)
    end_row: int = Field(ge=1, le=1000)

    @model_validator(mode="after")
    def ordered(self):
        if self.end_row <= self.start_row:
            raise ValueError("Formula range must be nonempty")
        return self


CellValue = StrictStr | StrictInt | StrictFloat | StrictBool | SheetFormula | None


class SheetChart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=150)
    kind: Literal["COLUMN", "BAR", "LINE"] = "COLUMN"
    label_column: int = Field(ge=0, le=25)
    value_column: int = Field(ge=0, le=25)


class SheetTab(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    title: str = Field(min_length=1, max_length=80, pattern=r"^[^\[\]:*?/\\]+$")
    headers: list[str] = Field(min_length=1, max_length=26)
    rows: list[list[CellValue]] = Field(min_length=1, max_length=1000)
    chart: SheetChart | None = None

    @model_validator(mode="after")
    def validate_grid(self):
        width = len(self.headers)
        if any(len(row) != width for row in self.rows):
            raise ValueError("Every row must match the header width")
        for row in self.rows:
            for value in row:
                if type(value) in (int, float) and (abs(value) > 1e15 or not math.isfinite(value)):
                    raise ValueError("Numeric cells must be finite and within ±10^15")
                if isinstance(value, str) and len(value) > 10000:
                    raise ValueError("Cell text exceeds 10,000 characters")
                if isinstance(value, SheetFormula):
                    if value.column >= width or value.end_row > len(self.rows):
                        raise ValueError("Formula range exceeds this sheet")
                    # Only raw numeric cells can feed aggregates: no cycles or
                    # surprising coercion of dates, text, booleans or formulas.
                    for source in self.rows[value.start_row : value.end_row]:
                        if type(source[value.column]) not in (int, float):
                            raise ValueError("Formula range must contain only numeric cells")
        if any(not label.strip() or len(label) > 200 for label in self.headers):
            raise ValueError("Headers must have 1–200 visible characters")
        if self.chart:
            if max(self.chart.label_column, self.chart.value_column) >= width:
                raise ValueError("Chart column exceeds this sheet")
            if self.chart.label_column == self.chart.value_column:
                raise ValueError("Chart label and value must use different columns")
            if any(type(row[self.chart.value_column]) not in (int, float) for row in self.rows):
                raise ValueError("Chart values must be numeric")
        return self


class SpreadsheetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    tabs: list[SheetTab] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_bounded(self):
        if len({tab.title.casefold() for tab in self.tabs}) != len(self.tabs):
            raise ValueError("Sheet titles must be unique")
        if sum(len(tab.rows) * len(tab.headers) for tab in self.tabs) > 10000:
            raise ValueError("Workbook exceeds 10,000 data cells")
        if len(self.model_dump_json()) > 500000:
            raise ValueError("Workbook exceeds the payload budget")
        return self


class SheetRangePatch(BaseModel):
    """One reviewed range replacement; expected values provide conflict detection."""

    model_config = ConfigDict(extra="forbid")
    sheet_title: str = Field(min_length=1, max_length=80, pattern=r"^[^\[\]:*?/\\]+$")
    range_a1: str = Field(pattern=r"^[A-Z]{1,2}[1-9][0-9]{0,3}:[A-Z]{1,2}[1-9][0-9]{0,3}$")
    expected_values: list[list[StrictStr | StrictInt | StrictFloat | StrictBool | None]] = Field(
        min_length=1, max_length=1000
    )
    new_values: list[list[StrictStr | StrictInt | StrictFloat | StrictBool | None]] = Field(
        min_length=1, max_length=1000
    )

    @model_validator(mode="after")
    def same_shape(self):
        match = re.fullmatch(r"([A-Z]{1,2})(\d+):([A-Z]{1,2})(\d+)", self.range_a1)
        assert match

        def column(value: str) -> int:
            result = 0
            for char in value:
                result = result * 26 + ord(char) - 64
            return result

        rows = int(match[4]) - int(match[2]) + 1
        cols = column(match[3]) - column(match[1]) + 1
        if rows < 1 or cols < 1 or rows * cols > 5000:
            raise ValueError("Range must be ordered and contain at most 5,000 cells")
        for grid in (self.expected_values, self.new_values):
            if len(grid) != rows or any(len(row) != cols for row in grid):
                raise ValueError("Range dimensions and values do not match")
        return self


class SpreadsheetPatchSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spreadsheet_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,200}$")
    patches: list[SheetRangePatch] = Field(min_length=1, max_length=20)


class SpreadsheetEditIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spreadsheet_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,200}$")
    sheet_title: str = Field(min_length=1, max_length=80, pattern=r"^[^\[\]:*?/\\]+$")
    range_a1: str = Field(
        pattern=r"^[A-Z]{1,2}[1-9][0-9]{0,3}:[A-Z]{1,2}[1-9][0-9]{0,3}$"
    )
    new_values: list[list[StrictStr | StrictInt | StrictFloat | StrictBool | None]] = Field(
        min_length=1, max_length=1000
    )


def entered_value(value: CellValue) -> dict:
    if value is None:
        return {}
    if isinstance(value, SheetFormula):
        column = chr(ord("A") + value.column)
        cell_range = f"{column}{value.start_row + 2}:{column}{value.end_row + 1}"
        return {"formulaValue": f"={value.function}({cell_range})"}
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, (int, float)):
        return {"numberValue": value}
    return {"stringValue": value}


def spreadsheet_body(spec: SpreadsheetSpec) -> dict:
    sheets = []
    for sheet_id, tab in enumerate(spec.tabs):
        rows = [tab.headers, *tab.rows]
        sheet = {
            "properties": {
                "sheetId": sheet_id,
                "title": tab.title,
                "gridProperties": {
                    "rowCount": max(50, len(rows)),
                    "columnCount": max(12, len(tab.headers)),
                    "frozenRowCount": 1,
                },
            },
            "data": [
                {
                    "startRow": 0,
                    "startColumn": 0,
                    "rowData": [
                        {"values": [{"userEnteredValue": entered_value(value)} for value in row]}
                        for row in rows
                    ],
                }
            ],
        }
        if tab.chart:

            def source(column, sheet_id=sheet_id, row_count=len(rows)):
                return {
                    "sourceRange": {
                        "sources": [
                            {
                                "sheetId": sheet_id,
                                "startRowIndex": 0,
                                "endRowIndex": row_count,
                                "startColumnIndex": column,
                                "endColumnIndex": column + 1,
                            }
                        ]
                    }
                }

            sheet["charts"] = [
                {
                    "chartId": sheet_id + 100,
                    "spec": {
                        "title": tab.chart.title,
                        "basicChart": {
                            "chartType": tab.chart.kind,
                            "headerCount": 1,
                            "legendPosition": "NO_LEGEND",
                            "domains": [{"domain": source(tab.chart.label_column)}],
                            "series": [{"series": source(tab.chart.value_column)}],
                        },
                    },
                    "position": {
                        "overlayPosition": {
                            "anchorCell": {
                                "sheetId": sheet_id,
                                "rowIndex": 1,
                                "columnIndex": len(tab.headers) + 1,
                            },
                            "widthPixels": 640,
                            "heightPixels": 400,
                        }
                    },
                }
            ]
            sheet["properties"]["gridProperties"]["columnCount"] = max(12, len(tab.headers) + 2)
        sheets.append(sheet)
    return {"properties": {"title": spec.title, "locale": "en_US"}, "sheets": sheets}


def verify_spreadsheet(spec: SpreadsheetSpec, actual: dict) -> None:
    """Check stored values AND evaluated formula errors, not just HTTP success."""

    def fail():
        raise ToolError(
            "Bảng tính đã tạo nhưng chưa qua kiểm tra nội dung.", code="verification_failed"
        )

    if actual.get("properties", {}).get("title") != spec.title:
        fail()
    sheets = actual.get("sheets", [])
    if len(sheets) != len(spec.tabs):
        fail()
    for sheet_id, tab in enumerate(spec.tabs):
        matches = [s for s in sheets if s.get("properties", {}).get("sheetId") == sheet_id]
        if len(matches) != 1:
            fail()
        sheet = matches[0]
        if sheet["properties"].get("title") != tab.title:
            fail()
        cells = {}
        for grid in sheet.get("data", []):
            for r, row in enumerate(grid.get("rowData", []), grid.get("startRow", 0)):
                for c, cell in enumerate(row.get("values", []), grid.get("startColumn", 0)):
                    cells[r, c] = cell
        for r, row in enumerate([tab.headers, *tab.rows]):
            for c, value in enumerate(row):
                cell = cells.get((r, c), {})
                if cell.get("userEnteredValue", {}) != entered_value(value):
                    fail()
                if isinstance(value, SheetFormula):
                    effective = cell.get("effectiveValue", {})
                    if "numberValue" not in effective or "errorValue" in effective:
                        fail()
                    values = [
                        source[value.column] for source in tab.rows[value.start_row : value.end_row]
                    ]
                    expected_number = {
                        "SUM": sum(values),
                        "AVERAGE": sum(values) / len(values),
                        "MIN": min(values),
                        "MAX": max(values),
                        "COUNT": len(values),
                    }[value.function]
                    if not math.isclose(
                        effective["numberValue"], expected_number, rel_tol=1e-10, abs_tol=1e-10
                    ):
                        fail()
        expected_charts = spreadsheet_body(spec)["sheets"][sheet_id].get("charts", [])
        charts = sheet.get("charts", [])
        if len(charts) != len(expected_charts):
            fail()
        for chart, expected in zip(charts, expected_charts, strict=True):
            # Google may replace a requested chartId. Identity is not part of
            # the reviewed spreadsheet content, so verify the semantic spec.
            chart_spec = chart.get("spec", {})
            if chart_spec.get("title") != expected["spec"]["title"]:
                fail()
            for key in ("chartType", "domains", "series", "headerCount"):
                if chart_spec.get("basicChart", {}).get(key) != expected["spec"]["basicChart"][key]:
                    fail()


class SpreadsheetCreator:
    def __init__(self, service):
        self.service = service
        self.spreadsheets = service.spreadsheets()

    def create(self, spec: SpreadsheetSpec, on_created: Callable[[str], None]) -> dict:
        # One create request includes every tab/cell/chart; never retry this write.
        created = self.spreadsheets.create(body=spreadsheet_body(spec)).execute(num_retries=0)
        resource_id = created["spreadsheetId"]
        on_created(resource_id)
        actual = self.spreadsheets.get(spreadsheetId=resource_id, includeGridData=True).execute(
            num_retries=0
        )
        verify_spreadsheet(spec, actual)
        return {
            "spreadsheet_id": resource_id,
            "verified": True,
            "url": f"https://docs.google.com/spreadsheets/d/{resource_id}/edit",
        }

    @staticmethod
    def _rectangular(values: list[list], rows: int, columns: int) -> list[list]:
        return [
            [
                (values[r][c] if r < len(values) and c < len(values[r]) else None)
                for c in range(columns)
            ]
            for r in range(rows)
        ]

    def preview_patch(self, spec: SpreadsheetPatchSpec) -> None:
        for patch in spec.patches:
            full_range = f"'{patch.sheet_title}'!{patch.range_a1}"
            actual = (
                self.service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=spec.spreadsheet_id,
                    range=full_range,
                    valueRenderOption="UNFORMATTED_VALUE",
                    dateTimeRenderOption="SERIAL_NUMBER",
                )
                .execute(num_retries=0)
                .get("values", [])
            )
            rows, columns = len(patch.expected_values), len(patch.expected_values[0])
            if self._rectangular(actual, rows, columns) != patch.expected_values:
                raise ToolError(
                    "Bảng tính đã thay đổi; cần xem lại bản sửa.", code="revision_conflict"
                )

    def prepare_patch(self, intent: SpreadsheetEditIntent) -> SpreadsheetPatchSpec:
        match = re.fullmatch(r"([A-Z]{1,2})(\d+):([A-Z]{1,2})(\d+)", intent.range_a1)
        assert match

        def column(value: str) -> int:
            result = 0
            for char in value:
                result = result * 26 + ord(char) - 64
            return result

        rows = int(match[4]) - int(match[2]) + 1
        columns = column(match[3]) - column(match[1]) + 1
        if len(intent.new_values) != rows or any(
            len(row) != columns for row in intent.new_values
        ):
            raise ToolError("Dữ liệu mới không khớp kích thước range.", code="invalid_patch")
        full_range = f"'{intent.sheet_title}'!{intent.range_a1}"
        actual = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=intent.spreadsheet_id,
                range=full_range,
                valueRenderOption="UNFORMATTED_VALUE",
                dateTimeRenderOption="SERIAL_NUMBER",
            )
            .execute(num_retries=0)
            .get("values", [])
        )
        return SpreadsheetPatchSpec(
            spreadsheet_id=intent.spreadsheet_id,
            patches=[
                SheetRangePatch(
                    sheet_title=intent.sheet_title,
                    range_a1=intent.range_a1,
                    expected_values=self._rectangular(actual, rows, columns),
                    new_values=intent.new_values,
                )
            ],
        )

    def apply_patch(self, spec: SpreadsheetPatchSpec) -> dict:
        self.preview_patch(spec)
        data = [
            {"range": f"'{patch.sheet_title}'!{patch.range_a1}", "values": patch.new_values}
            for patch in spec.patches
        ]
        # RAW prevents untrusted strings beginning with '=' from becoming formulas.
        values = self.service.spreadsheets().values()
        values.batchUpdate(
            spreadsheetId=spec.spreadsheet_id,
            body={"valueInputOption": "RAW", "data": data},
        ).execute(num_retries=0)
        checked = (
            values.batchGet(
                spreadsheetId=spec.spreadsheet_id,
                ranges=[item["range"] for item in data],
                valueRenderOption="UNFORMATTED_VALUE",
                dateTimeRenderOption="SERIAL_NUMBER",
            )
            .execute(num_retries=0)
            .get("valueRanges", [])
        )
        if len(checked) != len(spec.patches):
            raise ToolError("Bản sửa Sheets chưa qua kiểm tra.", code="verification_failed")
        for actual, patch in zip(checked, spec.patches, strict=True):
            rows, columns = len(patch.new_values), len(patch.new_values[0])
            if self._rectangular(actual.get("values", []), rows, columns) != patch.new_values:
                raise ToolError("Bản sửa Sheets chưa qua kiểm tra.", code="verification_failed")
        return {
            "spreadsheet_id": spec.spreadsheet_id,
            "verified": True,
            "ranges_updated": len(spec.patches),
            "url": f"https://docs.google.com/spreadsheets/d/{spec.spreadsheet_id}/edit",
        }
