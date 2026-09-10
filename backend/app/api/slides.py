"""Authenticated Google Slides endpoints with digest-bound approval."""

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUser, DbSession
from app.api.documents import invoke, operation
from app.tools.documents import DocumentApproval
from app.tools.slides import SlidesPrepare

router = APIRouter(prefix="/api/slides", tags=["slides"])


@router.post("/prepare")
async def prepare(payload: SlidesPrepare, request: Request, user: CurrentUser, db: DbSession):
    return await invoke("slides_prepare", payload, request, user, db)


@router.post("/approve")
async def approve(payload: DocumentApproval, request: Request, user: CurrentUser, db: DbSession):
    return await invoke("slides_execute", payload, request, user, db)


@router.get("/operations/{operation_id}")
async def status(operation_id: str, user: CurrentUser):
    return await operation(operation_id, user)
