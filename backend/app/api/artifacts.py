"""API kết quả đã lưu. Export an toàn sang Markdown, DOCX hoặc PDF."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession, require_permission
from app.auth.permissions import REPORT_EXPORT
from app.db.models import SavedArtifact
from app.services.artifacts import ArtifactWrite
from app.services.report_exports import export_report
from app.tools.contracts import ToolContext

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.get("")
async def listing(
    request: Request, user: CurrentUser, db: DbSession, include_archived: bool = False
):
    from app.core.config import get_settings

    return await request.app.state.registry.execute(
        "artifact_list",
        {"include_archived": include_archived},
        ToolContext(request_id=request.state.request_id, user=user, db=db, settings=get_settings()),
    )


@router.post("")
async def save(payload: ArtifactWrite, request: Request, user: CurrentUser, db: DbSession):
    from app.core.config import get_settings

    return await request.app.state.registry.execute(
        "artifact_save",
        payload.model_dump(mode="json"),
        ToolContext(request_id=request.state.request_id, user=user, db=db, settings=get_settings()),
    )


@router.get("/{artifact_id}/export", dependencies=[Depends(require_permission(REPORT_EXPORT))])
async def export(
    artifact_id: str,
    user: CurrentUser,
    db: DbSession,
    format: Literal["md", "docx", "pdf"] = "md",
):
    row = await db.scalar(
        select(SavedArtifact).where(
            SavedArtifact.id == artifact_id, SavedArtifact.user_id == user.id
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản lưu.")
    body, media_type = export_report(row.title, row.content, format)
    return Response(
        body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="report-{row.id}.{format}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
