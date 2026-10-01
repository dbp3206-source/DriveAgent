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


class SheetRowFormula(BaseModel):
    """Safe same-row subtraction for budgets and variance trackers."""

    model_config = ConfigDict(extra="forbid")
    operator: Literal["SUBTRACT"]
    left_column: int = Field(ge=0, le=25)
    right_column: int = Field(ge=0, le=25)
    row: int = Field(ge=0, le=999)

    @model_validator(mode="after")
    def different_sources(self):
        if self.left_column == self.right_column:
            raise ValueError("Subtraction needs two different source columns")
        return self


CellValue = (
    StrictStr | StrictInt | StrictFloat | StrictBool | SheetFormula | SheetRowFormula | None
)


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
        for row_index, row in enumerate(self.rows):
            for column_index, value in enumerate(row):
                if type(value) in (int, float) and (abs(value) > 1e15 or not math.isfinite(value)):
                    raise ValueError("Numeric cells must be finite and within ±10^15")
                if isinstance(value, str) and len(value) > 10000:
                    raise ValueError("Cell text exceeds 10,000 characters")
                if isinstance(value, SheetFormula):
                    if value.column >= width or value.end_row > len(self.rows):
                        raise ValueError("Formula range exceeds this sheet")
                if isinstance(value, SheetRowFormula):
                    if max(value.left_column, value.right_column) >= width:
                        raise ValueError("Formula column exceeds this sheet")
                    if value.row >= len(self.rows):
                        raise ValueError("Formula row exceeds this sheet")
                    if value.row != row_index:
                        raise ValueError("Row formula must stay on its own data row")
                    if column_index in {value.left_column, value.right_column}:
                        raise ValueError("Row formula cannot reference itself")
        if any(not label.strip() or len(label) > 200 for label in self.headers):
            raise ValueError("Headers must have 1–200 visible characters")
        if self.chart:
            if max(self.chart.label_column, self.chart.value_column) >= width:
                raise ValueError("Chart column exceeds this sheet")
            if self.chart.label_column == self.chart.value_column:
                raise ValueError("Chart label and value must use different columns")
            if any(type(row[self.chart.value_column]) not in (int, float) for row in self.rows):
                raise ValueError("Chart values must be numeric")
        # Resolve the complete dependency graph locally. This rejects cycles,
        # text coercion and invalid references before any write is proposed.
        for row_index, row in enumerate(self.rows):
            for column_index, value in enumerate(row):
                if isinstance(value, (SheetFormula, SheetRowFormula)):
                    evaluate_cell(self.rows, row_index, column_index)
        return self


class SpreadsheetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    theme: Literal["editorial", "study", "finance"] = "editorial"
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
    """One reviewed range replacement with value/formula conflict detection."""

    model_config = ConfigDict(extra="forbid")
    sheet_title: str = Field(min_length=1, max_length=80, pattern=r"^[^\[\]:*?/\\]+$")
    range_a1: str = Field(pattern=r"^[A-Z]{1,2}[1-9][0-9]{0,3}:[A-Z]{1,2}[1-9][0-9]{0,3}$")
    expected_values: list[list[StrictStr | StrictInt | StrictFloat | StrictBool | None]] = Field(
        min_length=1, max_length=1000
    )
    expected_formulas: list[list[StrictStr | None]] | None = Field(
        default=None, max_length=1000
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
        if self.expected_formulas is None:
            # Backward-compatible normalization for stored approvals. A live
            # formula will still conflict with this all-None fingerprint.
            self.expected_formulas = [[None for _ in range(cols)] for _ in range(rows)]
        elif len(self.expected_formulas) != rows or any(
            len(row) != cols for row in self.expected_formulas
        ):
            raise ValueError("Range dimensions and formula fingerprints do not match")
        else:
            self.expected_formulas = [
                [
                    value if isinstance(value, str) and value.startswith("=") else None
                    for value in row
                ]
                for row in self.expected_formulas
            ]
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
    if isinstance(value, SheetRowFormula):
        left = chr(ord("A") + value.left_column)
        right = chr(ord("A") + value.right_column)
        row = value.row + 2
        return {"formulaValue": f"={left}{row}-{right}{row}"}
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, (int, float)):
        return {"numberValue": value}
    return {"stringValue": value}


