"""Typed Google Docs executor; no model calls and no automatic write retries.

The caller owns approval/idempotency. Save the returned document ID immediately
via ``on_created`` so a later formatting failure does not hide the created file.
Google indexes text in UTF-16 units, not Python characters (emoji use two units).
"""

import secrets
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.tools.contracts import ToolError


class DocumentBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["paragraph", "table"] = "paragraph"
    text: str | None = Field(default=None, max_length=10000)
    rows: list[list[str]] | None = Field(default=None, max_length=50)
    style: Literal["NORMAL_TEXT", "HEADING_1", "HEADING_2", "HEADING_3"] = "NORMAL_TEXT"
    list_style: Literal["none", "bullet", "numbered"] = "none"

    @field_validator("text")
    @classmethod
    def safe_text(cls, value: str | None) -> str | None:
        # Docs silently removes some controls; reject them before verification differs.
        if value is None:
            return value
        if any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("Control characters are not supported")
        return value

    @model_validator(mode="after")
    def validate_kind(self):
        if self.kind == "paragraph":
            if not self.text:
                raise ValueError("Paragraph blocks require text")
            if self.rows is not None:
                raise ValueError("Paragraph blocks cannot contain table rows")
            return self
        if self.text is not None:
            raise ValueError("Table blocks cannot contain paragraph text")
        if not self.rows:
            raise ValueError("Table blocks require at least one row")
        columns = len(self.rows[0])
        if not 1 <= columns <= 10:
            raise ValueError("Tables must contain between 1 and 10 columns")
        if any(len(row) != columns for row in self.rows):
            raise ValueError("All table rows must have the same number of cells")
        if self.style != "NORMAL_TEXT" or self.list_style != "none":
            raise ValueError("Table blocks cannot use paragraph or list styles")
        total = 0
        for row in self.rows:
            for cell in row:
                if len(cell) > 2500:
                    raise ValueError("Table cells cannot exceed 2,500 characters")
                self.safe_text(cell)
                total += len(cell)
        if total > 50000:
            raise ValueError("A table cannot exceed 50,000 characters")
        return self


class DocumentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    theme: Literal["editorial", "study", "business"] = "editorial"
    blocks: list[DocumentBlock] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def bounded(self):
        DocumentBlock.safe_text(self.title)
        total = len(self.title)
        table_count = 0
        table_cells = 0
        for block in self.blocks:
            total += len(block.text or "")
            if block.kind == "table" and block.rows is not None:
                table_count += 1
                table_cells += sum(len(row) for row in block.rows)
                total += sum(len(cell) for row in block.rows for cell in row)
        if table_count > 8:
            raise ValueError("A document cannot contain more than 8 tables")
        if table_cells > 300:
            raise ValueError("A document cannot contain more than 300 table cells")
        if total > 100000:
            raise ValueError("Document exceeds 100,000 characters")
        return self


class DocumentPatchSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,200}$")
    tab_id: str = Field(min_length=1, max_length=200)
    revision_id: str = Field(min_length=1, max_length=500)
    old_text: str = Field(min_length=1, max_length=30000)
    new_text: str = Field(max_length=30000)

    @field_validator("old_text", "new_text")
    @classmethod
    def safe_text(cls, value: str) -> str:
        return DocumentBlock.safe_text(value)


def utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


DOCUMENT_THEMES = {
    "editorial": {"accent": {"red": 0.12, "green": 0.24, "blue": 0.42}},
    "study": {"accent": {"red": 0.05, "green": 0.34, "blue": 0.31}},
    "business": {"accent": {"red": 0.11, "green": 0.11, "blue": 0.13}},
}


