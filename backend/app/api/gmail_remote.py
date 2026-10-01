"""Signed remote Gmail actions with explicit browser confirmation."""

from html import escape
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import get_settings
from app.services.gmail_remote import GmailRemoteService, RemoteActionSigner, reply_draft_body
from app.tools.contracts import ToolError

router = APIRouter(prefix="/api/gmail/remote", tags=["gmail_remote"])


class RemoteActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=10, max_length=2000)


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or "remote-req"


@router.get("/digest")
async def get_remote_digest(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    query: str = Query(default="is:unread newer_than:2d", max_length=200),
    max_results: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    """Lấy bản tin tóm tắt email điều hành và danh sách email khẩn cấp từ xa."""
    settings = get_settings()
    service = GmailRemoteService(settings, request.app.state.registry)
    return await service.get_executive_digest(
        user=user,
        db=db,
        request_id=_get_request_id(request),
        query=query,
        max_results=max_results,
    )


@router.post("/action")
async def execute_remote_action(
    payload: RemoteActionPayload,
    request: Request,
    db: DbSession,
) -> dict[str, Any]:
    """Thực thi thao tác từ xa bằng Remote Action Token bảo mật."""
    settings = get_settings()
    service = GmailRemoteService(settings, request.app.state.registry)
    try:
        return await service.execute_remote_token(
            token=payload.token,
            db=db,
            request_id=_get_request_id(request),
        )
    except ToolError as exc:
        status_code = 409 if exc.code == "remote_action_replayed" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


def _confirmation_page(token: str, heading: str, details: str) -> HTMLResponse:
    safe_token = escape(token, quote=True)
    content = f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="origin"><title>Veridra · Xác nhận</title>
<style>
body{{font:16px/1.55 system-ui,sans-serif;background:#111827;color:#f3f4f6;
margin:0;padding:24px}}
main{{max-width:680px;margin:8vh auto;background:#1f2937;
padding:28px;border-radius:20px}}
h1{{font-size:1.35rem;margin:0 0 1rem}}
.preview{{white-space:pre-wrap;overflow-wrap:anywhere;background:#111827;
padding:16px;border-radius:12px}}
button{{font:inherit;font-weight:650;border:0;border-radius:999px;
padding:12px 20px;background:#4f8cff;color:#07111f;
cursor:pointer}}
.note{{color:#cbd5e1}}dt{{color:#aab5c5}}
dd{{margin:0 0 .8rem;overflow-wrap:anywhere}}
</style></head><body><main><h1>{heading}</h1>{details}
<p class="note">Chưa có thay đổi nào được ghi lên Google.
Chỉ tiếp tục nếu bản xem trước chính xác.</p>
<form method="post" action="/api/gmail/remote/action/confirm">
<input type="hidden" name="token" value="{safe_token}">
<button type="submit">Xác nhận thao tác này</button></form></main></body></html>"""
    return HTMLResponse(
        content=content,
        headers={
            "Cache-Control": "no-store, private",
            # A same-origin confirmation POST needs an origin signal for the
            # public CSRF gate, but the signed action token in the GET URL must
            # never appear in a Referer header.
            "Referrer-Policy": "origin",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _result_page(heading: str, message: str, status_code: int = 200, link: str = ""):
    safe_link = ""
    if link.startswith("https://mail.google.com/"):
        safe_link = (
            f'<p><a rel="noreferrer" href="{escape(link, quote=True)}">'
            "Mở bản nháp trong Gmail ↗</a></p>"
        )
    content = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Veridra · Trạng thái</title><style>
body{{font:16px/1.55 system-ui,sans-serif;background:#111827;color:#f3f4f6;
margin:0;padding:24px}}
main{{max-width:680px;margin:8vh auto;background:#1f2937;
padding:28px;border-radius:20px}}
a{{color:#93c5fd}}
</style></head><body><main><h1>{escape(heading)}</h1><p>{escape(message)}</p>{safe_link}</main></body></html>"""
    return HTMLResponse(
        content=content,
        status_code=status_code,
        headers={
            "Cache-Control": "no-store, private",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/action/run", response_class=HTMLResponse)
async def run_remote_action_link(
    request: Request,
    token: str = Query(min_length=10, max_length=2000),
):
    """Show a safe preview. GET never performs a Gmail or Drive write."""
    settings = get_settings()
    try:
        data = RemoteActionSigner.verify_action(token, settings.app_secret)
        action = data.get("action")
        payload = data.get("payload", {})
        if action == "create_reply_draft":
            recipient = str(payload.get("recipient", ""))
            subject = str(payload.get("subject", "Re: Email"))
            body = reply_draft_body(
                recipient,
                str(payload.get("source_snippet", "")),
                str(payload.get("display_name", "Veridra")),
            )
            details = (
                f"<dl><dt>Người nhận</dt><dd>{escape(recipient)}</dd>"
                f"<dt>Tiêu đề</dt><dd>{escape(subject)}</dd></dl>"
                f'<div class="preview">{escape(body)}</div>'
            )
            return _confirmation_page(token, "Xem lại thư nháp Gmail", details)
        if action == "export_to_doc":
            title = str(payload.get("title", "Tóm tắt Email"))
            content = str(payload.get("content", ""))
            details = (
                f"<dl><dt>Tên tài liệu</dt><dd>{escape(title)}</dd></dl>"
                f'<div class="preview">{escape(content)}</div>'
            )
            return _confirmation_page(token, "Xem lại nội dung chuẩn bị xuất", details)
        raise ToolError("Hành động từ xa không được hỗ trợ.", code="unsupported_action")
    except ToolError as exc:
        messages = {
            "token_expired": "Liên kết đã hết hạn. Hãy tạo yêu cầu mới từ Veridra.",
            "remote_action_replayed": "Yêu cầu này đã được dùng. Hãy tạo yêu cầu mới.",
            "invalid_signature": "Liên kết không hợp lệ.",
        }
        return _result_page(
            "Không thể xác nhận",
            messages.get(exc.code, "Liên kết không hợp lệ."),
            400,
        )


@router.post("/action/confirm", response_class=HTMLResponse)
async def confirm_remote_action(
    request: Request,
    db: DbSession,
    token: str = Form(min_length=10, max_length=2000),
):
    """Execute only after the user submits the preview confirmation form."""
    service = GmailRemoteService(get_settings(), request.app.state.registry)
    try:
        result = await service.execute_remote_token(
            token=token,
            db=db,
            request_id=_get_request_id(request),
        )
        return _result_page(
            "Đã hoàn tất thao tác",
            result.get("message", "Thao tác đã hoàn tất."),
            link=result.get("gmail_draft_url", ""),
        )
    except ToolError as exc:
        status_code = 409 if exc.code == "remote_action_replayed" else 400
        messages = {
            "remote_action_replayed": (
                "Yêu cầu này đã được dùng, không thực hiện lại để tránh thao tác trùng."
            ),
            "token_expired": "Liên kết đã hết hạn. Hãy tạo yêu cầu mới từ Veridra.",
        }
        return _result_page(
            "Không thể hoàn tất",
            messages.get(
                exc.code,
                "Thao tác không thành công. Hãy mở Veridra để kiểm tra trạng thái.",
            ),
            status_code,
        )


@router.post("/webhook")
async def gmail_pubsub_webhook(
    request: Request,
):
    """Push delivery remains disabled until Google OIDC verification is configured."""
    raise HTTPException(
        status_code=501,
        detail="Gmail push chưa được cấu hình; webhook chưa nhận sự kiện.",
    )
