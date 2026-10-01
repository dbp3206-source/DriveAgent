from io import BytesIO
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from app.core.config import Settings
from app.db.models import User
from app.tools.contracts import ToolContext
from app.tools.drive import (
    ListDriveFilesInput,
    ReadDriveFileInput,
    SearchDriveFilesInput,
    _convert_bytes,
    _escape_drive_query,
    _extension_for,
    _google_sheet_markdown,
    is_supported_drive_file,
    list_drive_files,
    read_drive_file,
    search_drive_files,
)


def test_drive_query_escaping_prevents_broken_query() -> None:
    assert _escape_drive_query("Bao's \\ plan") == "Bao\\'s \\\\ plan"


def test_known_extensions_are_preserved_for_conversion() -> None:
    assert _extension_for("application/pdf") == ".pdf"
    assert _extension_for("text/csv") == ".csv"
    assert _extension_for("application/octet-stream") == ".bin"


def test_excel_conversion_closes_read_only_workbook_before_temp_cleanup() -> None:
    workbook = Workbook()
    workbook.active.append(["Cột 1", "Cột 2"])
    workbook.active.append([1, 2])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()

    text = _convert_bytes(
        buffer.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "qa.xlsx",
    )

    assert "Cột 2" in text
    assert "| 1 | 2 |" in text


def test_google_sheet_reader_preserves_tabs_columns_and_cells() -> None:
    class Request:
        def __init__(self, payload):
            self.payload = payload

        def execute(self):
            return self.payload

    class Spreadsheets:
        def values(self):
            return self

        def get(self, **kwargs):  # type: ignore[no-redef]
            if "range" not in kwargs:
                return Request(
                    {
                        "properties": {"title": "Chi tiêu"},
                        "sheets": [
                            {"properties": {"title": "Tháng 9"}},
                            {"properties": {"title": "Ghi chú"}},
                        ],
                    }
                )
            rows = (
                [["Mục", "Số tiền"], ["Sách", 120], ["Xe buýt", 30]]
                if "Tháng 9" in kwargs["range"]
                else [["Nội dung"], ["Giữ nguyên | ký tự"]]
            )
            return Request({"values": rows})

    class Service:
        def spreadsheets(self):
            return Spreadsheets()

    result = _google_sheet_markdown(Service(), "sheet-id")

    assert "# Chi tiêu" in result
    assert "## Tháng 9" in result
    assert "| Mục | Số tiền |" in result
    assert "| Sách | 120 |" in result
    assert "Giữ nguyên \\| ký tự" in result


def test_native_sheet_keeps_moderate_width_values_needed_for_totals() -> None:
    class Request:
        def __init__(self, payload):
            self.payload = payload

        def execute(self):
            return self.payload

    class Spreadsheets:
        def values(self):
            return self

        def get(self, **kwargs):
            if "range" not in kwargs:
                return Request(
                    {
                        "properties": {"title": "QA"},
                        "sheets": [{"properties": {"title": "Chi phí"}}],
                    }
                )
            return Request(
                {"values": [[f"Cột {i}" for i in range(1, 15)], list(range(1, 15))]}
            )

    class Service:
        def spreadsheets(self):
            return Spreadsheets()

    result = _google_sheet_markdown(Service(), "qa-sheet")

    assert "Cột 14" in result
    assert "| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |" in result
    assert "rút gọn" not in result


@pytest.mark.parametrize(
    "mime_type,file_name",
    [
        ("application/vnd.google-apps.document", "Kế hoạch"),
        ("application/pdf", "report.pdf"),
        ("text/markdown", "notes.md"),
        ("application/octet-stream", "agent.ipynb"),
    ],
)
def test_supported_drive_file_contract_accepts_extractable_formats(
    mime_type: str, file_name: str
) -> None:
    assert is_supported_drive_file(mime_type, file_name) is True


@pytest.mark.parametrize(
    "mime_type,file_name",
    [
        ("video/mp4", "lecture.mp4"),
        ("application/zip", "archive.zip"),
        ("application/octet-stream", "unknown.bin"),
    ],
)
def test_supported_drive_file_contract_rejects_non_document_formats(
    mime_type: str, file_name: str
) -> None:
    assert is_supported_drive_file(mime_type, file_name) is False


