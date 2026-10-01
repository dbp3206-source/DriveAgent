"""Write endpoints require same-origin approval plus current RBAC and Google scopes."""

import asyncio

from fastapi import APIRouter, HTTPException, Request

from app.api.dependencies import CurrentUser, DbSession, is_trusted_ui_origin
from app.core.config import get_settings
from app.core.json_utils import json_object
from app.services.relational_operations import operation_store_for
from app.tools.contracts import ToolContext
from app.tools.documents import DocumentApproval, DocumentPrepare

router = APIRouter(prefix="/api/documents", tags=["documents"])


async def invoke(name, payload, request, user, db):
    settings = get_settings()
    if not is_trusted_ui_origin(request, settings):
        raise HTTPException(status_code=403, detail="Cần xác nhận từ giao diện ứng dụng.")
    return await request.app.state.registry.execute(
        name,
        payload.model_dump(mode="json"),
        ToolContext(
            request_id=getattr(request.state, "request_id", None) or "req-doc",
            user=user,
            db=db,
            settings=settings,
            source="api",
        ),
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
        operation_store_for(get_settings()).get,
        user.id,
        operation_id,
    )
    return {
        "operation_id": row["id"],
        "state": row["state"],
        "resource_id": row["resource_id"],
        "error_code": row["error_code"],
        "result": json_object(row["result"]) if row["result"] else None,
    }
