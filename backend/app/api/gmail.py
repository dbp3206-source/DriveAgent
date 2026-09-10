"""Gmail API endpoints governed by 2-phase human approval and ToolRegistry."""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import get_settings
from app.services.operations import OperationStore
from app.tools.contracts import ToolContext
from app.tools.gmail import (
    EmailApprovalInput,
    EmailPrepareInput,
    GmailListInput,
    GmailReadThreadInput,
)

router = APIRouter(prefix="/api/gmail", tags=["gmail"])


async def invoke_gmail_tool(name: str, payload: dict, request: Request, user, db):
    settings = get_settings()
    return await request.app.state.registry.execute(
        name,
        payload,
        ToolContext(request_id=request.state.request_id, user=user, db=db, settings=settings),
    )


@router.get("/messages")
async def list_messages(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    query: str = Query(default="is:unread", max_length=200),
    max_results: int = Query(default=10, ge=1, le=50),
):
    """Lấy danh sách thư Gmail theo bộ lọc."""
    payload = GmailListInput(query=query, max_results=max_results).model_dump(mode="json")
    return await invoke_gmail_tool("gmail_list_messages", payload, request, user, db)


@router.get("/threads/{thread_id}")
async def read_thread(
    thread_id: str,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Đọc toàn bộ nội dung chuỗi hội thoại email."""
    payload = GmailReadThreadInput(thread_id=thread_id).model_dump(mode="json")
    return await invoke_gmail_tool("gmail_read_thread", payload, request, user, db)


@router.post("/prepare")
async def prepare_email(
    payload: EmailPrepareInput,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Soạn bản nháp email và sinh mã SHA-256 digest để người dùng xem trước."""
    return await invoke_gmail_tool(
        "gmail_prepare_draft", payload.model_dump(mode="json"), request, user, db
    )


@router.post("/approve")
async def approve_and_send(
    payload: EmailApprovalInput,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Người dùng bấm xác nhận gửi đúng bản digest đã duyệt."""
    return await invoke_gmail_tool("gmail_send", payload.model_dump(mode="json"), request, user, db)


@router.get("/operations/{operation_id}")
async def get_operation(operation_id: str, user: CurrentUser):
    """Xem trạng thái gửi email từ operations.db."""
    row = await asyncio.to_thread(
        OperationStore(get_settings().data_dir / "operations.db").get,
        user.id,
        operation_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy thao tác.")
    return {
        "operation_id": row["id"],
        "state": row["state"],
        "resource_id": row["resource_id"],
        "error_code": row["error_code"],
        "result": json.loads(row["result"]) if row["result"] else None,
    }