def _build_document_plan(spec: DocumentSpec) -> dict:
    # The title is authored once as the native TITLE paragraph. A model may
    # echo it as the first body block; suppress that duplicate in the export.
    content_blocks = spec.blocks
    if (
        content_blocks
        and content_blocks[0].kind == "paragraph"
        and content_blocks[0].text
        and content_blocks[0].text.strip() == spec.title.strip()
    ):
        content_blocks = content_blocks[1:]

    entries: list[tuple[str, str, str, list[list[str]] | None]] = [
        (spec.title, "TITLE", "none", None)
    ]
    tables: list[dict] = []
    expected_content = [
        {"kind": "paragraph", "text": line}
        for line in spec.title.split("\n")
        if line
    ]
    for block in content_blocks:
        if block.kind == "table":
            marker = f"__DRIVEAGENT_TABLE_{secrets.token_hex(12)}__"
            user_text = [spec.title, *(candidate.text or "" for candidate in content_blocks)]
            user_text.extend(
                cell
                for candidate in content_blocks
                for row in (candidate.rows or [])
                for cell in row
            )
            while any(marker in value for value in user_text):
                marker = f"__DRIVEAGENT_TABLE_{secrets.token_hex(12)}__"
            entries.append((marker, "NORMAL_TEXT", "none", block.rows))
            expected_content.append(
                {"kind": "table", "rows": [row.copy() for row in block.rows or []]}
            )
        else:
            value = block.text or ""
            entries.append((value, block.style, block.list_style, None))
            expected_content.extend(
                {"kind": "paragraph", "text": line}
                for line in value.split("\n")
                if line
            )

    text = "".join(value + "\n" for value, _, _, _ in entries)
    requests = [
        {"insertText": {"location": {"index": 1}, "text": text}},
        {
            "updateDocumentStyle": {
                "documentStyle": {
                    "marginTop": {"magnitude": 54, "unit": "PT"},
                    "marginBottom": {"magnitude": 54, "unit": "PT"},
                    "marginLeft": {"magnitude": 64, "unit": "PT"},
                    "marginRight": {"magnitude": 64, "unit": "PT"},
                },
                "fields": "marginTop,marginBottom,marginLeft,marginRight",
            }
        },
    ]
    accent = DOCUMENT_THEMES[spec.theme]["accent"]
    index = 1
    for value, style, list_style, table_rows in entries:
        end = index + utf16_length(value + "\n")
        is_title = style == "TITLE"
        requests.append(
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": index, "endIndex": end},
                    "paragraphStyle": {
                        "namedStyleType": style,
                        "lineSpacing": 108 if is_title else 118,
                        "spaceBelow": {
                            "magnitude": 16 if is_title else 7,
                            "unit": "PT",
                        },
                    },
                    "fields": "namedStyleType,lineSpacing,spaceBelow",
                }
            }
        )
        size = {"TITLE": 25, "HEADING_1": 18, "HEADING_2": 15, "HEADING_3": 12}.get(
            style, 11
        )
        requests.append(
            {
                "updateTextStyle": {
                    "range": {"startIndex": index, "endIndex": end - 1},
                    "textStyle": {
                        "weightedFontFamily": {
                            "fontFamily": "Arial",
                            "weight": 700 if style != "NORMAL_TEXT" else 400,
                        },
                        "fontSize": {"magnitude": size, "unit": "PT"},
                        "bold": style != "NORMAL_TEXT",
                        "foregroundColor": {
                            "color": {
                                "rgbColor": (
                                    accent
                                    if style != "NORMAL_TEXT"
                                    else {"red": 0.13, "green": 0.14, "blue": 0.16}
                                )
                            }
                        },
                    },
                    "fields": "weightedFontFamily,fontSize,bold,foregroundColor",
                }
            }
        )
        if list_style != "none":
            requests.append(
                {
                    "createParagraphBullets": {
                        "range": {"startIndex": index, "endIndex": end},
                        "bulletPreset": (
                            "BULLET_DISC_CIRCLE_SQUARE"
                            if list_style == "bullet"
                            else "NUMBERED_DECIMAL_ALPHA_ROMAN"
                        ),
                    }
                }
            )
        if table_rows is not None:
            tables.append(
                {
                    "marker": value,
                    "index": index,
                    "rows": table_rows,
                }
            )
        index = end
    return {
        "text": text,
        "requests": requests,
        "tables": tables,
        "expected_content": expected_content,
        "accent": accent,
    }


def create_requests(spec: DocumentSpec) -> tuple[str, list[dict]]:
    plan = _build_document_plan(spec)
    return plan["text"], plan["requests"]


def document_tab(document: dict, tab_id: str | None = None) -> tuple[str, list[dict]]:
    def flatten(tabs):
        for tab in tabs:
            yield tab
            yield from flatten(tab.get("childTabs", []))

    tabs = list(flatten(document.get("tabs", [])))
    selected = [tab for tab in tabs if tab_id is None or tab["tabProperties"]["tabId"] == tab_id]
    if len(selected) != 1:
        raise ToolError("Hãy chọn đúng một tab tài liệu.", code="document_tab_required")
    tab = selected[0]
    return tab["tabProperties"]["tabId"], tab["documentTab"]["body"]["content"]


def plain_body(elements: list[dict]) -> str:
    """Only contiguous paragraph text is patchable; tables/images need another editor."""
    text = ""
    for item in elements:
        if "sectionBreak" in item and item.get("startIndex", 0) == 0:
            continue
        paragraph = item.get("paragraph")
        if paragraph is None or item.get("startIndex") != 1 + utf16_length(text):
            raise ToolError(
                "Chỉ hỗ trợ chỉnh đoạn văn liên tục, chưa hỗ trợ bảng/ảnh.",
                code="unsupported_document_structure",
            )
        for part in paragraph.get("elements", []):
            if "textRun" not in part:
                raise ToolError(
                    "Đoạn chọn có thành phần không phải văn bản.",
                    code="unsupported_document_structure",
                )
            text += part["textRun"]["content"]
    return text


