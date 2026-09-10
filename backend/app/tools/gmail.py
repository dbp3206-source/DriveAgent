"""Gmail tools governed by 6-gate registry and 2-phase human-in-the-loop approval."""

import asyncio
import base64
import io
import json
import logging
import mimetypes
import secrets
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from pydantic import BaseModel, ConfigDict, Field

from app.auth.google_oauth import refresh_and_store_if_needed
from app.auth.permissions import GMAIL_READ, GMAIL_SEND
from app.services.operations import OperationStore
from app.tools.contracts import ToolContext, ToolDefinition, ToolError

logger = logging.getLogger(__name__)

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
GOOGLE_EXPORTS = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
    "application/vnd.google-apps.drawing": ("image/png", ".png"),
}


def operation_store(context: ToolContext) -> OperationStore:
    return OperationStore(context.settings.data_dir / "operations.db")


def handle_gmail_http_error(exc: HttpError, action: str = "thao tác") -> ToolError:
    err_str = str(exc)
    if exc.status_code == 403 and "insufficientPermissions" in err_str:
        return ToolError(
            "Tài khoản Google chưa cấp đủ quyền đọc hoặc gửi Gmail. "
            "Vui lòng bấm vào đây để kết nối lại tài khoản và cấp quyền Gmail: /api/auth/google",
            code="gmail_insufficient_permissions",
        )
    if "accessNotConfigured" in err_str or "has not been used" in err_str or "disabled" in err_str:
        return ToolError(
            "Gmail API chưa được Kích hoạt (Enable) trong Google Cloud Console. "
            "Hãy bật Gmail API trong Google Cloud Console, sau đó kết nối lại tài khoản.",
            code="gmail_api_disabled",
        )
    return ToolError(f"Gmail tạm thời không thể {action}.", code="gmail_error")


class GmailListInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(default="is:unread", max_length=200)
    max_results: int = Field(default=10, ge=1, le=50)


class EmailHeaderSummary(BaseModel):
    id: str
    thread_id: str
    sender: str
    subject: str
    date: str
    snippet: str


class GmailListOutput(BaseModel):
    messages: list[EmailHeaderSummary]
    total_found: int


class GmailReadThreadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thread_id: str = Field(min_length=5, max_length=100)


class ThreadMessage(BaseModel):
    id: str
    sender: str
    recipient: str
    date: str
    subject: str
    body: str


class GmailReadThreadOutput(BaseModel):
    thread_id: str
    subject: str
    messages: list[ThreadMessage]


class EmailDraftSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient: str = Field(min_length=3, max_length=200)
    subject: str = Field(min_length=1, max_length=250)
    body: str = Field(min_length=1, max_length=50000)
    drive_file_ids: list[str] = Field(default_factory=list, max_length=5)


class EmailPrepareInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(pattern=r"^[A-Za-z0-9_-]{8,100}$")
    draft: EmailDraftSpec


class EmailApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    approved_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class EmailOperationResult(BaseModel):
    data: dict[str, Any]


def _download_attachment(drive, file_id: str) -> tuple[str, str, bytes]:
    """Download one user-selected Drive file with a bounded in-memory payload."""

    metadata = (
        drive.files()
        .get(fileId=file_id, fields="id,name,mimeType,size,trashed,capabilities(canDownload)")
        .execute(num_retries=0)
    )
    if metadata.get("trashed") or metadata.get("capabilities", {}).get("canDownload") is False:
        raise ToolError("Không thể tải một tệp đính kèm đã chọn.", code="attachment_unavailable")
    declared_size = int(metadata.get("size") or 0)
    if declared_size > MAX_ATTACHMENT_BYTES:
        raise ToolError("Tệp đính kèm vượt giới hạn 15 MB.", code="attachment_too_large")

    source_mime = metadata.get("mimeType", "application/octet-stream")
    file_name = metadata.get("name", "attachment")
    if source_mime in GOOGLE_EXPORTS:
        target_mime, extension = GOOGLE_EXPORTS[source_mime]
        request = drive.files().export_media(fileId=file_id, mimeType=target_mime)
        if not file_name.casefold().endswith(extension):
            file_name += extension
    else:
        target_mime = source_mime
        request = drive.files().get_media(fileId=file_id)

    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk(num_retries=0)
        if buffer.tell() > MAX_ATTACHMENT_BYTES:
            raise ToolError("Tệp đính kèm vượt giới hạn 15 MB.", code="attachment_too_large")
    return file_name, target_mime, buffer.getvalue()


