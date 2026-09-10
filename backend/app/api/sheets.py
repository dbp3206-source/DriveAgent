"""Authenticated Sheets endpoints; approval cannot be supplied by model output."""

from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUser, DbSession
from app.api.documents import invoke, operation
from app.tools.documents import DocumentApproval
from app.tools.sheets import SpreadsheetPrepare

router = APIRouter(prefix="/api/sheets", tags=["sheets"])


@router.post("/prepare")
async def prepare(payload: SpreadsheetPrepare, request: Request, user: CurrentUser, db: DbSession):
    return await invoke("sheets_prepare", payload, request, user, db)


@router.post("/approve")
async def approve(payload: DocumentApproval, request: Request, user: CurrentUser, db: DbSession):
    return await invoke("sheets_execute", payload, request, user, db)


@router.get("/operations/{operation_id}")
async def status(operation_id: str, user: CurrentUser):
    return await operation(operation_id, user)