def evaluate_cell(
    rows: list[list[CellValue]],
    row: int,
    column: int,
    visiting: set[tuple[int, int]] | None = None,
) -> int | float:
    """Evaluate the deliberately small formula language for verification."""

    visiting = set() if visiting is None else visiting
    key = (row, column)
    if key in visiting:
        raise ValueError("Formula dependency cycle is not allowed")
    if row >= len(rows) or column >= len(rows[row]):
        raise ValueError("Formula reference exceeds this sheet")
    value = rows[row][column]
    if type(value) in (int, float):
        return value
    visiting.add(key)
    try:
        if isinstance(value, SheetRowFormula):
            left = evaluate_cell(rows, value.row, value.left_column, visiting)
            right = evaluate_cell(rows, value.row, value.right_column, visiting)
            return left - right
        if isinstance(value, SheetFormula):
            values = [
                evaluate_cell(rows, source_row, value.column, visiting)
                for source_row in range(value.start_row, value.end_row)
                if rows[source_row][value.column] is not None
            ]
            if value.function == "SUM":
                return sum(values)
            if value.function == "COUNT":
                return len(values)
            if not values:
                raise ValueError("Non-sum aggregate needs at least one numeric cell")
            if value.function == "AVERAGE":
                return sum(values) / len(values)
            if value.function == "MIN":
                return min(values)
            return max(values)
    finally:
        visiting.remove(key)
    raise ValueError("Formula source must resolve to a number")


SHEET_THEMES = {
    "editorial": {
        "header": {"red": 0.08, "green": 0.14, "blue": 0.25},
        "stripe": {"red": 0.95, "green": 0.97, "blue": 1.0},
    },
    "study": {
        "header": {"red": 0.04, "green": 0.27, "blue": 0.25},
        "stripe": {"red": 0.94, "green": 0.98, "blue": 0.96},
    },
    "finance": {
        "header": {"red": 0.1, "green": 0.13, "blue": 0.12},
        "stripe": {"red": 0.94, "green": 0.97, "blue": 0.94},
    },
}


def _cell(value: CellValue, *, header: bool, striped: bool, theme: str) -> dict:
    palette = SHEET_THEMES[theme]
    cell = {
        "userEnteredValue": entered_value(value),
        "userEnteredFormat": {
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "WRAP",
            "horizontalAlignment": (
                "CENTER" if header else "RIGHT" if type(value) in (int, float) else "LEFT"
            ),
            "textFormat": {
                "fontFamily": "Arial",
                "fontSize": 10,
                "bold": header,
                "foregroundColor": (
                    {"red": 1.0, "green": 1.0, "blue": 1.0}
                    if header
                    else {"red": 0.12, "green": 0.13, "blue": 0.15}
                ),
            },
        },
    }
    if header:
        cell["userEnteredFormat"]["backgroundColor"] = palette["header"]
    elif striped:
        cell["userEnteredFormat"]["backgroundColor"] = palette["stripe"]
    return cell


