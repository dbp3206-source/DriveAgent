"""Các tool Google Drive read-only bắt buộc của project."""

import asyncio
import io
import json
import tempfile
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from markitdown import MarkItDown
from pydantic import BaseModel, Field

from app.api.schemas import DriveFileListResponse, DriveFileResponse, FileContentResponse
from app.auth.google_oauth import refresh_and_store_if_needed
from app.auth.permissions import DRIVE_READ
from app.tools.contracts import ToolContext, ToolDefinition, ToolError

DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
GOOGLE_FOLDER = "application/vnd.google-apps.folder"
EXPORT_MIME_TYPES = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "application/pdf",
    "application/vnd.google-apps.drawing": "application/pdf",
}


class ListDriveFilesInput(BaseModel):
    page_size: int = Field(default=50, ge=1, le=100)
    page_token: str | None = None
    folder_id: str | None = None
    mime_type: str | None = None


class SearchDriveFilesInput(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    page_size: int = Field(default=50, ge=1, le=100)
    page_token: str | None = None
    mime_type: str | None = None


class ReadDriveFileInput(BaseModel):
    file_id: str = Field(min_length=3, max_length=300)
    max_characters: int = Field(default=120_000, ge=1_000, le=500_000)


def _escape_drive_query(value: str) -> str:
    """Escape backslash và dấu nháy theo cú pháp query của Google Drive."""

    return value.replace("\\", "\\\\").replace("'", "\\'")


def _file_response(item: dict[str, Any]) -> DriveFileResponse:
    return DriveFileResponse(
        id=item["id"],
        name=item.get("name", "Không tên"),
        mime_type=item.get("mimeType", "application/octet-stream"),
        modified_time=item.get("modifiedTime"),
        size=item.get("size"),
        web_view_link=item.get("webViewLink"),
        owners=[
            owner.get("displayName", owner.get("emailAddress", ""))
            for owner in item.get("owners", [])
        ],
    )


async def _drive_service(context: ToolContext):  # type: ignore[no-untyped-def]
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)
    return await asyncio.to_thread(
        build, "drive", "v3", credentials=credentials, cache_discovery=False
    )


def _translate_http_error(exc: HttpError) -> ToolError:
    status = getattr(exc.resp, "status", 500)
    retryable = status in {408, 429, 500, 502, 503, 504}
    return ToolError(
        f"Google Drive trả về HTTP {status}: {exc.reason}",
        code=f"google_drive_{status}",
        retryable=retryable,
    )


