from types import SimpleNamespace

import pytest

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
