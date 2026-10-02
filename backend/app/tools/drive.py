"""Các tool Google Drive read-only bắt buộc của project."""

import asyncio
import hashlib
import io
import json
import tempfile
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from pydantic import BaseModel, Field

from app.api.schemas import DriveFileListResponse, DriveFileResponse, FileContentResponse
from app.auth.google_oauth import refresh_and_store_if_needed
from app.auth.permissions import DRIVE_READ
from app.tools.contracts import ToolContext, ToolDefinition, ToolError

DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
GOOGLE_FOLDER = "application/vnd.google-apps.folder"
GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
EXPORT_MIME_TYPES = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "application/pdf",
    "application/vnd.google-apps.drawing": "application/pdf",
}
SUPPORTED_BINARY_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/json",
}


def is_supported_drive_file(mime_type: str, file_name: str = "") -> bool:
    """Return whether the current extraction pipeline can read this file safely."""

    return (
        mime_type in EXPORT_MIME_TYPES
        or mime_type.startswith("text/")
        or mime_type in SUPPORTED_BINARY_MIME_TYPES
        or file_name.casefold().endswith(".ipynb")
    )


class ListDriveFilesInput(BaseModel):
    page_size: int = Field(default=50, ge=1, le=100)
    page_token: str | None = None
    folder_id: str | None = None
    mime_type: str | None = None
    exclude_folders: bool = False


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


async def drive_file_metadata(
    payload: ReadDriveFileInput, context: ToolContext
) -> DriveFileResponse:
    service = await _drive_service(context)
    try:
        item = await asyncio.to_thread(
            service.files()
            .get(
                fileId=payload.file_id,
                fields="id,name,mimeType,modifiedTime,webViewLink,trashed,capabilities(canDownload)",
                supportsAllDrives=True,
            )
            .execute
        )
    except HttpError as exc:
        raise _translate_http_error(exc) from exc
    if item.get("trashed") or item.get("capabilities", {}).get("canDownload") is False:
        raise ToolError(
            "Tài liệu đã bị xóa hoặc không còn quyền đọc nội dung.", code="source_unavailable"
        )
    return _file_response(item)


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
    if payload.exclude_folders:
        clauses.append(f"mimeType != '{GOOGLE_FOLDER}'")
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


def _markdown_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", "<br>")


def _parse_spreadsheet_to_dossier(file_path: Path, file_name: str) -> str:
    """Chuyển đổi file Excel (.xlsx) thành Hồ sơ Tóm tắt Giá trị Cao (Smart Document Dossier)."""
    import openpyxl

    try:
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    except Exception:
        from markitdown import MarkItDown

        return MarkItDown().convert(str(file_path)).text_content

    try:
        return _spreadsheet_dossier(wb, file_name)
    finally:
        # Windows cannot remove the temporary download while openpyxl still
        # owns the read-only ZIP handle.
        wb.close()