async def list_drive_files(
    payload: ListDriveFilesInput, context: ToolContext
) -> DriveFileListResponse:
    service = await _drive_service(context)
    clauses = ["trashed = false"]
    if payload.folder_id:
        clauses.append(f"'{_escape_drive_query(payload.folder_id)}' in parents")
    if payload.mime_type:
        clauses.append(f"mimeType = '{_escape_drive_query(payload.mime_type)}'")
    try:
        response = await asyncio.to_thread(
            service.files()
            .list(
                q=" and ".join(clauses),
                pageSize=payload.page_size,
                pageToken=payload.page_token,
                orderBy="modifiedTime desc",
                fields=(
                    "nextPageToken,files(id,name,mimeType,modifiedTime,size,webViewLink,owners)"
                ),
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute
        )
    except HttpError as exc:
        raise _translate_http_error(exc) from exc
    return DriveFileListResponse(
        files=[_file_response(item) for item in response.get("files", [])],
        next_page_token=response.get("nextPageToken"),
    )


async def search_drive_files(
    payload: SearchDriveFilesInput, context: ToolContext
) -> DriveFileListResponse:
    service = await _drive_service(context)
    escaped = _escape_drive_query(payload.query)
    clauses = ["trashed = false", f"(name contains '{escaped}' or fullText contains '{escaped}')"]
    if payload.mime_type:
        clauses.append(f"mimeType = '{_escape_drive_query(payload.mime_type)}'")
    try:
        response = await asyncio.to_thread(
            service.files()
            .list(
                q=" and ".join(clauses),
                pageSize=payload.page_size,
                pageToken=payload.page_token,
                orderBy="modifiedTime desc",
                fields=(
                    "nextPageToken,files(id,name,mimeType,modifiedTime,size,webViewLink,owners)"
                ),
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute
        )
    except HttpError as exc:
        raise _translate_http_error(exc) from exc
    return DriveFileListResponse(
        files=[_file_response(item) for item in response.get("files", [])],
        next_page_token=response.get("nextPageToken"),
    )


def _download_request(service, metadata: dict[str, Any]):  # type: ignore[no-untyped-def]
    mime_type = metadata["mimeType"]
    if mime_type in EXPORT_MIME_TYPES:
        return service.files().export_media(
            fileId=metadata["id"], mimeType=EXPORT_MIME_TYPES[mime_type]
        )
    if mime_type.startswith("application/vnd.google-apps"):
        raise ToolError(
            f"Chưa hỗ trợ đọc Google Workspace type {mime_type}.",
            code="unsupported_file_type",
        )
    return service.files().get_media(fileId=metadata["id"], supportsAllDrives=True)


def _extension_for(mime_type: str) -> str:
    mapping = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        "text/csv": ".csv",
        "text/plain": ".txt",
        "text/markdown": ".md",
        "text/html": ".html",
        "application/json": ".json",
    }
    return mapping.get(mime_type, ".bin")


def _extract_notebook(content: bytes) -> str:
    """Lấy source hữu ích từ notebook, không index output/base64 và metadata nhiễu."""

    try:
        notebook = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ToolError("Notebook không phải JSON hợp lệ.", code="conversion_failed") from exc
    sections: list[str] = []
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") not in {"markdown", "code"}:
            continue
        source = cell.get("source", "")
        text = "".join(source) if isinstance(source, list) else str(source)
        if text.strip():
            sections.append(text.strip())
    if not sections:
        raise ToolError("Notebook không có Markdown hoặc code để đọc.", code="conversion_failed")
    return "\n\n".join(sections)


def _convert_bytes(content: bytes, mime_type: str, file_name: str = "") -> str:
    if file_name.lower().endswith(".ipynb"):
        return _extract_notebook(content)
    if mime_type.startswith("text/") or mime_type == "application/json":
        return content.decode("utf-8", errors="replace")
    suffix = _extension_for(mime_type)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    try:
        result = MarkItDown().convert(str(temp_path))
        return result.text_content
    except Exception as exc:
        raise ToolError(
            f"Không thể chuyển đổi định dạng {mime_type}: {exc}",
            code="conversion_failed",
        ) from exc
    finally:
        temp_path.unlink(missing_ok=True)


async def read_drive_file(payload: ReadDriveFileInput, context: ToolContext) -> FileContentResponse:
    service = await _drive_service(context)
    try:
        metadata = await asyncio.to_thread(
            service.files()
            .get(
                fileId=payload.file_id,
                fields="id,name,mimeType,modifiedTime,size,webViewLink,owners",
                supportsAllDrives=True,
            )
            .execute
        )
        if metadata["mimeType"] == GOOGLE_FOLDER:
            raise ToolError("Thư mục không có nội dung để đọc.", code="folder_not_readable")
        declared_size = int(metadata.get("size", 0))
        maximum_bytes = context.settings.max_download_mb * 1024 * 1024
        if declared_size and declared_size > maximum_bytes:
            raise ToolError(
                f"Tệp lớn hơn giới hạn {context.settings.max_download_mb} MB.",
                code="file_too_large",
            )

        request = _download_request(service, metadata)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request, chunksize=1024 * 1024)
        done = False
        while not done:
            _status, done = await asyncio.to_thread(downloader.next_chunk)
            if buffer.tell() > maximum_bytes:
                raise ToolError(
                    f"Tệp vượt giới hạn {context.settings.max_download_mb} MB khi tải.",
                    code="file_too_large",
                )
        effective_mime = EXPORT_MIME_TYPES.get(metadata["mimeType"], metadata["mimeType"])
        text = await asyncio.to_thread(
            _convert_bytes, buffer.getvalue(), effective_mime, metadata.get("name", "")
        )
    except HttpError as exc:
        raise _translate_http_error(exc) from exc

    truncated = len(text) > payload.max_characters
    return FileContentResponse(
        file=_file_response(metadata),
        text=text[: payload.max_characters],
        truncated=truncated,
    )


def drive_tool_definitions() -> list[ToolDefinition]:
    common = {
        "required_permissions": {DRIVE_READ},
        "required_oauth_scopes": {DRIVE_READONLY_SCOPE},
        "rate_limit_per_minute": 60,
        "max_attempts": 3,
    }
    return [
        ToolDefinition(
            name="drive_list_files",
            description="Liệt kê các tệp Google Drive mà người dùng hiện tại có thể truy cập.",
            input_model=ListDriveFilesInput,
            output_model=DriveFileListResponse,
            handler=list_drive_files,
            **common,
        ),
        ToolDefinition(
            name="drive_search_files",
            description="Tìm tệp Google Drive theo tên hoặc nội dung full-text.",
            input_model=SearchDriveFilesInput,
            output_model=DriveFileListResponse,
            handler=search_drive_files,
            **common,
        ),
        ToolDefinition(
            name="drive_read_file",
            description="Đọc và chuyển nội dung một tệp Google Drive thành văn bản.",
            input_model=ReadDriveFileInput,
            output_model=FileContentResponse,
            handler=read_drive_file,
            **common,
        ),
    ]
