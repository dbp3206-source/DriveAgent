import json
from pathlib import Path

import openpyxl
import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from app.core.config import Settings
from app.db.models import LocalSource, User
from app.services.local_sources import (
    LocalReadInput,
    LocalSearchInput,
    extract_text,
    hash_content,
    read_local,
    search_local,
)
from app.tools.contracts import ToolContext, ToolError
from app.tools.drive import (
    _convert_bytes,
    _download_request,
    _parse_spreadsheet_to_dossier,
)
from app.tools.google_errors import workspace_http_error


def test_local_text_and_notebook_imports_are_deterministic() -> None:
    assert extract_text("notes.md", b"\xef\xbb\xbf# Ghi chu") == "# Ghi chu"
    assert extract_text("rows.csv", b"a,b\n1,2") == "a,b\n1,2"
    notebook = {"cells": [{"source": ["# Heading\n"]}, {"source": "print(1)"}]}
    assert "# Heading" in extract_text("lesson.ipynb", json.dumps(notebook).encode())
    assert hash_content("same") == hash_content("same")


def test_local_import_validates_notebook_cells_and_csv_shape() -> None:
    with pytest.raises(ToolError, match="CSV") as csv_error:
        extract_text("wide.csv", b",".join(b"x" for _ in range(101)))
    assert csv_error.value.code == "table_too_large"
    with pytest.raises(ToolError):
        extract_text("bad.ipynb", json.dumps({"cells": ["not a cell"]}).encode())
    with pytest.raises(ToolError):
        extract_text("bad.ipynb", json.dumps({"cells": [{"source": 7}]}).encode())


@pytest.mark.parametrize(
    ("name", "payload", "code"),
    [
        ("archive.zip", b"x", "unsupported_type"),
        ("empty.txt", b"  \n", "empty_document"),
        ("binary.txt", b"a\x00b", "invalid_document"),
    ],
)
def test_local_import_rejects_unsafe_or_empty_inputs(
    name: str, payload: bytes, code: str
) -> None:
    with pytest.raises(ToolError) as exc_info:
        extract_text(name, payload)
    assert exc_info.value.code == code


@pytest.mark.asyncio
async def test_local_search_and_read_return_scoped_citations() -> None:
    user = User(id="user-1", email="qa@example.com", display_name="QA")
    row = LocalSource(
        id="source-1",
        user_id=user.id,
        name="study.md",
        content="Mã kiểm thử DA-LOCAL-2026 và ngày họp là thứ Sáu.",
        content_hash=hash_content("Mã kiểm thử DA-LOCAL-2026 và ngày họp là thứ Sáu."),
    )

    class FakeDB:
        async def scalars(self, _query):
            return [row]

        async def scalar(self, _query):
            return row

    context = ToolContext(
        request_id="local-qa",
        user=user,
        db=FakeDB(),  # type: ignore[arg-type]
        settings=Settings(),
    )
    found = await search_local(LocalSearchInput(query="DA-LOCAL-2026"), context)
    read = await read_local(LocalReadInput(source_id="local:source-1"), context)

    assert found.data["search_type"] == "keyword_and_content"
    assert found.data["sources"][0]["name"] == "study.md"
    assert read.data["citations"][0]["file_id"] == "local:source-1"
    assert read.data["text"].startswith("Mã kiểm thử")


@pytest.mark.asyncio
async def test_local_search_falls_back_to_recent_sources_for_stop_words() -> None:
    user = User(id="user-2", email="qa2@example.com", display_name="QA 2")
    row = LocalSource(
        id="source-2",
        user_id=user.id,
        name="recent.md",
        content="x" * 120 + " nội dung gần đây " + "y" * 240,
        content_hash=hash_content("x" * 120 + " nội dung gần đây " + "y" * 240),
    )

    class FallbackDB:
        def __init__(self) -> None:
            self.calls = 0

        async def scalars(self, _query):
            self.calls += 1
            return [] if self.calls == 1 else [row]

    context = ToolContext(
        request_id="local-fallback",
        user=user,
        db=FallbackDB(),  # type: ignore[arg-type]
        settings=Settings(),
    )
    result = await search_local(LocalSearchInput(query="file"), context)

    assert result.data["search_type"] == "recent_sources"
    assert result.data["sources"][0]["snippet"].endswith("…")