def _attach_drive_files(message: MIMEMultipart, credentials, file_ids: list[str]) -> list[str]:
    if not file_ids:
        return []
    total = 0
    names: list[str] = []
    with build("drive", "v3", credentials=credentials, cache_discovery=False) as drive:
        for file_id in file_ids:
            name, mime_type, payload = _download_attachment(drive, file_id)
            total += len(payload)
            if total > MAX_ATTACHMENT_BYTES:
                raise ToolError(
                    "Tổng dung lượng tệp đính kèm vượt giới hạn 15 MB.",
                    code="attachments_too_large",
                )
            guessed = mimetypes.guess_type(name)[0] or mime_type
            maintype, _, subtype = guessed.partition("/")
            part = MIMEBase(maintype or "application", subtype or "octet-stream")
            part.set_payload(payload)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=name)
            message.attach(part)
            names.append(name)
    return names


async def gmail_list_messages(payload: GmailListInput, context: ToolContext) -> GmailListOutput:
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)

    def execute() -> GmailListOutput:
        with build("gmail", "v1", credentials=credentials, cache_discovery=False) as service:
            try:
                res = (
                    service.users()
                    .messages()
                    .list(userId="me", q=payload.query, maxResults=payload.max_results)
                    .execute()
                )
                items = res.get("messages", [])
                total = res.get("resultSizeEstimate", len(items))

                summaries = []
                for item in items[: payload.max_results]:
                    msg = (
                        service.users()
                        .messages()
                        .get(
                            userId="me",
                            id=item["id"],
                            format="metadata",
                            metadataHeaders=["From", "Subject", "Date"],
                        )
                        .execute()
                    )
                    headers = {
                        h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])
                    }
                    summaries.append(
                        EmailHeaderSummary(
                            id=msg["id"],
                            thread_id=msg.get("threadId", msg["id"]),
                            sender=headers.get("From", "Không rõ"),
                            subject=headers.get("Subject", "(Không có tiêu đề)"),
                            date=headers.get("Date", ""),
                            snippet=msg.get("snippet", ""),
                        )
                    )
                return GmailListOutput(messages=summaries, total_found=total)
            except HttpError as exc:
                raise handle_gmail_http_error(exc, "tìm kiếm email") from exc

    return await asyncio.to_thread(execute)


async def gmail_read_thread(
    payload: GmailReadThreadInput, context: ToolContext
) -> GmailReadThreadOutput:
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)

    def extract_body(payload_part: dict) -> str:
        body = ""
        if "body" in payload_part and payload_part["body"].get("data"):
            try:
                return base64.urlsafe_b64decode(payload_part["body"]["data"]).decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                pass
        parts = payload_part.get("parts", [])
        for p in parts:
            mime = p.get("mimeType", "")
            if mime == "text/plain" and p.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", errors="replace")
            if mime == "text/html" and p.get("body", {}).get("data"):
                body = base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", errors="replace")
        return body

    def execute() -> GmailReadThreadOutput:
        with build("gmail", "v1", credentials=credentials, cache_discovery=False) as service:
            try:
                thread = service.users().threads().get(userId="me", id=payload.thread_id).execute()
                msgs = []
                subject = "(Không có tiêu đề)"
                for m in thread.get("messages", []):
                    headers = {
                        h["name"]: h["value"] for h in m.get("payload", {}).get("headers", [])
                    }
                    if "Subject" in headers and subject == "(Không có tiêu đề)":
                        subject = headers["Subject"]
                    body_text = extract_body(m.get("payload", {}))
                    msgs.append(
                        ThreadMessage(
                            id=m["id"],
                            sender=headers.get("From", "Không rõ"),
                            recipient=headers.get("To", "me"),
                            date=headers.get("Date", ""),
                            subject=headers.get("Subject", subject),
                            body=body_text[:10000],
                        )
                    )
                return GmailReadThreadOutput(
                    thread_id=payload.thread_id, subject=subject, messages=msgs
                )
            except HttpError as exc:
                raise handle_gmail_http_error(exc, "đọc email thread") from exc

    return await asyncio.to_thread(execute)


async def gmail_prepare_draft(
    payload: EmailPrepareInput, context: ToolContext
) -> EmailOperationResult:
    row = await asyncio.to_thread(
        operation_store(context).prepare,
        context.user.id,
        payload.request_key,
        "email_send",
        payload.model_dump(mode="json"),
    )
    return EmailOperationResult(
        data={
            "operation_id": row["id"],
            "state": row["state"],
            "digest": row["digest"],
            "preview": json.loads(row["spec"]),
            "expires_after_seconds": 1800,
        }
    )


