"""API Drive gọi Tool Registry, không gọi Google API trực tiếp."""

from uuid import uuid4

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import DriveFileListResponse, FileContentResponse, IndexFileResponse
from app.core.config import get_settings
from app.db.models import DriveFileIndex
from app.services.rag import IndexDriveFileInput
from app.tools.contracts import ToolContext
from app.tools.drive import ListDriveFilesInput, ReadDriveFileInput, SearchDriveFilesInput
from app.tools.registry import ToolRegistry

router = APIRouter(prefix="/api/drive", tags=["drive"])


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
            settings=get_settings(),
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
    indexed_ids = set(
        await db.scalars(
            select(DriveFileIndex.drive_file_id).where(DriveFileIndex.user_id == user.id)
        )
    )
    for file in result.files:
        file.indexed = file.id in indexed_ids
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
