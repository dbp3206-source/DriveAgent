"""Write endpoints require same-origin approval plus current RBAC and Google scopes."""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import get_settings
from app.services.operations import OperationStore
from app.tools.contracts import ToolContext
from app.tools.documents import DocumentApproval, DocumentPrepare

router = APIRouter(prefix="/api/documents", tags=["documents"])


async def invoke(name, payload, request, user, db):
    settings = get_settings()
    if request.headers.get("origin") not in {settings.frontend_origin, settings.public_base_url}:
        raise HTTPException(status_code=403, detail="Cần xác nhận từ giao diện ứng dụng.")
    return await request.app.state.registry.execute(
        name,
        payload.model_dump(mode="json"),
        ToolContext(request_id=request.state.request_id, user=user, db=db, settings=settings),
    )


@router.post("/prepare")
async def prepare(payload: DocumentPrepare, request: Request, user: CurrentUser, db: DbSession):
    return await invoke("docs_prepare", payload, request, user, db)


@router.post("/approve")
async def approve(payload: DocumentApproval, request: Request, user: CurrentUser, db: DbSession):
    return await invoke("docs_execute", payload, request, user, db)


@router.get("/operations/{operation_id}")
async def operation(operation_id: str, user: CurrentUser):
    row = await asyncio.to_thread(
        OperationStore(get_settings().data_dir / "operations.db").get,
        user.id,
        operation_id,
    )
    return {
        "operation_id": row["id"],
        "state": row["state"],
        "resource_id": row["resource_id"],
        "error_code": row["error_code"],
        "result": json.loads(row["result"]) if row["result"] else None,
    }