def test_notebook_conversion_keeps_sources_and_drops_outputs() -> None:
    notebook = b"""{
      "cells": [
        {"cell_type": "markdown", "source": ["# State, Nodes, Edges"]},
        {"cell_type": "code", "source": ["print('ok')"],
         "outputs": [{"data": {"image/png": "BASE64_SHOULD_NOT_BE_INDEXED"}}]}
      ]
    }"""

    result = _convert_bytes(notebook, "application/octet-stream", "agent.ipynb")

    assert "State, Nodes, Edges" in result
    assert "print('ok')" in result
    assert "BASE64_SHOULD_NOT_BE_INDEXED" not in result


class FakeRequest:
    def __init__(self, response):  # type: ignore[no-untyped-def]
        self.response = response

    def execute(self):  # type: ignore[no-untyped-def]
        return self.response


class FakeFiles:
    def __init__(self):
        self.list_calls: list[dict] = []

    def list(self, **kwargs):  # type: ignore[no-untyped-def]
        self.list_calls.append(kwargs)
        return FakeRequest(
            {
                "files": [
                    {
                        "id": "file-123",
                        "name": "Kế hoạch quý",
                        "mimeType": "text/plain",
                        "owners": [{"displayName": "Bao"}],
                    }
                ],
                "nextPageToken": "next-page",
            }
        )

    def get(self, **_kwargs):  # type: ignore[no-untyped-def]
        return FakeRequest(
            {
                "id": "file-123",
                "name": "ghi-chu.txt",
                "mimeType": "text/plain",
                "size": "17",
                "owners": [],
            }
        )

    def get_media(self, **_kwargs):  # type: ignore[no-untyped-def]
        return object()


class FakeService:
    def __init__(self):
        self.files_resource = FakeFiles()

    def files(self) -> FakeFiles:
        return self.files_resource


def tool_context() -> ToolContext:
    return ToolContext(
        request_id="drive-test",
        user=User(email="drive@example.com", display_name="Drive"),
        db=SimpleNamespace(),  # type: ignore[arg-type]
        settings=Settings(),
    )


@pytest.mark.asyncio
async def test_drive_list_and_search_build_expected_queries(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    service = FakeService()

    async def fake_service(_context):  # type: ignore[no-untyped-def]
        return service

    monkeypatch.setattr("app.tools.drive._drive_service", fake_service)
    listed = await list_drive_files(
        ListDriveFilesInput(folder_id="folder-1", page_size=25), tool_context()
    )
    searched = await search_drive_files(
        SearchDriveFilesInput(query="Bao's plan", mime_type="text/plain"), tool_context()
    )

    assert listed.files[0].id == "file-123"
    assert listed.next_page_token == "next-page"
    assert searched.files[0].name == "Kế hoạch quý"
    assert "'folder-1' in parents" in service.files_resource.list_calls[0]["q"]
    assert "name contains 'Bao\\'s plan'" in service.files_resource.list_calls[1]["q"]
    assert "mimeType = 'text/plain'" in service.files_resource.list_calls[1]["q"]


@pytest.mark.asyncio
async def test_drive_read_downloads_and_returns_text(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    service = FakeService()

    async def fake_service(_context):  # type: ignore[no-untyped-def]
        return service

    class FakeDownloader:
        def __init__(self, buffer, _request, chunksize):  # type: ignore[no-untyped-def]
            self.buffer = buffer
            self.chunksize = chunksize

        def next_chunk(self):  # type: ignore[no-untyped-def]
            self.buffer.write("Nội dung Drive".encode())
            return None, True

    monkeypatch.setattr("app.tools.drive._drive_service", fake_service)
    monkeypatch.setattr("app.tools.drive.MediaIoBaseDownload", FakeDownloader)
    result = await read_drive_file(ReadDriveFileInput(file_id="file-123"), tool_context())

    assert result.file.name == "ghi-chu.txt"
    assert result.text == "Nội dung Drive"
    assert result.truncated is False