@pytest.mark.asyncio
async def test_local_search_does_not_substitute_recent_file_for_specific_miss() -> None:
    user = User(id="user-specific", email="qa-specific@example.com", display_name="QA")

    class EmptyDB:
        def __init__(self) -> None:
            self.calls = 0

        async def scalars(self, _query):
            self.calls += 1
            return []

    db = EmptyDB()
    context = ToolContext(
        request_id="local-specific-miss",
        user=user,
        db=db,  # type: ignore[arg-type]
        settings=Settings(),
    )
    result = await search_local(LocalSearchInput(query="LOCAL-STUDY-2026"), context)

    assert result.data["sources"] == []
    assert db.calls == 1


@pytest.mark.asyncio
async def test_local_search_extracts_a_token_match_when_query_is_not_literal() -> None:
    user = User(id="user-3", email="qa3@example.com", display_name="QA 3")
    row = LocalSource(
        id="source-3",
        user_id=user.id,
        name="token.md",
        content="Đây là nội dung có mã kiểm thử.",
        content_hash=hash_content("Đây là nội dung có mã kiểm thử."),
    )

    class TokenDB:
        async def scalars(self, _query):
            return [row]

    context = ToolContext(
        request_id="local-token",
        user=user,
        db=TokenDB(),  # type: ignore[arg-type]
        settings=Settings(),
    )
    result = await search_local(LocalSearchInput(query="mã khác"), context)

    assert "mã kiểm thử" in result.data["sources"][0]["snippet"].casefold()


@pytest.mark.asyncio
async def test_local_read_reports_missing_source() -> None:
    user = User(id="user-4", email="qa4@example.com", display_name="QA 4")

    class EmptyDB:
        async def scalar(self, _query):
            return None

    context = ToolContext(
        request_id="local-missing",
        user=user,
        db=EmptyDB(),  # type: ignore[arg-type]
        settings=Settings(),
    )
    with pytest.raises(ToolError) as exc_info:
        await read_local(LocalReadInput(source_id="missing"), context)
    assert exc_info.value.code == "source_not_found"


def test_excel_dossier_contains_structure_preview_and_empty_tab(tmp_path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Chi phí"
    sheet.append([f"Cột {index}" for index in range(1, 15)])
    sheet.append(list(range(1, 15)))
    workbook.create_sheet("Trống")
    path = tmp_path / "budget.xlsx"
    workbook.save(path)

    dossier = _parse_spreadsheet_to_dossier(path, "budget.xlsx")

    assert "# 📊 Hồ sơ Tài liệu: budget.xlsx" in dossier
    assert "Chi phí" in dossier
    assert "Đã ẩn bớt" not in dossier
    assert "Cột 14" in dossier
    assert "| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |" in dossier
    assert "Trống" in dossier


def test_drive_conversion_handles_text_and_notebook() -> None:
    assert _convert_bytes(b"hello", "text/plain", "hello.txt") == "hello"
    notebook = b'{"cells":[{"cell_type":"markdown","source":["# A"]}]}'
    assert _convert_bytes(notebook, "application/octet-stream", "a.ipynb") == "# A"


def test_download_request_uses_export_and_rejects_workspace_type() -> None:
    class Files:
        def export_media(self, **kwargs):
            return ("export", kwargs)

        def get_media(self, **kwargs):
            return ("download", kwargs)

    class Service:
        def files(self):
            return Files()

    assert _download_request(
        Service(),
        {"id": "doc-1", "mimeType": "application/vnd.google-apps.document"},
    )[0] == "export"
    assert _download_request(Service(), {"id": "file-1", "mimeType": "text/plain"})[0] == "download"
    with pytest.raises(ToolError):
        _download_request(
            Service(),
            {"id": "form-1", "mimeType": "application/vnd.google-apps.form"},
        )


@pytest.mark.parametrize(
    ("status", "body", "code"),
    [
        (403, b"accessNotConfigured", "drive_api_disabled"),
        (403, b"forbidden", "google_workspace_permission_denied"),
        (429, b"slow down", "google_workspace_rate_limited"),
        (500, b"server", "google_workspace_error"),
    ],
)
def test_google_workspace_errors_are_actionable(
    status: int, body: bytes, code: str
) -> None:
    response = Response({"status": str(status)})
    response.reason = "test"
    error = workspace_http_error(HttpError(response, body), "Drive")
    assert error.code == code
    assert "token" not in str(error).casefold()
