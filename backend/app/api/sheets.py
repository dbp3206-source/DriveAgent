"""Authenticated Sheets endpoints; approval cannot be supplied by model output."""

from fastapi import APIRouter, HTTPException, Request

from app.api.dependencies import CurrentUser, DbSession, is_trusted_ui_origin
from app.api.documents import invoke, operation
from app.core.config import get_settings
from app.tools.contracts import ToolContext
from app.tools.documents import DocumentApproval
from app.tools.sheets import SpreadsheetPrepare, sheets_reconcile

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


@router.post("/operations/{operation_id}/reconcile")
async def reconcile(operation_id: str, request: Request, user: CurrentUser, db: DbSession):
    settings = get_settings()
    if not is_trusted_ui_origin(request, settings):
        raise HTTPException(status_code=403, detail="Cần xác nhận từ giao diện ứng dụng.")
    return await sheets_reconcile(
        operation_id,
        ToolContext(
            request_id=request.state.request_id,
            user=user,
            db=db,
            settings=settings,
            source="sheets_reconciliation",
        ),
    )
