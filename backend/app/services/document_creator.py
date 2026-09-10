"""Typed Google Docs executor; no model calls and no automatic write retries.

The caller owns approval/idempotency. Save the returned document ID immediately
via ``on_created`` so a later formatting failure does not hide the created file.
Google indexes text in UTF-16 units, not Python characters (emoji use two units).
"""

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.tools.contracts import ToolError


class DocumentBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=10000)
    style: Literal["NORMAL_TEXT", "HEADING_1", "HEADING_2", "HEADING_3"] = "NORMAL_TEXT"

    @field_validator("text")
    @classmethod
    def safe_text(cls, value: str) -> str:
        # Docs silently removes some controls; reject them before verification differs.
        if any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("Control characters are not supported")
        return value


class DocumentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    blocks: list[DocumentBlock] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def bounded(self):
        DocumentBlock.safe_text(self.title)
        if sum(len(block.text) for block in self.blocks) > 100000:
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


def create_requests(spec: DocumentSpec) -> tuple[str, list[dict]]:
    paragraphs = [(spec.title, "TITLE")] + [(b.text, b.style) for b in spec.blocks]
    text = "".join(value + "\n" for value, _ in paragraphs)
    requests = [{"insertText": {"location": {"index": 1}, "text": text}}]
    index = 1
    for value, style in paragraphs:
        end = index + utf16_length(value + "\n")
        requests.append(
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": index, "endIndex": end},
                    "paragraphStyle": {"namedStyleType": style},
                    "fields": "namedStyleType",
                }
            }
        )
        index = end
    return text, requests


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


class DocumentCreator:
    def __init__(self, service):
        self.documents = service.documents()

    def read(self, document_id: str) -> dict:
        return self.documents.get(documentId=document_id, includeTabsContent=True).execute(
            num_retries=0
        )

    def create(self, spec: DocumentSpec, on_created: Callable[[str], None]) -> dict:
        expected, requests = create_requests(spec)
        created = self.documents.create(body={"title": spec.title}).execute(num_retries=0)
        document_id = created["documentId"]
        on_created(document_id)
        self.documents.batchUpdate(documentId=document_id, body={"requests": requests}).execute(
            num_retries=0
        )
        actual = self.read(document_id)
        tab_id, elements = document_tab(actual)
        # A blank Google Doc already has its terminal paragraph newline.
        if plain_body(elements) != expected + "\n" or actual.get("title") != spec.title:
            raise ToolError(
                "Đã tạo tài liệu nhưng nội dung chưa qua kiểm tra.", code="verification_failed"
            )
        return {
            "document_id": document_id,
            "tab_id": tab_id,
            "verified": True,
            "url": f"https://docs.google.com/document/d/{document_id}/edit",
        }

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
