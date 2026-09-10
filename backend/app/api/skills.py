"""Same-origin skill management and read-only skill runtime endpoints."""

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUser, DbSession
from app.api.documents import invoke
from app.core.config import get_settings
from app.tools.contracts import ToolContext
from app.tools.skills import SkillArchive, SkillRun, SkillSave

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("")
async def list_all(
    request: Request, user: CurrentUser, db: DbSession, include_archived: bool = False
):
    return await request.app.state.registry.execute(
        "skill_list",
        {"include_archived": include_archived},
        ToolContext(
            request_id=request.state.request_id,
            user=user,
            db=db,
            settings=get_settings(),
            source="api",
        ),
    )


@router.post("")
async def save(payload: SkillSave, request: Request, user: CurrentUser, db: DbSession):
    return await invoke("skill_save", payload, request, user, db)


@router.post("/run")
async def run(payload: SkillRun, request: Request, user: CurrentUser, db: DbSession):
    return await invoke("skill_run", payload, request, user, db)


@router.post("/archive")
async def archive(payload: SkillArchive, request: Request, user: CurrentUser, db: DbSession):
    return await invoke("skill_archive", payload, request, user, db)