def _spreadsheet_dossier(wb: Any, file_name: str) -> str:
    """Build a readable preview from an already opened workbook."""

    sheet_names = wb.sheetnames
    sections = [f"# 📊 Hồ sơ Tài liệu: {file_name}"]
    sections.append(
        f"> [!NOTE]\n"
        f"> **Định dạng**: Bảng tính Excel (.xlsx) | "
        f"**Số trang tính**: {len(sheet_names)} sheet(s)\n"
        f"> 💡 *Veridra đã lọc bỏ toàn bộ các cột trống (`Unnamed`), "
        f"trích xuất thông tin trọng tâm và lập bảng xem trước tinh gọn.*"
    )

    sheet_summaries = []
    primary_preview = []

    for name in sheet_names:
        sheet = wb[name]
        rows = []
        for r in sheet.iter_rows(values_only=True):
            if any(cell is not None and str(cell).strip() != "" for cell in r):
                rows.append(list(r))
            if len(rows) >= 60:
                break

        if not rows:
            sheet_summaries.append((name, 0, 0, []))
            continue

        width = max(len(r) for r in rows)
        active_cols = [
            c for c in range(width)
            if any(c < len(r) and r[c] is not None and str(r[c]).strip() != "" for r in rows)
        ]
        first_row = rows[0]
        col_names = []
        for c in active_cols:
            raw_name = str(
                first_row[c] if c < len(first_row) and first_row[c] is not None else ""
            ).strip()
            if not raw_name or raw_name.lower().startswith("unnamed"):
                raw_name = f"Cột {c+1}"
            col_names.append(raw_name)

        sheet_summaries.append((name, len(rows), len(active_cols), col_names))

        if not primary_preview and len(rows) > 1:
            # Moderate-width sheets must retain all cells so questions about a
            # late column or a row total have the same evidence as the source.
            preview_cols = active_cols[:20]
            header_cells = [
                _markdown_cell(col_names[idx])
                for idx, _ in enumerate(preview_cols)
            ]
            tbl = [
                f"### 🔍 Mẫu dữ liệu tiêu biểu: Sheet `{name}`",
                "| " + " | ".join(header_cells) + " |",
                "| " + " | ".join("---" for _ in header_cells) + " |",
            ]
            preview_rows = rows[1:60] if len(active_cols) <= 20 else rows[1:6]
            for row in preview_rows:
                tbl.append(
                    "| " + " | ".join(
                        _markdown_cell(row[c] if c < len(row) else "")
                        for c in preview_cols
                    ) + " |"
                )
            if len(active_cols) > 20:
                tbl.append(
                    f"\n_*(Đã ẩn bớt {len(active_cols) - 20} cột để bảng xem trước vừa vặn. "
                    "Mở trên Google Sheets để thao tác đầy đủ)*_"
                )
            primary_preview = tbl

    sections.append("## 📑 Danh mục Trang tính & Cấu trúc Dữ liệu")
    tbl_rows = [
        "| Trang tính | Số dòng mẫu | Số cột dữ liệu | Các trường thông tin chính |",
        "|---|---|---|---|",
    ]
    for s_name, row_cnt, col_cnt, cols in sheet_summaries:
        cols_text = ", ".join(f"`{c}`" for c in cols[:8])
        if len(cols) > 8:
            cols_text += f" _(+{len(cols) - 8} cột khác)_"
        tbl_rows.append(
            f"| **{s_name}** | {row_cnt}+ dòng | {col_cnt} cột | "
            f"{cols_text or 'Trống'} |"
        )
    sections.append("\n".join(tbl_rows))

    if primary_preview:
        sections.append("\n".join(primary_preview))

    return "\n\n".join(sections)


def _google_sheet_markdown(service, spreadsheet_id: str) -> str:  # type: ignore[no-untyped-def]
    """Read every non-empty tab as a rectangular Markdown table or Dossier."""

    metadata = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="properties.title,sheets.properties(title,hidden)",
        includeGridData=False,
    ).execute()
    title = metadata.get("properties", {}).get("title", "Google Sheets")
    sections = [f"# {title}"]
    for sheet in metadata.get("sheets", []):
        properties = sheet.get("properties", {})
        sheet_title = str(properties.get("title", "Sheet"))
        escaped_title = sheet_title.replace("'", "''")
        response = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{escaped_title}'",
            majorDimension="ROWS",
            valueRenderOption="FORMATTED_VALUE",
            dateTimeRenderOption="FORMATTED_STRING",
        ).execute()
        rows = response.get("values", [])
        sections.append(f"## {sheet_title}")
        if not rows:
            sections.append("_(Trang tính trống)_")
            continue
        width = max(len(row) for row in rows)
        normalized = [list(row) + [""] * (width - len(row)) for row in rows]
        active_indices = [
            col_idx for col_idx in range(width)
            if any(str(row[col_idx]).strip() for row in normalized)
        ]
        if not active_indices:
            sections.append("_(Trang tính không có dữ liệu)_")
            continue

        if len(active_indices) > 20:
            header_row = normalized[0]
            col_names = [str(header_row[i]).strip() or f"Cột {i+1}" for i in active_indices]
            col_chips = ", ".join(f"`{c}`" for c in col_names[:10])
            if len(col_names) > 10:
                col_chips += f" _(+{len(col_names)-10} cột khác)_"
            sections.append(
                f"> [!NOTE]\n"
                f"> **Tổng số dòng**: {len(normalized)} | "
                f"**Số cột dữ liệu**: {len(active_indices)}\n"
                f"> **Các trường thông tin nhận diện**: {col_chips}\n"
                f"> 💡 *Bảng tính có {len(active_indices)} cột. Veridra đã rút gọn "
                "bảng xem trước 5 dòng đầu tiên với các cột cốt lõi.*"
            )
            preview_cols = active_indices[:8]
            p_headers = [str(header_row[i]).strip() or f"Cột {i+1}" for i in preview_cols]
            table = [
                "| " + " | ".join(_markdown_cell(h) for h in p_headers) + " |",
                "| " + " | ".join("---" for _ in p_headers) + " |",
            ]
            for row in normalized[1:6]:
                table.append("| " + " | ".join(_markdown_cell(row[i]) for i in preview_cols) + " |")
            sections.append("\n".join(table))
        else:
            header = [
                _markdown_cell(normalized[0][index]) or f"Cột {index + 1}"
                for index in active_indices
            ]
            table = [
                "| " + " | ".join(header) + " |",
                "| " + " | ".join("---" for _ in header) + " |",
            ]
            table.extend(
                "| " + " | ".join(_markdown_cell(row[index]) for index in active_indices) + " |"
                for row in normalized[1:]
            )
            sections.append("\n".join(table))
    return "\n\n".join(sections)