def _column_width(tab: SheetTab, column: int) -> int:
    values = [tab.headers[column], *(row[column] for row in tab.rows[:100])]
    visible = [
        "Công thức" if isinstance(value, SheetFormula) else "" if value is None else str(value)
        for value in values
    ]
    return max(100, min(280, max(len(value) for value in visible) * 8 + 32))


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
                        {
                            "values": [
                                _cell(
                                    value,
                                    header=row_index == 0,
                                    striped=row_index > 0 and row_index % 2 == 0,
                                    theme=spec.theme,
                                )
                                for value in row
                            ]
                        }
                        for row_index, row in enumerate(rows)
                    ],
                    "rowMetadata": [
                        {"pixelSize": 34 if row_index == 0 else 28}
                        for row_index in range(len(rows))
                    ],
                    "columnMetadata": [
                        {"pixelSize": _column_width(tab, column)}
                        for column in range(len(tab.headers))
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
    return {"properties": {"title": spec.title, "locale": "vi_VN"}, "sheets": sheets}


def _colors_match(c1: dict | None, c2: dict | None) -> bool:
    if not c1 or not c2:
        return c1 == c2
    return all(
        math.isclose(float(c1.get(k, 0)), float(c2.get(k, 0)), abs_tol=0.03)
        for k in ("red", "green", "blue")
    )


def _entered_values_match(expected: dict, actual: dict) -> bool:
    """Accept Google's harmless normalization of a one-cell aggregate range.

    Sheets stores ``=SUM(B2:B2)`` as ``=SUM(B2)``. Both formulas have the same
    dependency and the effective value is verified separately below; all other
    entered values and formulas still require an exact match.
    """

    if actual == expected:
        return True
    expected_formula = expected.get("formulaValue")
    actual_formula = actual.get("formulaValue")
    if not expected_formula or not actual_formula:
        return False
    one_cell = re.fullmatch(
        r"=(SUM|AVERAGE|MIN|MAX|COUNT)\(([A-Z]+\d+):\2\)", expected_formula
    )
    return bool(
        one_cell and actual_formula == f"={one_cell.group(1)}({one_cell.group(2)})"
    )


def verify_spreadsheet(spec: SpreadsheetSpec, actual: dict) -> None:
    """Check stored values AND evaluated formula errors, not just HTTP success."""

    def fail(reason: str):
        raise ToolError(
            f"Bảng tính đã tạo nhưng chưa qua kiểm tra nội dung: {reason}.",
            code="verification_failed",
        )

    if actual.get("properties", {}).get("title") != spec.title:
        fail("tiêu đề không khớp")
    sheets = actual.get("sheets", [])
    if len(sheets) != len(spec.tabs):
        fail("số tab không khớp")
    for sheet_id, tab in enumerate(spec.tabs):
        matches = [s for s in sheets if s.get("properties", {}).get("sheetId") == sheet_id]
        if len(matches) != 1:
            fail(f"không tìm thấy tab số {sheet_id + 1}")
        sheet = matches[0]
        if sheet["properties"].get("title") != tab.title:
            fail(f"tên tab số {sheet_id + 1} không khớp")
        if sheet["properties"].get("gridProperties", {}).get("frozenRowCount") != 1:
            fail(f"tab {tab.title} chưa cố định hàng tiêu đề")
        cells = {}
        for grid in sheet.get("data", []):
            for r, row in enumerate(grid.get("rowData", []), grid.get("startRow", 0)):
                for c, cell in enumerate(row.get("values", []), grid.get("startColumn", 0)):
                    cells[r, c] = cell
        for r, row in enumerate([tab.headers, *tab.rows]):
            for c, value in enumerate(row):
                cell = cells.get((r, c), {})
                if not _entered_values_match(
                    entered_value(value), cell.get("userEnteredValue", {})
                ):
                    fail(f"giá trị ô hàng {r + 1}, cột {c + 1} không khớp")
                if r == 0:
                    header_format = cell.get("userEnteredFormat", {})
                    if not _colors_match(
                        header_format.get("backgroundColor"), SHEET_THEMES[spec.theme]["header"]
                    ):
                        fail(f"màu tiêu đề cột {c + 1} không khớp")
                    if header_format.get("textFormat", {}).get("bold") is not True:
                        fail(f"tiêu đề cột {c + 1} chưa in đậm")
                if isinstance(value, (SheetFormula, SheetRowFormula)):
                    effective = cell.get("effectiveValue", {})
                    if "numberValue" not in effective or "errorValue" in effective:
                        fail(f"công thức hàng {r + 1}, cột {c + 1} chưa tính được")
                    expected_number = evaluate_cell(tab.rows, r - 1, c)
                    if not math.isclose(
                        effective["numberValue"], expected_number, rel_tol=1e-10, abs_tol=1e-10
                    ):
                        fail(f"kết quả công thức hàng {r + 1}, cột {c + 1} sai")
        expected_charts = spreadsheet_body(spec)["sheets"][sheet_id].get("charts", [])
        charts = sheet.get("charts", [])
        if len(charts) != len(expected_charts):
            fail(f"số biểu đồ trên tab {tab.title} không khớp")
        for chart, expected in zip(charts, expected_charts, strict=True):
            # Google may replace a requested chartId. Identity is not part of
            # the reviewed spreadsheet content, so verify the semantic spec.
            chart_spec = chart.get("spec", {})
            if chart_spec.get("title") != expected["spec"]["title"]:
                fail(f"tiêu đề biểu đồ trên tab {tab.title} không khớp")
            for key in ("chartType", "headerCount"):
                if chart_spec.get("basicChart", {}).get(key) != expected["spec"]["basicChart"][key]:
                    fail(f"cấu hình {key} của biểu đồ trên tab {tab.title} không khớp")

            def _normalize_range(source_obj, current_sheet_id=sheet_id):
                src = source_obj.get("sourceRange", {}).get("sources", [{}])[0]
                return (
                    # The Sheets API omits ``sheetId`` when the range belongs
                    # to the first sheet (whose id is 0).  Treat that compact
                    # representation as the current sheet, while still
                    # rejecting an explicit id that points elsewhere.
                    src.get("sheetId", current_sheet_id),
                    src.get("startRowIndex"),
                    src.get("endRowIndex"),
                    src.get("startColumnIndex"),
                    src.get("endColumnIndex"),
                )

            actual_domain = _normalize_range(
                chart_spec.get("basicChart", {}).get("domains", [{}])[0].get("domain", {})
            )
            expected_domain = _normalize_range(
                expected["spec"]["basicChart"]["domains"][0]["domain"]
            )
            if actual_domain != expected_domain:
                fail(f"cấu hình domains của biểu đồ trên tab {tab.title} không khớp")

            actual_series = _normalize_range(
                chart_spec.get("basicChart", {}).get("series", [{}])[0].get("series", {})
            )
            expected_series = _normalize_range(
                expected["spec"]["basicChart"]["series"][0]["series"]
            )
            if actual_series != expected_series:
                fail(f"cấu hình series của biểu đồ trên tab {tab.title} không khớp")


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

    @staticmethod
    def _formula_markers(values: list[list]) -> list[list[str | None]]:
        """Keep exact formulas and erase ordinary rendered values."""

        return [
            [value if isinstance(value, str) and value.startswith("=") else None for value in row]
            for row in values
        ]

    def _read_range(
        self, spreadsheet_id: str, patch: SheetRangePatch, *, render_option: str
    ) -> list[list]:
        full_range = f"'{patch.sheet_title}'!{patch.range_a1}"
        return (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=full_range,
                valueRenderOption=render_option,
                dateTimeRenderOption="SERIAL_NUMBER",
            )
            .execute(num_retries=0)
            .get("values", [])
        )

    def preview_patch(self, spec: SpreadsheetPatchSpec) -> None:
        for patch in spec.patches:
            rows, columns = len(patch.expected_values), len(patch.expected_values[0])
            actual = self._rectangular(
                self._read_range(
                    spec.spreadsheet_id, patch, render_option="UNFORMATTED_VALUE"
                ),
                rows,
                columns,
            )
            if actual != patch.expected_values:
                raise ToolError(
                    "Bảng tính đã thay đổi; cần xem lại bản sửa.", code="revision_conflict"
                )
            actual_formulas = self._rectangular(
                self._read_range(spec.spreadsheet_id, patch, render_option="FORMULA"),
                rows,
                columns,
            )
            if self._formula_markers(actual_formulas) != patch.expected_formulas:
                raise ToolError(
                    "Bảng tính đã thay đổi công thức; cần xem lại bản sửa.",
                    code="revision_conflict",
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
        formulas = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=intent.spreadsheet_id,
                range=full_range,
                valueRenderOption="FORMULA",
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
                    expected_formulas=self._formula_markers(
                        self._rectangular(formulas, rows, columns)
                    ),
                    new_values=intent.new_values,
                )
            ],
        )

    def apply_patch(self, spec: SpreadsheetPatchSpec) -> dict:
        # Google Sheets values.batchUpdate has no compare-and-swap primitive.
        # Two immediate formula-aware reads reject edits that arrive between
        # preview and approval. A tiny race can still occur after the final
        # read, so this remains single-attempt and never claims full atomicity.
        self.preview_patch(spec)
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
        self.verify_patch_applied(spec)
        return {
            "spreadsheet_id": spec.spreadsheet_id,
            "verified": True,
            "ranges_updated": len(spec.patches),
            "url": f"https://docs.google.com/spreadsheets/d/{spec.spreadsheet_id}/edit",
        }

    def verify_patch_applied(self, spec: SpreadsheetPatchSpec) -> None:
        """Read the reviewed ranges back without issuing another write.

        This method is deliberately separate from ``apply_patch`` so an
        interrupted edit can be reconciled later from its durable checkpoint.
        Reconciliation must never repeat ``batchUpdate``.
        """

        data = [
            {"range": f"'{patch.sheet_title}'!{patch.range_a1}"}
            for patch in spec.patches
        ]
        values = self.service.spreadsheets().values()
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