def _paragraph_text(paragraph: dict) -> str:
    text = ""
    for part in paragraph.get("elements", []):
        if "textRun" not in part:
            raise ToolError(
                "Tài liệu có thành phần không phải văn bản.",
                code="unsupported_document_structure",
            )
        text += part["textRun"].get("content", "")
    return text


def _table_shape(table: dict) -> tuple[int, int]:
    rows = table.get("tableRows", [])
    return len(rows), max((len(row.get("tableCells", [])) for row in rows), default=0)


def _find_inserted_table(
    elements: list[dict], start_index: int, expected_rows: int, expected_columns: int
) -> dict:
    candidates = [
        item
        for item in elements
        if "table" in item
        and start_index <= item.get("startIndex", -1) <= start_index + 1
        and _table_shape(item["table"]) == (expected_rows, expected_columns)
    ]
    if len(candidates) != 1:
        raise ToolError(
            "Đã tạo tài liệu nhưng chưa xác định được bảng vừa chèn.",
            code="verification_failed",
        )
    return candidates[0]


def _table_cell_insert_requests(table: dict, rows: list[list[str]], tab_id: str) -> list[dict]:
    table_rows = table.get("tableRows", [])
    if len(table_rows) != len(rows):
        raise ToolError("Số hàng của bảng không khớp bản duyệt.", code="verification_failed")
    insertions = []
    for row_index, row in enumerate(rows):
        cells = table_rows[row_index].get("tableCells", [])
        if len(cells) != len(row):
            raise ToolError("Số cột của bảng không khớp bản duyệt.", code="verification_failed")
        for column_index, value in enumerate(row):
            if not value:
                continue
            paragraph_elements = [
                item
                for item in cells[column_index].get("content", [])
                if item.get("paragraph") is not None
            ]
            if len(paragraph_elements) != 1 or "startIndex" not in paragraph_elements[0]:
                raise ToolError(
                    "Không xác định được vị trí ô trong bảng.", code="verification_failed"
                )
            start_index = paragraph_elements[0]["startIndex"]
            insertions.append(
                {
                    "index": start_index,
                    "request": {
                        "insertText": {
                            "location": {
                                "index": start_index,
                                "tabId": tab_id,
                            },
                            "text": value,
                        }
                    },
                }
            )
    # Inserting from the end keeps all not-yet-used UTF-16 indexes stable.
    return [
        item["request"]
        for item in sorted(insertions, key=lambda item: item["index"], reverse=True)
    ]


def _extract_document_content(elements: list[dict]) -> list[dict]:
    extracted = []
    for item in elements:
        if "sectionBreak" in item:
            continue
        paragraph = item.get("paragraph")
        if paragraph is not None:
            text = _paragraph_text(paragraph).removesuffix("\n")
            extracted.extend(
                {"kind": "paragraph", "text": line} for line in text.split("\n") if line
            )
            continue
        table = item.get("table")
        if table is None:
            raise ToolError(
                "Tài liệu có cấu trúc chưa được hỗ trợ.", code="unsupported_document_structure"
            )
        rows = []
        for row in table.get("tableRows", []):
            values = []
            for cell in row.get("tableCells", []):
                paragraphs = [
                    content.get("paragraph")
                    for content in cell.get("content", [])
                    if content.get("paragraph") is not None
                ]
                if not paragraphs:
                    raise ToolError(
                        "Không đọc lại được nội dung ô bảng.", code="verification_failed"
                    )
                value = "".join(_paragraph_text(part) for part in paragraphs).removesuffix("\n")
                values.append(value)
            rows.append(values)
        extracted.append({"kind": "table", "rows": rows})
    return extracted