def _convert_bytes(
    content: bytes,
    mime_type: str,
    file_name: str = "",
    *,
    asset_dir: Path | None = None,
    asset_base_url: str | None = None,
) -> str:
    if file_name.lower().endswith(".ipynb"):
        return _extract_notebook(content)
    if mime_type.startswith("text/") or mime_type == "application/json":
        return content.decode("utf-8", errors="replace")
    suffix = _extension_for(mime_type)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    try:
        if mime_type == "application/pdf" or suffix == ".pdf":
            from app.services.pdf_parser import parse_pdf_to_markdown

            return parse_pdf_to_markdown(
                temp_path, asset_dir=asset_dir, asset_base_url=asset_base_url
            )
        if suffix in {".xlsx", ".xlsm", ".xltx"}:
            return _parse_spreadsheet_to_dossier(temp_path, file_name or "Bảng tính Excel")
        from markitdown import MarkItDown

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
        if not is_supported_drive_file(metadata["mimeType"], metadata.get("name", "")):
            raise ToolError(
                "Veridra chưa hỗ trợ đọc định dạng tệp này. "
                "Hãy dùng PDF, Docs, Sheets, Slides, DOCX, XLSX, PPTX, CSV, "
                "TXT, Markdown, HTML, JSON hoặc IPYNB.",
                code="unsupported_file_type",
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

        asset_user = context.user.id or hashlib.sha256(
            context.user.email.encode("utf-8")
        ).hexdigest()[:24]
        asset_dir = (
            context.settings.data_dir
            / "pdf_assets"
            / asset_user
            / metadata["id"]
        )
        if metadata["mimeType"] == GOOGLE_SHEET:
            credentials = await refresh_and_store_if_needed(
                context.user, context.db, context.settings
            )
            sheets_service = await asyncio.to_thread(
                build, "sheets", "v4", credentials=credentials, cache_discovery=False
            )
            text = await asyncio.to_thread(
                _google_sheet_markdown, sheets_service, metadata["id"]
            )
        else:
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
            effective_mime = EXPORT_MIME_TYPES.get(
                metadata["mimeType"], metadata["mimeType"]
            )
            text = await asyncio.to_thread(
                _convert_bytes,
                buffer.getvalue(),
                effective_mime,
                metadata.get("name", ""),
                asset_dir=asset_dir,
                asset_base_url=f"/api/drive/files/{metadata['id']}/assets",
            )
    except HttpError as exc:
        raise _translate_http_error(exc) from exc

    truncated = len(text) > payload.max_characters
    return FileContentResponse(
        file=_file_response(metadata),
        text=text[: payload.max_characters],
        truncated=truncated,
        assets=[
            f"/api/drive/files/{metadata['id']}/assets/{asset.name}"
            for asset in sorted(asset_dir.glob("image-*"))
            if asset.is_file()
        ],
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
            name="drive_file_metadata",
            description="Kiểm tra quyền đọc và phiên bản tệp Drive, không tải nội dung.",
            input_model=ReadDriveFileInput,
            output_model=DriveFileResponse,
            handler=drive_file_metadata,
            **common,
        ),
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
            timeout_seconds=120,
            **common,
        ),
    ]
