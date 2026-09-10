"""API kết quả đã lưu. Export không chạy Markdown/HTML và luôn tải xuống."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession, require_permission
from app.auth.permissions import MEMORY_READ
from app.db.models import SavedArtifact
from app.services.artifacts import ArtifactWrite
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


@router.get("/{artifact_id}/export", dependencies=[Depends(require_permission(MEMORY_READ))])
async def export(artifact_id: str, user: CurrentUser, db: DbSession):
    row = await db.scalar(
        select(SavedArtifact).where(
            SavedArtifact.id == artifact_id, SavedArtifact.user_id == user.id
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản lưu.")
    return Response(
        f"# {row.title}\n\n{row.content}\n",
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="note-{row.id}.md"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