async def gmail_send(payload: EmailApprovalInput, context: ToolContext) -> EmailOperationResult:
    store = operation_store(context)
    row = await asyncio.to_thread(store.get, context.user.id, payload.operation_id)
    if row["capability"] != "email_send":
        raise ToolError("Không phải thao tác gửi Email.", code="invalid_operation")

    spec_data = EmailPrepareInput.model_validate_json(row["spec"])
    if not secrets.compare_digest(row["digest"], payload.approved_digest):
        raise ToolError("Bản xác nhận không khớp nội dung đã xem.", code="digest_mismatch")
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)
    await asyncio.to_thread(store.claim, context.user.id, row["id"], payload.approved_digest)

    def execute() -> dict:
        send_attempted = False
        try:
            with build("gmail", "v1", credentials=credentials, cache_discovery=False) as service:
                message = MIMEMultipart()
                message["to"] = spec_data.draft.recipient
                message["subject"] = spec_data.draft.subject
                message.attach(MIMEText(spec_data.draft.body, "plain", "utf-8"))
                attachment_names = _attach_drive_files(
                    message,
                    credentials,
                    spec_data.draft.drive_file_ids,
                )

                raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
                send_attempted = True
                sent_msg = service.users().messages().send(userId="me", body={"raw": raw}).execute()

                result = {
                    "sent": True,
                    "message_id": sent_msg.get("id"),
                    "thread_id": sent_msg.get("threadId"),
                    "recipient": spec_data.draft.recipient,
                    "subject": spec_data.draft.subject,
                    "attachment_names": attachment_names,
                }
                store.finish(context.user.id, row["id"], result)
                return result
        except Exception as exc:
            code = "gmail_send_failed"
            if isinstance(exc, HttpError) and exc.resp.status in {401, 403}:
                code = "gmail_permission_denied"
            if send_attempted:
                store.uncertain(context.user.id, row["id"], code)
            else:
                store.fail(context.user.id, row["id"], code)
            logger.warning("Gmail send failed; type=%s code=%s", type(exc).__name__, code)
            raise ToolError(
                "Chưa xác minh gửi email hoàn tất. Hãy kiểm tra trạng thái thao tác; "
                "không gửi lại để tránh tạo thư trùng.",
                code=code,
            ) from None

    result_data = await asyncio.to_thread(execute)
    return EmailOperationResult(data={"operation_id": row["id"], **result_data})


def gmail_tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="gmail_list_messages",
            description=(
                "Tìm kiếm và liệt kê email trong Gmail theo bộ lọc như is:unread hoặc from:."
            ),
            input_model=GmailListInput,
            output_model=GmailListOutput,
            handler=gmail_list_messages,
            required_permissions={GMAIL_READ},
            required_oauth_scopes={GMAIL_READONLY_SCOPE},
            timeout_seconds=30,
        ),
        ToolDefinition(
            name="gmail_read_thread",
            description="Đọc các thư trong một chuỗi hội thoại Gmail theo thread_id.",
            input_model=GmailReadThreadInput,
            output_model=GmailReadThreadOutput,
            handler=gmail_read_thread,
            required_permissions={GMAIL_READ},
            required_oauth_scopes={GMAIL_READONLY_SCOPE},
            timeout_seconds=30,
        ),
        ToolDefinition(
            name="gmail_prepare_draft",
            description="Soạn bản nháp email để người dùng xem trước; chưa gửi ra ngoài.",
            input_model=EmailPrepareInput,
            output_model=EmailOperationResult,
            handler=gmail_prepare_draft,
            required_permissions={GMAIL_SEND},
            required_oauth_scopes={GMAIL_SEND_SCOPE, DRIVE_READONLY_SCOPE},
            requires_user_action=True,
            timeout_seconds=30,
        ),
        ToolDefinition(
            name="gmail_send",
            description="Gửi đúng bản email người dùng đã duyệt trên giao diện.",
            input_model=EmailApprovalInput,
            output_model=EmailOperationResult,
            handler=gmail_send,
            required_permissions={GMAIL_SEND},
            required_oauth_scopes={GMAIL_SEND_SCOPE, DRIVE_READONLY_SCOPE},
            requires_user_action=True,
            timeout_seconds=45,
        ),
    ]
