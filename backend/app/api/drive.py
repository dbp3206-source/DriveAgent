"""API Drive gọi Tool Registry, không gọi Google API trực tiếp."""

import asyncio
import hashlib
import io
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import (
    DriveFileListResponse,
    FileContentResponse,
    IndexFileResponse,
    UnindexFileResponse,
)
from app.core.config import get_settings
from app.db.models import DriveFileIndex
from app.services.rag import (
    IndexDriveFileInput,
    is_current_index_hash,
    same_drive_revision,
)
from app.services.user_inference import user_runtime_settings
from app.tools.contracts import ToolContext, ToolError
from app.tools.drive import (
    GOOGLE_FOLDER,
    ListDriveFilesInput,
    ReadDriveFileInput,
    SearchDriveFilesInput,
    _download_request,
    _drive_service,
)
from app.tools.registry import ToolRegistry

router = APIRouter(prefix="/api/drive", tags=["drive"])


def _asset_user_scope(user) -> str:  # type: ignore[no-untyped-def]
    if user.id:
        return str(user.id)
    return hashlib.sha256(user.email.encode("utf-8")).hexdigest()[:24]


def registry_from(request: Request) -> ToolRegistry:
    return request.app.state.registry


async def execute(request: Request, user, db, tool: str, arguments: dict):  # type: ignore[no-untyped-def]
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return await registry_from(request).execute(
        tool,
        arguments,
        ToolContext(
            request_id=request_id,
            user=user,
            db=db,
            settings=await user_runtime_settings(db, user.id, get_settings()),
            source="api",
        ),
    )


@router.get("/files", response_model=DriveFileListResponse)
async def list_files(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    query: str | None = Query(default=None, max_length=500),
    page_size: int = Query(default=50, ge=1, le=100),
    page_token: str | None = None,
    mime_type: str | None = None,
    folder_id: str | None = None,
):
    if query:
        result = await execute(
            request,
            user,
            db,
            "drive_search_files",
            SearchDriveFilesInput(
                query=query,
                page_size=page_size,
                page_token=page_token,
                mime_type=mime_type,
            ).model_dump(),
        )
    else:
        result = await execute(
            request,
            user,
            db,
            "drive_list_files",
            ListDriveFilesInput(
                page_size=page_size,
                page_token=page_token,
                mime_type=mime_type,
                folder_id=folder_id,
            ).model_dump(),
        )
    indexed_rows = {
        row.drive_file_id: (row.modified_time, row.content_hash)
        for row in await db.scalars(
            select(DriveFileIndex).where(DriveFileIndex.user_id == user.id)
        )
    }
    for file in result.files:
        indexed_state = indexed_rows.get(file.id)
        if indexed_state is None:
            file.indexed = False
            file.index_status = "not_indexed"
        elif is_current_index_hash(indexed_state[1], get_settings()) and same_drive_revision(
            indexed_state[0], file.modified_time
        ):
            file.indexed = True
            file.index_status = "fresh"
        else:
            file.indexed = False
            file.index_status = "stale"
    return result


@router.get("/files/{file_id}/content", response_model=FileContentResponse)
async def read_file(file_id: str, request: Request, user: CurrentUser, db: DbSession):
    return await execute(
        request,
        user,
        db,
        "drive_read_file",
        ReadDriveFileInput(file_id=file_id).model_dump(),
    )


@router.get("/files/{file_id}/source")
async def read_file_source(file_id: str, request: Request, user: CurrentUser, db: DbSession):
    """Return original bytes for formats where an in-app conversion is lossy.

    Workspace-native files intentionally stay source-only: the user receives the
    canonical Drive URL instead of a misleading reconstructed document.
    """

    metadata = await execute(
        request,
        user,
        db,
        "drive_file_metadata",
        ReadDriveFileInput(file_id=file_id).model_dump(),
    )
    if metadata.mime_type == GOOGLE_FOLDER:
        raise HTTPException(status_code=409, detail="Thư mục không có nội dung để xem.")
    if metadata.mime_type.startswith("application/vnd.google-apps"):
        raise HTTPException(
            status_code=409,
            detail="Tệp Google Workspace nên mở bằng đường dẫn gốc để giữ nguyên định dạng.",
        )
    allowed = (
        metadata.mime_type.startswith("image/")
        or metadata.mime_type.startswith("text/")
        or metadata.mime_type in {"application/pdf", "application/json", "text/csv"}
    )
    if not allowed:
        raise HTTPException(
            status_code=409,
            detail="Định dạng này có thể mất bố cục khi xem trong ứng dụng; hãy mở bản gốc.",
        )
    service = await _drive_service(
        ToolContext(
            request_id=getattr(request.state, "request_id", str(uuid4())),
            user=user,
            db=db,
            settings=get_settings(),
            source="api",
        )
    )
    try:
        raw = await asyncio.to_thread(
            service.files()
            .get(
                fileId=file_id,
                fields="id,name,mimeType,size,trashed,capabilities(canDownload)",
                supportsAllDrives=True,
            )
            .execute
        )
        if raw.get("trashed") or raw.get("capabilities", {}).get("canDownload") is False:
            raise HTTPException(status_code=404, detail="Tệp không còn quyền đọc.")
        if raw.get("mimeType") != metadata.mime_type:
            raise HTTPException(status_code=409, detail="Phiên bản tệp đã thay đổi; hãy tải lại.")
        request_media = _download_request(service, raw)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request_media, chunksize=1024 * 1024)
        done = False
        limit = get_settings().max_download_mb * 1024 * 1024
        while not done:
            _status, done = await asyncio.to_thread(downloader.next_chunk)
            if buffer.tell() > limit:
                raise HTTPException(status_code=413, detail="Tệp vượt giới hạn xem trực tiếp.")
    except ToolError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except HttpError as exc:
        raise HTTPException(
            status_code=502,
            detail="Không thể tải bản gốc từ Google Drive.",
        ) from exc
    filename = raw.get("name", "drive-file")
    return Response(
        content=buffer.getvalue(),
        media_type=raw.get("mimeType", "application/octet-stream"),
        headers={"Content-Disposition": f'inline; filename="{filename.replace(chr(34), "")}"'},
    )


@router.get("/files/{file_id}/assets/{asset_name:path}")
async def read_file_asset(
    file_id: str,
    asset_name: str,
    user: CurrentUser,
    request: Request,
):
    """Serve parser-owned PDF images only for the current user's file scope."""

    root = (get_settings().data_dir / "pdf_assets" / _asset_user_scope(user) / file_id).resolve()
    candidate = (root / asset_name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Asset không tồn tại.") from exc
    if (
        not candidate.is_file()
        or candidate.parent != root
        or candidate.name != asset_name.split("/")[-1]
    ):
        raise HTTPException(status_code=404, detail="Asset không tồn tại.")
    return FileResponse(candidate)


@router.post("/files/{file_id}/index", response_model=IndexFileResponse)
async def index_file(
    file_id: str,
    request: Request,
    user: CurrentUser,
    db: DbSession,
    force: bool = False,
):
    return await execute(
        request,
        user,
        db,
        "rag_index_drive_file",
        IndexDriveFileInput(file_id=file_id, force=force).model_dump(),
    )


@router.delete("/files/{file_id}/index", response_model=UnindexFileResponse)
async def unindex_file(
    file_id: str,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    return await execute(
        request,
        user,
        db,
        "rag_unindex_drive_file",
        {"file_id": file_id},
    )
