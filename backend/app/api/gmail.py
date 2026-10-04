"""Gmail API endpoints governed by 2-phase human approval and ToolRegistry."""

import asyncio
import base64
import re
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.api.dependencies import CurrentUser, DbSession, is_trusted_ui_origin
from app.auth.permissions import GMAIL_READ, permissions_for_role
from app.core.config import get_settings
from app.core.json_utils import json_object
from app.services.mail_images import MailImageError, MailImageIndex, fetch_mail_image
from app.services.relational_operations import operation_store_for
from app.tools.contracts import ToolContext, ToolError
from app.tools.gmail import (
    EmailApprovalInput,
    EmailPrepareInput,
    GmailDraftPrepareInput,
    GmailListInput,
    GmailReadThreadInput,
)

router = APIRouter(prefix="/api/gmail", tags=["gmail"])
_mail_images = MailImageIndex()
_image_slots = asyncio.Semaphore(4)


async def invoke_gmail_tool(name: str, payload: dict, request: Request, user, db):
    settings = get_settings()
    # Session auth alone is insufficient for write-capable endpoints: a foreign
    # page could otherwise submit a prepared digest with the user's cookie.
    if name in {
        "gmail_prepare_native_draft",
        "gmail_create_draft",
        "gmail_prepare_draft",
        "gmail_send",
    } and not is_trusted_ui_origin(request, settings):
        raise HTTPException(status_code=403, detail="Cần xác nhận từ giao diện ứng dụng.")
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
    page_token: str | None = Query(default=None, min_length=1, max_length=500),
):
    """Lấy danh sách thư Gmail theo bộ lọc."""
    payload = GmailListInput(
        query=query, max_results=max_results, page_token=page_token
    ).model_dump(mode="json")
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
    result = await invoke_gmail_tool("gmail_read_thread", payload, request, user, db)
    data = result.model_dump(mode="json")
    for message in data.get("messages", []):
        message["external_image_sources"] = _mail_images.register(
            str(user.id), message["id"], message.get("html_body") or ""
        )
    return data


@router.get("/messages/{message_id}/images/{image_id}")
async def external_image(message_id: str, image_id: str, user: CurrentUser):
    if GMAIL_READ not in permissions_for_role(user.role):
        raise HTTPException(403, "Tài khoản không có quyền đọc Gmail.")
    source = _mail_images.lookup(str(user.id), message_id, image_id)
    if not source:
        raise HTTPException(404, "Mở lại thư để tải ảnh; ảnh không thuộc thư đã mở của tài khoản.")
    try:
        async with asyncio.timeout(15):
            async with _image_slots:
                async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
                    content, mime = await fetch_mail_image(source, client)
    except (MailImageError, httpx.HTTPError, OSError, TimeoutError) as exc:
        raise HTTPException(502, "Chưa tải được ảnh từ máy chủ bên ngoài.") from exc
    return Response(content, media_type=mime, headers={
        "Cache-Control": "private, max-age=300",
        "Vary": "Cookie",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
    })


@router.get("/messages/{message_id}/attachments/{attachment_id}")
async def get_attachment(
    message_id: str,
    attachment_id: str,
    request: Request,
    user: CurrentUser,
    db: DbSession,
    inline: bool = Query(default=False),
):
    """Serve only a Gmail-verified attachment; inline display is restricted to raster images."""
    result = await invoke_gmail_tool(
        "gmail_get_attachment",
        {"message_id": message_id, "attachment_id": attachment_id},
        request,
        user,
        db,
    )
    mime_type = str(result.mime_type or "application/octet-stream").casefold()
    try:
        content = base64.b64decode(result.data_base64, validate=True)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Không thể đọc tệp đính kèm.") from exc

    safe_inline_types = {
        "image/png", "image/jpeg", "image/gif", "image/webp", "image/avif", "image/bmp"
    }
    can_inline = inline and mime_type in safe_inline_types
    disposition = "inline" if can_inline else "attachment"
    filename = re.sub(r"[\r\n\x00-\x1f\x7f]", "_", str(result.filename or "attachment"))[:180]
    headers = {
        "Content-Disposition": (
            f"{disposition}; filename*=UTF-8''{quote(filename, safe='')} ".strip()
        ),
        "Cache-Control": "private, no-store",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
    }
    return Response(
        content=content,
        media_type=mime_type if can_inline else "application/octet-stream",
        headers=headers,
    )


@router.post("/threads/{thread_id}/summary")
async def summarize_thread(
    thread_id: str,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Tóm tắt toàn bộ chuỗi thành đúng ba ý theo yêu cầu chủ động của người dùng."""
    if not is_trusted_ui_origin(request, get_settings()):
        raise HTTPException(status_code=403, detail="Cần thao tác từ giao diện ứng dụng.")
    payload = GmailReadThreadInput(thread_id=thread_id).model_dump(mode="json")
    return await invoke_gmail_tool("gmail_summarize_thread", payload, request, user, db)


@router.post("/draft")
async def create_draft(
    payload: GmailDraftPrepareInput,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Chuẩn bị xem trước thư nháp; Gmail chưa thay đổi ở bước này."""
    return await invoke_gmail_tool(
        "gmail_prepare_native_draft", payload.model_dump(mode="json"), request, user, db
    )


@router.post("/draft/approve")
async def approve_draft(
    payload: EmailApprovalInput,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Tạo native Gmail draft đúng với nội dung người dùng đã duyệt."""
    return await invoke_gmail_tool(
        "gmail_create_draft", payload.model_dump(mode="json"), request, user, db
    )


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
    """Check a user-owned Gmail send or draft operation."""
    try:
        row = await asyncio.to_thread(
            operation_store_for(get_settings()).get,
            user.id,
            operation_id,
        )
    except ToolError:
        raise HTTPException(status_code=404, detail="Không tìm thấy thao tác.") from None
    return {
        "operation_id": row["id"],
        "state": row["state"],
        "resource_id": row["resource_id"],
        "error_code": row["error_code"],
        "result": json_object(row["result"]) if row["result"] else None,
    }