class DocumentCreator:
    def __init__(self, service):
        self.documents = service.documents()

    def read(self, document_id: str) -> dict:
        return self.documents.get(documentId=document_id, includeTabsContent=True).execute(
            num_retries=0
        )

    def create(self, spec: DocumentSpec, on_created: Callable[[str], None]) -> dict:
        plan = _build_document_plan(spec)
        created = self.documents.create(body={"title": spec.title}).execute(num_retries=0)
        document_id = created["documentId"]
        on_created(document_id)
        self.documents.batchUpdate(
            documentId=document_id, body={"requests": plan["requests"]}
        ).execute(num_retries=0)

        # Docs API requires a read between inserting each table and inserting
        # cell text so that cell indexes are based on the server's actual structure.
        # Process placeholders from the end so earlier UTF-16 indexes do not move.
        for table in reversed(plan["tables"]):
            rows = table["rows"]
            columns = len(rows[0])
            insert_table_requests = [
                {
                    "deleteContentRange": {
                        "range": {
                            "startIndex": table["index"],
                            "endIndex": table["index"] + utf16_length(table["marker"]),
                        }
                    }
                },
                {
                    "insertTable": {
                        "rows": len(rows),
                        "columns": columns,
                        "location": {"index": table["index"]},
                    }
                },
            ]
            self.documents.batchUpdate(
                documentId=document_id, body={"requests": insert_table_requests}
            ).execute(num_retries=0)
            partial = self.read(document_id)
            tab_id, elements = document_tab(partial)
            inserted_table = _find_inserted_table(
                elements, table["index"], len(rows), columns
            )
            cell_requests = _table_cell_insert_requests(inserted_table["table"], rows, tab_id)
            if cell_requests:
                self.documents.batchUpdate(
                    documentId=document_id, body={"requests": cell_requests}
                ).execute(num_retries=0)

        tab_id = self.verify_created(document_id, spec)
        return {
            "document_id": document_id,
            "tab_id": tab_id,
            "verified": True,
            "url": f"https://docs.google.com/document/d/{document_id}/edit",
        }

    def verify_created(self, document_id: str, spec: DocumentSpec) -> str:
        """Read back a created document and compare its semantic block topology."""

        actual = self.read(document_id)
        tab_id, elements = document_tab(actual)
        expected = _build_document_plan(spec)["expected_content"]
        if _extract_document_content(elements) != expected or actual.get("title") != spec.title:
            raise ToolError(
                "Nội dung Google Docs không khớp bản đã duyệt.", code="verification_failed"
            )
        return tab_id

    def verify_patch_applied(self, spec: DocumentPatchSpec) -> None:
        """Verify an uncertain patch without repeating the write."""

        _, elements = document_tab(self.read(spec.document_id), spec.tab_id)
        actual = plain_body(elements)
        if spec.old_text and spec.old_text != spec.new_text and spec.old_text in actual:
            raise ToolError("Đoạn cũ vẫn còn trong tài liệu.", code="verification_failed")
        if spec.new_text and actual.count(spec.new_text) != 1:
            raise ToolError("Đoạn mới không khớp duy nhất một lần.", code="verification_failed")

    def preview_patch(self, spec: DocumentPatchSpec) -> tuple[str, list[dict]]:
        actual = self.read(spec.document_id)
        if actual.get("revisionId") != spec.revision_id:
            raise ToolError(
                "Tài liệu đã thay đổi; cần xem lại bản sửa trước khi xác nhận.",
                code="revision_conflict",
            )
        _, elements = document_tab(actual, spec.tab_id)
        original = plain_body(elements)
        if original.count(spec.old_text) != 1:
            raise ToolError("Đoạn cần sửa phải khớp chính xác một lần.", code="ambiguous_patch")
        position = original.index(spec.old_text)
        end = position + len(spec.old_text)
        # Never remove the document's required terminal newline.
        if end >= len(original):
            raise ToolError("Không được xóa ký tự kết thúc tài liệu.", code="invalid_patch")
        start_index = 1 + utf16_length(original[:position])
        requests = [
            {
                "deleteContentRange": {
                    "range": {
                        "tabId": spec.tab_id,
                        "startIndex": start_index,
                        "endIndex": start_index + utf16_length(spec.old_text),
                    }
                }
            }
        ]
        if spec.new_text:
            requests.append(
                {
                    "insertText": {
                        "location": {
                            "tabId": spec.tab_id,
                            "index": start_index,
                        },
                        "text": spec.new_text,
                    }
                }
            )
        return original[:position] + spec.new_text + original[end:], requests

    def apply_patch(self, spec: DocumentPatchSpec) -> dict:
        expected, requests = self.preview_patch(spec)
        self.documents.batchUpdate(
            documentId=spec.document_id,
            body={
                "requests": requests,
                "writeControl": {"requiredRevisionId": spec.revision_id},
            },
        ).execute(num_retries=0)
        _, elements = document_tab(self.read(spec.document_id), spec.tab_id)
        if plain_body(elements) != expected:
            raise ToolError(
                "Đã gửi bản sửa nhưng chưa xác minh được nội dung cuối cùng.",
                code="verification_failed",
            )
        return {
            "document_id": spec.document_id,
            "verified": True,
            "url": f"https://docs.google.com/document/d/{spec.document_id}/edit",
        }
