"""Gmail tools governed by 6-gate registry and 2-phase human-in-the-loop approval."""

import asyncio
import base64
import io
import json
import logging
import mimetypes
import re
import secrets
from collections.abc import Callable
from datetime import date, datetime, timedelta
from email import encoders
from email.header import decode_header, make_header
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, getaddresses, parseaddr
from html import unescape
from html.parser import HTMLParser
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.google_oauth import refresh_and_store_if_needed
from app.auth.permissions import GMAIL_DRAFT, GMAIL_READ, GMAIL_SEND
from app.services.inference_gateway import create_inference_client
from app.services.operations import OperationStore
from app.services.relational_operations import operation_store_for
from app.tools.contracts import OperationReference, ToolContext, ToolDefinition, ToolError

logger = logging.getLogger(__name__)

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_MODIFY_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
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
    return operation_store_for(context.settings)


def handle_gmail_http_error(exc: HttpError, action: str = "thao tác") -> ToolError:
    # Only the HTTP status is logged. SDK exception text may include request
    # URLs or private account details, so never write it to server logs.
    logger.warning("Gmail API rejected %s; status=%s", action, exc.status_code)
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
    status = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "resp", None), "status", 500
    )
    status = int(status)
    return ToolError(
        f"Gmail tạm thời không thể {action}.",
        code=f"gmail_{status}",
        retryable=status in {408, 429, 500, 502, 503, 504},
    )


class GmailListInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(default="is:unread", max_length=200)
    max_results: int = Field(default=10, ge=1, le=50)
    page_token: str | None = Field(default=None, min_length=1, max_length=500)


class EmailHeaderSummary(BaseModel):
    id: str
    thread_id: str
    sender: str
    subject: str
    date: str
    snippet: str
    unread: bool = False
    has_attachment: bool = False


class GmailListOutput(BaseModel):
    messages: list[EmailHeaderSummary]
    total_found: int
    total_is_estimate: bool = True
    next_page_token: str | None = None


class GmailReadMatchingInput(BaseModel):
    """One bounded, read-only gather for multi-email analysis."""

    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=200)
    local_date: date | None = None
    day_scope: Literal["any", "today"] = "any"
    timezone: str = Field(default="Asia/Bangkok", min_length=1, max_length=64)
    sender_address: str | None = Field(default=None, max_length=200)
    sender_name: str | None = Field(default=None, min_length=1, max_length=200)
    max_results: int = Field(default=12, ge=1, le=30)
    page_token: str | None = Field(default=None, min_length=1, max_length=500)


class GmailReadMatchingMessage(BaseModel):
    id: str
    thread_id: str
    sender: str
    subject: str
    date: str
    received_at_local: str
    body: str
    body_available: bool
    attachment_count: int
    inline_image_count: int
    has_html: bool


class GmailReadMatchingOutput(BaseModel):
    messages: list[GmailReadMatchingMessage]
    as_of_local: str
    next_page_token: str | None = None
    examined_count: int
    date_unverified_count: int
    future_excluded_count: int
    sender_mismatch_count: int
    local_day_mismatch_count: int
    unreadable_body_count: int
    note: str = (
        "Đã đọc phần văn bản MIME đầy đủ của các thư trả về; ảnh, tệp đính kèm "
        "và trang web được liên kết chưa được diễn giải."
    )


class GmailReadThreadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thread_id: str = Field(min_length=5, max_length=100)


class GmailAttachmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str = Field(min_length=5, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    attachment_id: str = Field(min_length=1, max_length=500)


class GmailAttachmentOutput(BaseModel):
    mime_type: str
    filename: str
    data_base64: str


class ThreadMessage(BaseModel):
    id: str
    sender: str
    recipient: str
    date: str
    subject: str
    body: str
    plain_body: str = ""
    html_body: str = ""
    presentation_mode: str = "unsupported"
    reply_to: str = ""
    message_id_header: str = ""
    references: str = ""
    unread: bool = False
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class GmailReadThreadOutput(BaseModel):
    thread_id: str
    subject: str
    messages: list[ThreadMessage]


class GmailSummaryOutput(BaseModel):
    bullets: list[str] = Field(min_length=3, max_length=3)


class EmailDraftSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient: str = Field(min_length=3, max_length=200)
    subject: str = Field(min_length=1, max_length=250)
    body: str = Field(min_length=1, max_length=50000)
    drive_file_ids: list[str] = Field(default_factory=list, max_length=5)
    cc: str = Field(default="", max_length=1000)
    bcc: str = Field(default="", max_length=1000)
    thread_id: str | None = Field(default=None, min_length=5, max_length=100)
    in_reply_to: str = Field(default="", max_length=500)
    references: str = Field(default="", max_length=2000)

    @field_validator("recipient", "cc", "bcc")
    @classmethod
    def validate_addresses(cls, value: str) -> str:
        clean = value.strip()
        if "\r" in clean or "\n" in clean:
            raise ValueError("Địa chỉ email không được chứa xuống dòng.")
        if not clean:
            return clean
        addresses = getaddresses([clean.replace(";", ",")])
        if not addresses or any(
            "@" not in address or address.startswith("@") for _, address in addresses
        ):
            raise ValueError("Địa chỉ email không hợp lệ.")
        return clean

    @field_validator("subject", "in_reply_to", "references")
    @classmethod
    def reject_header_injection(cls, value: str) -> str:
        if "\r" in value or "\n" in value:
            raise ValueError("Header email không được chứa xuống dòng.")
        return value.strip()


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


class GmailCreateDraftInput(BaseModel):
    """Input parameters to create a native draft in Gmail."""

    model_config = ConfigDict(extra="forbid")
    recipient: str = Field(
        default="",
        max_length=200,
        description="Địa chỉ email người nhận (mặc định gửi cho bạn nếu để trống)",
    )
    subject: str = Field(min_length=1, max_length=250, description="Tiêu đề email")
    body: str = Field(min_length=1, max_length=50000, description="Nội dung email dạng văn bản")
    cc: str = Field(default="", max_length=1000, description="Địa chỉ CC (nếu có)")
    bcc: str = Field(default="", max_length=1000, description="Địa chỉ BCC (nếu có)")
    thread_id: str | None = Field(
        default=None,
        max_length=100,
        description="Thread ID nếu tạo thư nháp trả lời theo luồng",
    )
    in_reply_to: str = Field(
        default="", max_length=500, description="Message-ID của thư cần trả lời"
    )
    references: str = Field(
        default="", max_length=2000, description="References header của chuỗi thư"
    )
    drive_file_ids: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Danh sách File ID trên Drive cần đính kèm",
    )

    @field_validator("recipient", "cc", "bcc")
    @classmethod
    def validate_addresses(cls, value: str) -> str:
        clean = value.strip()
        if "\r" in clean or "\n" in clean:
            raise ValueError("Địa chỉ email không được chứa xuống dòng.")
        if not clean or clean.casefold() == "me":
            return clean
        addresses = getaddresses([clean.replace(";", ",")])
        if not addresses or any(
            "@" not in address or address.startswith("@") for _, address in addresses
        ):
            raise ValueError("Địa chỉ email không hợp lệ.")
        return clean

    @field_validator("subject", "in_reply_to", "references")
    @classmethod
    def reject_header_injection(cls, value: str) -> str:
        if "\r" in value or "\n" in value:
            raise ValueError("Header email không được chứa xuống dòng.")
        return value.strip()


class GmailDraftPrepareInput(BaseModel):
    """Payload for preparing a native Gmail draft before explicit approval."""

    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(pattern=r"^[A-Za-z0-9_-]{8,100}$")
    draft: GmailCreateDraftInput


class GmailCreateDraftOutput(BaseModel):
    draft_id: str
    message_id: str
    thread_id: str | None = None
    recipient: str
    subject: str
    attachment_names: list[str] = Field(default_factory=list)
    gmail_draft_url: str = "https://mail.google.com/mail/u/0/#drafts"
    message: str


class _HtmlToText(HTMLParser):
    """Small dependency-free HTML email reader; scripts and styles stay hidden."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "head"}:
            self.hidden_depth += 1
        elif not self.hidden_depth and tag in {"p", "div", "br", "li", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "head"} and self.hidden_depth:
            self.hidden_depth -= 1
        elif not self.hidden_depth and tag in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def _decode_mime_header(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except (LookupError, UnicodeDecodeError):
        return value


def _format_address_header(value: str) -> str:
    return ", ".join(
        formataddr((display_name, address), charset="utf-8")
        for display_name, address in getaddresses([value.replace(";", ",")])
    )


def _html_to_text(value: str) -> str:
    parser = _HtmlToText()
    parser.feed(value)
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _decode_body(data: str, charset: str = "utf-8") -> str:
    try:
        padding = "=" * (-len(data) % 4)
        raw = base64.urlsafe_b64decode(data + padding)
        try:
            return raw.decode(charset or "utf-8", errors="replace")
        except LookupError:
            return raw.decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""


def _content_score(value: str) -> int:
    """Estimate useful reading content without letting tracking URLs dominate."""

    without_urls = re.sub(r"https?://\S+", " ", value)
    words = re.findall(r"[\wÀ-ỹ]{2,}", without_urls, flags=re.UNICODE)
    return sum(len(word) for word in words)


_TRACKING_PADDING = re.compile(
    r"[\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f"
    r"\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufe00-\ufe0f\ufeff]"
)


def _strip_tracking_padding(value: str) -> str:
    """Remove invisible email-preview padding while retaining normal accents."""

    # Marketing emails commonly insert default-ignorable Unicode characters to
    # pad preview text. They are invisible visually but create noisy accessible
    # names, copied text and model context. Ordinary combining accents are not
    # removed; this list contains only known formatting/joiner code points.
    return _TRACKING_PADDING.sub("", unescape(str(value)))


def _clean_snippet(value: str) -> str:
    """Turn Gmail's one-line preview into compact, readable text."""

    return " ".join(_strip_tracking_padding(value).split())


def _clean_body_text(value: str) -> str:
    """Clean tracking padding from a body without flattening its paragraphs."""

    cleaned = _strip_tracking_padding(value).replace("\r\n", "\n").replace("\r", "\n")

    def _clean_url(match: re.Match[str]) -> str:
        url = match.group(0)
        if any(marker in url for marker in ("elqTrack", "elq=", "utm_", "trk=")) and len(url) > 90:
            from urllib.parse import urlsplit, urlunsplit

            parts = urlsplit(url)
            clean_query = "&".join(
                q for q in parts.query.split("&")
                if not any(q.startswith(m) for m in ("elq", "utm_", "trk="))
            )
            return urlunsplit((parts.scheme, parts.netloc, parts.path, clean_query, parts.fragment))
        return url

    cleaned = re.sub(r"https?://[^\s<>\"']+", _clean_url, cleaned)
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in cleaned.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _part_charset(part: dict) -> str:
    """Read the declared MIME charset without trusting arbitrary headers as code."""

    for header in part.get("headers", []) or []:
        if str(header.get("name", "")).casefold() != "content-type":
            continue
        match = re.search(r"charset\s*=\s*[\"']?([^;\"'\s]+)", str(header.get("value", "")), re.I)
        if match:
            return match.group(1)
    return str((part.get("body") or {}).get("charset") or "utf-8")


def _calendar_to_readable(value: str) -> str:
    """Render common iCalendar invitation fields as readable text without HTML."""
    unfolded: list[str] = []
    for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        elif line:
            unfolded.append(line)

    labels = {
        "SUMMARY": "Tiêu đề",
        "DTSTART": "Bắt đầu",
        "DTEND": "Kết thúc",
        "LOCATION": "Địa điểm",
        "DESCRIPTION": "Mô tả",
        "ORGANIZER": "Người tổ chức",
        "ATTENDEE": "Người tham dự",
        "URL": "Liên kết",
        "STATUS": "Trạng thái",
    }
    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in unfolded:
        if line.upper() == "BEGIN:VEVENT":
            current = {}
            events.append(current)
            continue
        if line.upper() == "END:VEVENT":
            current = None
            continue
        if current is None or ":" not in line:
            continue
        raw_key, raw_value = line.split(":", 1)
        key = raw_key.split(";", 1)[0].upper()
        if key not in labels:
            continue
        text = re.sub(r"\\([nN])", "\n", raw_value)
        text = re.sub(r"\\([\\,;])", r"\1", text).strip()
        if key in {"DTSTART", "DTEND"}:
            match = re.fullmatch(r"(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2})(Z)?)?", text)
            if match:
                year, month, day, hour, minute, second, utc = match.groups()
                text = f"{day}/{month}/{year}"
                if hour:
                    text += f" {hour}:{minute}:{second}" + (" UTC" if utc else "")
        label = labels[key]
        if key == "ATTENDEE" and label in current:
            current[label] += f"\n{text}"
        else:
            current[label] = text

    if not events:
        return value.strip()
    rendered: list[str] = []
    for index, event in enumerate(events, start=1):
        if len(events) > 1:
            rendered.append(f"Sự kiện {index}")
        rendered.extend(f"{key}: {content}" for key, content in event.items())
        if index < len(events):
            rendered.append("")
    return "\n".join(rendered)


def _extract_message_content(
    payload: dict,
    attachment_loader: Callable[[str], str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Extract readable text while preserving metadata for every downloadable part."""

    plain: list[str] = []
    html: list[str] = []
    attachments: list[dict[str, Any]] = []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        filename = part.get("filename", "")
        headers = {
            str(header.get("name", "")).casefold(): str(header.get("value", ""))
            for header in part.get("headers", []) or []
        }
        content_id = headers.get("content-id", "").strip().strip("<>")
        disposition = headers.get("content-disposition", "").casefold()
        is_inline_image = str(mime).casefold().startswith("image/") and (
            bool(content_id) or "inline" in disposition
        )
        has_non_text_attachment = body.get("attachmentId") and not str(mime).startswith("text/")
        if filename or is_inline_image or has_non_text_attachment:
            attachment = {
                "filename": filename or (
                    content_id or f"Tệp đính kèm ({mime or 'không rõ định dạng'})"
                ),
                "mime_type": mime or "application/octet-stream",
                "size": int(body.get("size") or 0),
                # Gmail can return a different opaque attachmentId for the same
                # MIME part in threads.get versus messages.get. The partId is
                # stable within the verified message; resolve it to the current
                # attachmentId only after loading that message again.
                "attachment_id": (
                    f"part:{part['partId']}"
                    if body.get("attachmentId") and part.get("partId")
                    else body.get("attachmentId")
                ),
            }
            if content_id or is_inline_image:
                attachment["content_id"] = content_id or None
                attachment["inline"] = is_inline_image
            if is_inline_image and body.get("data"):
                try:
                    raw = base64.urlsafe_b64decode(
                        str(body["data"]) + "=" * (-len(str(body["data"])) % 4)
                    )
                    if 0 < len(raw) <= 2 * 1024 * 1024:
                        attachment["data_base64"] = base64.b64encode(raw).decode("ascii")
                except (ValueError, TypeError):
                    pass
            attachments.append(attachment)
        elif mime in {"text/plain", "text/html", "text/calendar"} and (
            body.get("data") or (body.get("attachmentId") and attachment_loader)
        ):
            encoded = body.get("data")
            if not encoded and attachment_loader:
                encoded = attachment_loader(str(body["attachmentId"]))
            decoded = _decode_body(encoded or "", _part_charset(part))
            if mime == "text/plain":
                plain.append(decoded)
            elif mime == "text/calendar":
                plain.append(_calendar_to_readable(decoded))
            elif mime == "text/html":
                html.append(decoded)
        for child in part.get("parts", []):
            walk(child)

    walk(payload)
    plain_text = "\n\n".join(item.strip() for item in plain if item.strip())
    html_text = _html_to_text("\n".join(html))
    plain_score = _content_score(plain_text)
    html_score = _content_score(html_text)
    # HTML must be convincingly richer before it replaces the safer plain body.
    text = html_text if html_score >= max(plain_score * 2, plain_score + 240) else plain_text
    if not text:
        text = html_text
    return _clean_body_text(text), attachments


def _can_render_faithfully(payload: dict) -> bool:
    """Only claim fidelity for a real plain-text MIME body.

    HTML mail is intentionally classified as unsupported. Rebuilding it after
    Gmail sanitization, image proxying and CSS rewriting cannot honestly be
    called identical to Gmail's renderer.
    """

    mime_types: list[str] = []

    def walk(part: dict) -> None:
        mime = str(part.get("mimeType") or "")
        body = part.get("body") or {}
        if mime.startswith("text/") and (body.get("data") or body.get("attachmentId")):
            mime_types.append(mime)
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    return bool(mime_types) and all(mime == "text/plain" for mime in mime_types)


def _presentation_for_message(
    payload: dict, extracted_text: str, exact_plain: str, html_body: str = ""
) -> tuple[str, str]:
    """Prefer the original HTML MIME representation, otherwise render its text part."""

    if html_body.strip():
        return "safe_html", exact_plain or extracted_text

    if extracted_text.strip() and _payload_has_mime(payload, {"text/calendar"}):
        return "calendar_text", extracted_text

    if _can_render_faithfully(payload) and exact_plain.strip():
        return "faithful_text", exact_plain
    if extracted_text.strip():
        return "readable_text", extracted_text
    return "unsupported", ""


def _payload_has_mime(payload: dict, expected: set[str]) -> bool:
    found = False

    def walk(part: dict) -> None:
        nonlocal found
        if str(part.get("mimeType") or "").casefold() in expected:
            found = True
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    return found


def _can_render_readably(payload: dict) -> bool:
    """Return whether the MIME structure has a text representation we can show."""

    html_parts: list[str] = []
    allowed_mimes = {
        "text/plain", "text/html", "text/calendar", "multipart/alternative",
        "multipart/mixed", "multipart/related", "multipart/signed",
    }

    def walk(part: dict) -> bool:
        mime = str(part.get("mimeType") or "").casefold()
        body = part.get("body") or {}
        if part.get("filename"):
            return True
        if mime and mime not in allowed_mimes:
            if mime.startswith("multipart/"):
                pass
            elif mime.startswith("image/"):
                pass
            else:
                return False
        if mime == "text/html" and body.get("data"):
            html_parts.append(_decode_body(str(body["data"]), _part_charset(part)))
        return all(walk(child) for child in part.get("parts", []) or [])

    if not walk(payload):
        return False
    return bool(html_parts) or bool(payload.get("mimeType", "").startswith("text/"))


def _extract_plain_body_exact(
    payload: dict,
    attachment_loader: Callable[[str], str] | None = None,
) -> str:
    """Decode plain MIME parts without rewriting whitespace, URLs or wording."""

    parts: list[str] = []

    def walk(part: dict) -> None:
        body = part.get("body") or {}
        if part.get("mimeType") == "text/plain" and not part.get("filename"):
            encoded = body.get("data")
            if not encoded and body.get("attachmentId") and attachment_loader:
                encoded = attachment_loader(str(body["attachmentId"]))
            if encoded:
                parts.append(_decode_body(str(encoded), _part_charset(part)))
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    return "\n".join(parts)


def _extract_html_body(
    payload: dict,
    attachment_loader: Callable[[str], str] | None = None,
) -> str:
    """Decode raw HTML MIME parts if present."""

    parts: list[str] = []

    def walk(part: dict) -> None:
        body = part.get("body") or {}
        if part.get("mimeType") == "text/html" and not part.get("filename"):
            encoded = body.get("data")
            if not encoded and body.get("attachmentId") and attachment_loader:
                encoded = attachment_loader(str(body["attachmentId"]))
            if encoded:
                parts.append(_decode_body(str(encoded), _part_charset(part)))
        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    return "\n".join(parts).strip()


def _validate_summary_response(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
        bullets = [" ".join(str(item).split()) for item in parsed.get("bullets", [])]
    except (ValueError, TypeError, AttributeError) as exc:
        raise ToolError("Gemini trả về bản tóm tắt không hợp lệ.", code="invalid_summary") from exc
    if len(bullets) != 3 or any(not item or len(item) > 300 for item in bullets):
        raise ToolError("Gemini chưa tạo đúng 3 ý tóm tắt.", code="invalid_summary")
    return bullets


def _first_external_address(*values: str, own_email: str = "") -> str:
    """Pick a safe reply target, never the authenticated user's own address."""

    own = own_email.strip().casefold()
    for value in values:
        for display_name, address in getaddresses([value.replace(";", ",")]):
            clean = address.strip()
            if clean and "@" in clean and clean.casefold() != own:
                return formataddr((display_name, clean)) if display_name else clean
    return ""


def _load_gmail_attachment(service, message_id: str, attachment_id: str) -> str:
    response = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
        .execute()
    )
    encoded = str(response.get("data") or "")
    if not encoded:
        return ""
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (ValueError, TypeError):
        return ""
    # Gmail attachments can be large; a body part is still bounded before it reaches the model.
    if len(raw) > 2 * 1024 * 1024:
        return ""
    return base64.urlsafe_b64encode(raw).decode("ascii")


async def gmail_get_attachment(
    payload: GmailAttachmentInput, context: ToolContext
) -> GmailAttachmentOutput:
    """Read one attachment after verifying it belongs to the requested Gmail message."""
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)

    def execute() -> GmailAttachmentOutput:
        with build("gmail", "v1", credentials=credentials, cache_discovery=False) as service:
            try:
                message = (
                    service.users().messages().get(
                        userId="me", id=payload.message_id, format="full"
                    ).execute()
                )
                matching: dict[str, Any] | None = None
                stable_part_id = (
                    payload.attachment_id[5:]
                    if payload.attachment_id.startswith("part:")
                    else None
                )

                def walk(part: dict[str, Any]) -> None:
                    nonlocal matching
                    body = part.get("body") or {}
                    if body.get("attachmentId") and (
                        (stable_part_id is not None and part.get("partId") == stable_part_id)
                        or body.get("attachmentId") == payload.attachment_id
                    ):
                        matching = part
                        return
                    for child in part.get("parts", []) or []:
                        walk(child)

                walk(message.get("payload", {}))
                if not matching:
                    raise ToolError(
                        "Không tìm thấy tệp đính kèm trong thư này.",
                        code="attachment_not_found",
                    )
                mime_type = str(matching.get("mimeType") or "application/octet-stream").casefold()
                filename = str(matching.get("filename") or "attachment")[:240]
                encoded = str((matching.get("body") or {}).get("data") or "")
                if not encoded:
                    current_attachment_id = str((matching.get("body") or {})["attachmentId"])
                    result = (
                        service.users().messages().attachments().get(
                            userId="me", messageId=payload.message_id,
                            id=current_attachment_id,
                        ).execute()
                    )
                    encoded = str(result.get("data") or "")
                try:
                    padding = "=" * (-len(encoded) % 4)
                    raw = base64.urlsafe_b64decode(encoded + padding)
                except (ValueError, TypeError) as exc:
                    raise ToolError(
                        "Tệp đính kèm không thể giải mã.", code="attachment_invalid"
                    ) from exc
                if not raw:
                    raise ToolError("Tệp đính kèm rỗng.", code="attachment_empty")
                if len(raw) > MAX_ATTACHMENT_BYTES:
                    raise ToolError(
                        "Tệp đính kèm vượt giới hạn 15 MB.", code="attachment_too_large"
                    )
                return GmailAttachmentOutput(
                    mime_type=mime_type,
                    filename=filename,
                    data_base64=base64.b64encode(raw).decode("ascii"),
                )
            except HttpError as exc:
                raise handle_gmail_http_error(exc, "đọc tệp đính kèm Gmail") from exc

    return await asyncio.to_thread(execute)


def _build_send_payload(draft: EmailDraftSpec, credentials) -> tuple[dict[str, str], list[str]]:
    """Build the exact RFC message and Gmail thread binding covered by approval."""

    message = MIMEMultipart()
    message["to"] = _format_address_header(draft.recipient)
    message["subject"] = draft.subject
    if draft.cc:
        message["cc"] = _format_address_header(draft.cc)
    if draft.bcc:
        message["bcc"] = _format_address_header(draft.bcc)
    if draft.in_reply_to:
        message["In-Reply-To"] = draft.in_reply_to
    if draft.references:
        message["References"] = draft.references
    message.attach(MIMEText(draft.body, "plain", "utf-8"))
    attachment_names = _attach_drive_files(message, credentials, draft.drive_file_ids)
    payload = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")}
    if draft.thread_id:
        payload["threadId"] = draft.thread_id
    return payload, attachment_names


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
                    .list(
                        userId="me",
                        q=payload.query,
                        maxResults=payload.max_results,
                        pageToken=payload.page_token,
                    )
                    .execute()
                )
                items = res.get("messages", [])
                total = res.get("resultSizeEstimate", len(items))
                page_items = items[: payload.max_results]
                if not page_items:
                    return GmailListOutput(
                        messages=[],
                        total_found=total,
                        next_page_token=res.get("nextPageToken"),
                    )
                attachment_query = " ".join(
                    part for part in (payload.query.strip(), "has:attachment") if part
                )
                attachment_res = (
                    service.users()
                    .messages()
                    .list(userId="me", q=attachment_query, maxResults=500)
                    .execute()
                )
                attachment_ids = {item["id"] for item in attachment_res.get("messages", [])}

                def load_summary(item: dict[str, Any]) -> EmailHeaderSummary:
                    msg = (
                        service.users()
                        .messages()
                        .get(
                            userId="me",
                            id=item["id"],
                            # Keep inbox listing light. Full MIME content is fetched
                            # only after the user explicitly opens a thread.
                            format="metadata",
                            metadataHeaders=["From", "Subject", "Date"],
                        )
                        .execute()
                    )
                    headers = {
                        h["name"].casefold(): _decode_mime_header(h["value"])
                        for h in msg.get("payload", {}).get("headers", [])
                    }
                    labels = set(msg.get("labelIds", []))
                    return EmailHeaderSummary(
                        id=msg["id"],
                        thread_id=msg.get("threadId", msg["id"]),
                        sender=headers.get("from", "Không rõ"),
                        subject=headers.get("subject", "(Không có tiêu đề)"),
                        date=headers.get("date", ""),
                        snippet=_clean_snippet(msg.get("snippet", "")),
                        unread="UNREAD" in labels,
                        has_attachment=msg["id"] in attachment_ids,
                    )

                # Gmail metadata reads are independent. Batch them into one API
                # request when the discovery client supports it; retain the
                # sequential path for test doubles, older clients, and any
                # batch transport failure. This is read-only and preserves the
                # exact response ordering expected by the UI.
                batch_factory = getattr(service, "new_batch_http_request", None)
                if not callable(batch_factory) or len(page_items) == 1:
                    summaries = [load_summary(item) for item in page_items]
                else:
                    responses: dict[str, dict[str, Any]] = {}
                    failures: dict[str, Exception] = {}
                    batch = batch_factory()

                    def on_metadata(
                        request_id: str,
                        response: dict[str, Any] | None,
                        exception: Exception | None,
                    ) -> None:
                        if exception:
                            failures[request_id] = exception
                        elif response is not None:
                            responses[request_id] = response

                    try:
                        for item in page_items:
                            batch.add(
                                service.users()
                                .messages()
                                .get(
                                    userId="me",
                                    id=item["id"],
                                    format="metadata",
                                    metadataHeaders=["From", "Subject", "Date"],
                                ),
                                callback=on_metadata,
                                request_id=item["id"],
                            )
                        batch.execute()
                    except Exception:
                        logger.info(
                            "Gmail metadata batch failed; retrying sequentially",
                            exc_info=True,
                        )
                        summaries = [load_summary(item) for item in page_items]
                    else:
                        if failures:
                            raise next(iter(failures.values()))
                        if len(responses) != len(page_items):
                            raise ToolError(
                                "Gmail trả về thiếu metadata thư; vui lòng thử lại.",
                                code="gmail_metadata_incomplete",
                            )

                        def summary_from_response(msg: dict[str, Any]) -> EmailHeaderSummary:
                            headers = {
                                h["name"].casefold(): _decode_mime_header(h["value"])
                                for h in msg.get("payload", {}).get("headers", [])
                            }
                            labels = set(msg.get("labelIds", []))
                            return EmailHeaderSummary(
                                id=msg["id"],
                                thread_id=msg.get("threadId", msg["id"]),
                                sender=headers.get("from", "Không rõ"),
                                subject=headers.get("subject", "(Không có tiêu đề)"),
                                date=headers.get("date", ""),
                                snippet=_clean_snippet(msg.get("snippet", "")),
                                unread="UNREAD" in labels,
                                has_attachment=msg["id"] in attachment_ids,
                            )

                        summaries = [
                            summary_from_response(responses[item["id"]]) for item in page_items
                        ]
                return GmailListOutput(
                    messages=summaries,
                    total_found=total,
                    next_page_token=res.get("nextPageToken"),
                )
            except HttpError as exc:
                raise handle_gmail_http_error(exc, "tìm kiếm email") from exc

    return await asyncio.to_thread(execute)


def _sender_display_name_matches(actual: str, expected: str) -> bool:
    """Accept a reordered full display name, never a partial-name match.

    Gmail headers in the connected mailbox use “Bảo Phúc Đinh”, while the
    owner may say “Đinh Bảo Phúc”. This is only a name check; callers should
    also provide sender_address when they require address-level identity.
    """

    actual_parts = actual.casefold().split()
    expected_parts = expected.casefold().split()
    return bool(actual_parts) and (
        actual_parts == expected_parts
        or (len(actual_parts) > 1 and sorted(actual_parts) == sorted(expected_parts))
    )


async def gmail_read_matching_messages(
    payload: GmailReadMatchingInput, context: ToolContext
) -> GmailReadMatchingOutput:
    """Read a bounded page of full text in one governed tool call.

    This avoids an LLM/tool round trip per email for reusable multi-email skills.
    It never returns raw HTML or attachment bytes to the model, never changes
    Gmail state, and fails closed rather than silently truncating source text.
    """

    try:
        timezone = ZoneInfo(payload.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ToolError("Múi giờ Gmail không hợp lệ.", code="invalid_timezone") from exc
    as_of = datetime.now(timezone)
    target_date = as_of.date() if payload.day_scope == "today" else payload.local_date
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)

    def execute() -> GmailReadMatchingOutput:
        with build("gmail", "v1", credentials=credentials, cache_discovery=False) as service:
            try:
                query = payload.query
                if target_date is not None:
                    start = datetime.combine(target_date, datetime.min.time(), timezone)
                    end = datetime.combine(
                        target_date + timedelta(days=1), datetime.min.time(), timezone
                    )
                    # Gmail treats textual dates as Pacific midnight. Seconds
                    # preserve the user's local day; the extra second ensures
                    # a message received exactly at midnight is not lost.
                    query += (
                        f" after:{int(start.timestamp()) - 1}"
                        f" before:{int(end.timestamp())}"
                    )
                items: list[dict[str, Any]] = []
                seen_message_ids: set[str] = set()
                seen_page_tokens: set[str] = set()
                next_page_token = payload.page_token
                max_pages = 5 if payload.day_scope == "today" else 1
                for _ in range(max_pages):
                    if next_page_token and next_page_token in seen_page_tokens:
                        break
                    if next_page_token:
                        seen_page_tokens.add(next_page_token)
                    page = (
                        service.users()
                        .messages()
                        .list(
                            userId="me",
                            q=query,
                            maxResults=min(payload.max_results, 100 - len(items)),
                            pageToken=next_page_token,
                        )
                        .execute()
                    )
                    for item in page.get("messages", []):
                        message_id = str(item.get("id") or "")
                        if message_id and message_id not in seen_message_ids:
                            seen_message_ids.add(message_id)
                            items.append(item)
                    next_page_token = page.get("nextPageToken")
                    if not next_page_token or len(items) >= 100:
                        break
                rows: list[GmailReadMatchingMessage] = []
                unverified_dates = 0
                future_excluded = 0
                sender_mismatch = 0
                local_day_mismatch = 0
                unreadable_bodies = 0
                total_body_bytes = 0
                for item in items:
                    message = (
                        service.users()
                        .messages()
                        .get(userId="me", id=item["id"], format="full")
                        .execute()
                    )
                    headers = {
                        h["name"].casefold(): _decode_mime_header(h["value"])
                        for h in message.get("payload", {}).get("headers", [])
                    }
                    sender = headers.get("from", "Không rõ")
                    if payload.sender_address and (
                        parseaddr(sender)[1].casefold() != payload.sender_address.casefold()
                    ):
                        sender_mismatch += 1
                        continue
                    if payload.sender_name and (
                        not _sender_display_name_matches(
                            parseaddr(sender)[0], payload.sender_name
                        )
                    ):
                        sender_mismatch += 1
                        continue
                    try:
                        received_at = datetime.fromtimestamp(
                            int(message["internalDate"]) / 1000, timezone
                        )
                    except (KeyError, TypeError, ValueError, OverflowError):
                        unverified_dates += 1
                        continue
                    if received_at > as_of:
                        future_excluded += 1
                        continue
                    if target_date is not None and received_at.date() != target_date:
                        local_day_mismatch += 1
                        continue
                    body, attachments = _extract_message_content(
                        message.get("payload", {}),
                        attachment_loader=lambda attachment_id, message_id=message["id"]: (
                            _load_gmail_attachment(service, message_id, attachment_id)
                        ),
                    )
                    total_body_bytes += len(body.encode("utf-8"))
                    if total_body_bytes > 90_000:
                        raise ToolError(
                            "Các email phù hợp quá dài để đọc trọn vẹn trong một lượt. "
                            "Hãy thu hẹp ngày hoặc bộ lọc, rồi thử lại.",
                            code="gmail_multi_read_too_large",
                        )
                    unreadable_bodies += not bool(body.strip())
                    rows.append(
                        GmailReadMatchingMessage(
                            id=message["id"],
                            thread_id=message.get("threadId", message["id"]),
                            sender=sender,
                            subject=headers.get("subject", "(Không có tiêu đề)"),
                            date=headers.get("date", ""),
                            received_at_local=received_at.isoformat(timespec="seconds"),
                            body=body,
                            body_available=bool(body.strip()),
                            attachment_count=len(attachments),
                            inline_image_count=sum(
                                1 for attachment in attachments if attachment.get("inline")
                            ),
                            has_html=_payload_has_mime(
                                message.get("payload", {}), {"text/html"}
                            ),
                        )
                    )
                return GmailReadMatchingOutput(
                    messages=rows,
                    as_of_local=as_of.isoformat(timespec="seconds"),
                    next_page_token=next_page_token,
                    examined_count=len(items),
                    date_unverified_count=unverified_dates,
                    future_excluded_count=future_excluded,
                    sender_mismatch_count=sender_mismatch,
                    local_day_mismatch_count=local_day_mismatch,
                    unreadable_body_count=unreadable_bodies,
                )
            except HttpError as exc:
                raise handle_gmail_http_error(exc, "đọc nhiều email") from exc

    return await asyncio.to_thread(execute)


async def gmail_read_thread(
    payload: GmailReadThreadInput, context: ToolContext
) -> GmailReadThreadOutput:
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)

    def execute() -> GmailReadThreadOutput:
        with build("gmail", "v1", credentials=credentials, cache_discovery=False) as service:
            try:
                thread = service.users().threads().get(userId="me", id=payload.thread_id).execute()
                msgs = []
                subject = "(Không có tiêu đề)"
                for m in thread.get("messages", []):
                    headers = {
                        h["name"].casefold(): _decode_mime_header(h["value"])
                        for h in m.get("payload", {}).get("headers", [])
                    }
                    if "subject" in headers and subject == "(Không có tiêu đề)":
                        subject = headers["subject"]
                    body_text, attachments = _extract_message_content(
                        m.get("payload", {}),
                        attachment_loader=lambda attachment_id, message_id=m["id"]: (
                            _load_gmail_attachment(service, message_id, attachment_id)
                        ),
                    )
                    exact_plain = _extract_plain_body_exact(
                        m.get("payload", {}),
                        attachment_loader=lambda attachment_id, message_id=m["id"]: (
                            _load_gmail_attachment(service, message_id, attachment_id)
                        ),
                    )
                    html_body = _extract_html_body(
                        m.get("payload", {}),
                        attachment_loader=lambda attachment_id, message_id=m["id"]: (
                            _load_gmail_attachment(service, message_id, attachment_id)
                        ),
                    )
                    presentation_mode, display_body = _presentation_for_message(
                        m.get("payload", {}), body_text, exact_plain, html_body
                    )
                    reply_to = _first_external_address(
                        headers.get("reply-to", ""),
                        headers.get("from", ""),
                        own_email=getattr(context.user, "email", ""),
                    )
                    msgs.append(
                        ThreadMessage(
                            id=m["id"],
                            sender=headers.get("from", "Không rõ"),
                            recipient=headers.get("to", "me"),
                            date=headers.get("date", ""),
                            subject=headers.get("subject", subject),
                            body=display_body,
                            plain_body=exact_plain,
                            html_body=html_body,
                            presentation_mode=presentation_mode,
                            reply_to=reply_to,
                            message_id_header=headers.get("message-id", ""),
                            references=headers.get("references", ""),
                            unread="UNREAD" in set(m.get("labelIds", [])),
                            attachments=attachments,
                        )
                    )
                return GmailReadThreadOutput(
                    thread_id=payload.thread_id, subject=subject, messages=msgs
                )
            except HttpError as exc:
                raise handle_gmail_http_error(exc, "đọc email thread") from exc

    return await asyncio.to_thread(execute)


async def gmail_summarize_thread(
    payload: GmailReadThreadInput, context: ToolContext
) -> GmailSummaryOutput:
    """Summarize the full readable thread only after an explicit UI action."""

    if not context.settings.gemini_is_configured:
        raise ToolError("Chưa cấu hình Gemini để tóm tắt email.", code="gemini_not_configured")
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)

    def load_full_thread() -> str:
        with build("gmail", "v1", credentials=credentials, cache_discovery=False) as service:
            try:
                thread = service.users().threads().get(userId="me", id=payload.thread_id).execute()
                sections: list[str] = []
                for index, message in enumerate(thread.get("messages", []), start=1):
                    headers = {
                        h["name"].casefold(): _decode_mime_header(h["value"])
                        for h in message.get("payload", {}).get("headers", [])
                    }
                    body_text, _ = _extract_message_content(
                        message.get("payload", {}),
                        attachment_loader=lambda attachment_id, message_id=message["id"]: (
                            _load_gmail_attachment(service, message_id, attachment_id)
                        ),
                    )
                    sections.append(
                        f"THƯ {index}\nNgười gửi: {headers.get('from', 'Không rõ')}\n"
                        f"Tiêu đề: {headers.get('subject', '')}\nNội dung:\n{body_text}"
                    )
                full_thread = "\n\n".join(sections)
                if len(full_thread) > 120000:
                    raise ToolError(
                        "Chuỗi email quá dài để tóm tắt trọn vẹn; hãy mở thư gốc trong Gmail.",
                        code="email_too_large_for_summary",
                    )
                return full_thread
            except HttpError as exc:
                raise handle_gmail_http_error(exc, "đọc email để tóm tắt") from exc

    full_text = await asyncio.to_thread(load_full_thread)
    if not full_text.strip():
        raise ToolError("Email không có nội dung văn bản để tóm tắt.", code="empty_email")

    prompt = (
        "Đọc toàn bộ chuỗi email bên dưới và tóm tắt đúng 3 ý chính bằng tiếng Việt. "
        "Mỗi ý là một câu ngắn, cụ thể, nêu nội dung, quyết định hoặc việc cần làm. "
        "Không chép ba câu đầu, không suy đoán, không thêm lời mở đầu. "
        "Trả về JSON duy nhất theo mẫu {\"bullets\":[\"...\",\"...\",\"...\"]}.\n\n"
        + full_text
    )
    client = create_inference_client(
        settings=context.settings,
        api_key=context.settings.gemini_api_key,
        data_dir=context.settings.data_dir,
        client_factory=genai.Client,
    )
    try:
        response = await client.aio.models.generate_content(
            model=context.settings.gemini_chat_model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=512,
                response_mime_type="application/json",
                automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
    except genai_errors.APIError as exc:
        raise ToolError(
            "Gemini chưa thể tóm tắt email lúc này.",
            code="gemini_summary_error",
            retryable=True,
        ) from exc
    except Exception as exc:
        raise ToolError(
            "Không kết nối được Gemini để tóm tắt email.",
            code="gemini_summary_unavailable",
            retryable=True,
        ) from exc
    finally:
        await client.aio.aclose()
    return GmailSummaryOutput(bullets=_validate_summary_response(response.text or ""))


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
            "result": json.loads(row["result"]) if row["result"] else None,
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
                send_body, attachment_names = _build_send_payload(spec_data.draft, credentials)
                send_attempted = True
                sent_msg = service.users().messages().send(userId="me", body=send_body).execute()

                result = {
                    "sent": True,
                    "message_id": sent_msg.get("id"),
                    "recipient": spec_data.draft.recipient,
                    "subject": spec_data.draft.subject,
                    "cc": spec_data.draft.cc,
                    "thread_id": sent_msg.get("threadId"),
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


async def gmail_prepare_native_draft(
    payload: GmailDraftPrepareInput, context: ToolContext
) -> EmailOperationResult:
    """Store an immutable Gmail-draft preview without touching Google."""

    row = await asyncio.to_thread(
        operation_store(context).prepare,
        context.user.id,
        payload.request_key,
        "gmail_draft_create",
        payload.draft.model_dump(mode="json"),
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


async def gmail_create_draft(
    payload: EmailApprovalInput, context: ToolContext
) -> GmailCreateDraftOutput:
    """Create a native Gmail draft only after approval of its saved digest."""
    store = operation_store(context)
    row = await asyncio.to_thread(store.get, context.user.id, payload.operation_id)
    if row["capability"] != "gmail_draft_create":
        raise ToolError("Không phải thao tác tạo thư nháp Gmail.", code="invalid_operation")
    if not secrets.compare_digest(row["digest"], payload.approved_digest):
        raise ToolError("Bản xác nhận không khớp nội dung đã xem.", code="digest_mismatch")
    draft_input = GmailCreateDraftInput.model_validate_json(row["spec"])
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)

    await asyncio.to_thread(store.claim, context.user.id, row["id"], payload.approved_digest)
    target_recipient = draft_input.recipient.strip()
    if not target_recipient or target_recipient.casefold() == "me":
        target_recipient = getattr(context.user, "email", "") or "me"

    def execute() -> GmailCreateDraftOutput:
        side_effect_started = False
        try:
            with build("gmail", "v1", credentials=credentials, cache_discovery=False) as service:
                draft_spec = EmailDraftSpec(
                    recipient=target_recipient,
                    subject=draft_input.subject,
                    body=draft_input.body,
                    cc=draft_input.cc,
                    bcc=draft_input.bcc,
                    thread_id=draft_input.thread_id,
                    in_reply_to=draft_input.in_reply_to,
                    references=draft_input.references,
                    drive_file_ids=draft_input.drive_file_ids,
                )
                send_body, attachment_names = _build_send_payload(draft_spec, credentials)
                side_effect_started = True
                draft_res = (
                    service.users()
                    .drafts()
                    .create(userId="me", body={"message": send_body})
                    .execute()
                )
                draft_id = str(draft_res.get("id") or "")
                msg = draft_res.get("message", {})
                message_id = str(msg.get("id") or "")
                thread_id = msg.get("threadId") or draft_input.thread_id
                draft_url = "https://mail.google.com/mail/u/0/#drafts"
                result = GmailCreateDraftOutput(
                    draft_id=draft_id,
                    message_id=message_id,
                    thread_id=thread_id,
                    recipient=target_recipient,
                    subject=draft_input.subject,
                    attachment_names=attachment_names,
                    gmail_draft_url=draft_url,
                    message=(
                        f"Đã tạo thư nháp thành công trong Gmail (ID: {draft_id}). "
                        f"Bạn có thể mở và kiểm tra tại: {draft_url}"
                    ),
                )
                store.checkpoint(context.user.id, row["id"], draft_id)
                store.finish(context.user.id, row["id"], result.model_dump(mode="json"))
                return result
        except Exception as exc:
            error_code = "gmail_draft_create_failed"
            if isinstance(exc, HttpError) and exc.resp.status in {401, 403}:
                error_code = "gmail_permission_denied"
            if side_effect_started:
                store.uncertain(context.user.id, row["id"], error_code)
            else:
                store.fail(context.user.id, row["id"], error_code)
            logger.warning(
                "Gmail draft creation failed; type=%s code=%s",
                type(exc).__name__,
                error_code,
            )
            raise ToolError(
                "Chưa xác minh tạo thư nháp hoàn tất. Hãy kiểm tra trạng thái thao tác "
                "trước khi tạo lại.",
                code=error_code,
            ) from None

    return await asyncio.to_thread(execute)


async def gmail_reconcile_draft(
    payload: OperationReference, context: ToolContext
) -> EmailOperationResult:
    """Read back an uncertain native draft; never create or send another message."""

    store = operation_store(context)
    row = await asyncio.to_thread(store.get, context.user.id, payload.operation_id)
    if row["state"] != "uncertain" or row["capability"] != "gmail_draft_create":
        raise ToolError("Thao tác Gmail không thể đối soát.", code="invalid_operation")
    if not row["resource_id"]:
        raise ToolError("Chưa có Draft ID để đọc lại.", code="reconcile_unavailable")
    expected = GmailCreateDraftInput.model_validate_json(row["spec"])
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)

    def reconcile() -> EmailOperationResult:
        with build("gmail", "v1", credentials=credentials, cache_discovery=False) as service:
            actual = (
                service.users()
                .drafts()
                .get(userId="me", id=row["resource_id"], format="metadata")
                .execute()
            )
        headers = {
            str(item.get("name", "")).casefold(): _decode_mime_header(
                str(item.get("value", ""))
            )
            for item in actual.get("message", {}).get("payload", {}).get("headers", [])
        }
        actual_recipients = {
            address.casefold() for _, address in getaddresses([headers.get("to", "")])
        }
        expected_recipient = expected.recipient.strip()
        if expected_recipient.casefold() == "me":
            expected_recipient = context.user.email
        if (
            expected_recipient.casefold() not in actual_recipients
            or headers.get("subject", "") != expected.subject
        ):
            raise ToolError("Thư nháp không khớp bản đã duyệt.", code="verification_failed")
        result = {
            "draft_id": row["resource_id"],
            "verified": True,
            "reconciled": True,
            "gmail_draft_url": "https://mail.google.com/mail/u/0/#drafts",
        }
        store.finish_reconciliation(context.user.id, payload.operation_id, result)
        return EmailOperationResult(data={"operation_id": payload.operation_id, **result})

    return await asyncio.to_thread(reconcile)


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
            max_attempts=3,
            timeout_seconds=30,
        ),
        ToolDefinition(
            name="gmail_read_matching_messages",
            description=(
                "Đọc văn bản đầy đủ của nhiều email khớp một truy vấn Gmail trong một lượt; "
                "lọc ngày/giờ nhận theo múi giờ và xác minh tên hoặc địa chỉ người gửi. "
                "Dùng cho bản tin/tổng hợp nhiều thư, kiểm next_page_token nếu còn trang. "
                "Không đọc nội dung ảnh hoặc tệp đính kèm."
            ),
            input_model=GmailReadMatchingInput,
            output_model=GmailReadMatchingOutput,
            handler=gmail_read_matching_messages,
            required_permissions={GMAIL_READ},
            required_oauth_scopes={GMAIL_READONLY_SCOPE},
            max_attempts=2,
            timeout_seconds=60,
        ),
        ToolDefinition(
            name="gmail_read_thread",
            description="Đọc các thư trong một chuỗi hội thoại Gmail theo thread_id.",
            input_model=GmailReadThreadInput,
            output_model=GmailReadThreadOutput,
            handler=gmail_read_thread,
            required_permissions={GMAIL_READ},
            required_oauth_scopes={GMAIL_READONLY_SCOPE},
            max_attempts=3,
            timeout_seconds=30,
        ),
        ToolDefinition(
            name="gmail_get_attachment",
            description="Tải một tệp đính kèm thuộc email đã xác thực, chỉ đọc.",
            input_model=GmailAttachmentInput,
            output_model=GmailAttachmentOutput,
            handler=gmail_get_attachment,
            required_permissions={GMAIL_READ},
            required_oauth_scopes={GMAIL_READONLY_SCOPE},
            max_attempts=2,
            timeout_seconds=30,
        ),
        ToolDefinition(
            name="gmail_summarize_thread",
            description="Tóm tắt toàn bộ chuỗi Gmail thành đúng ba ý sau thao tác chủ động.",
            input_model=GmailReadThreadInput,
            output_model=GmailSummaryOutput,
            handler=gmail_summarize_thread,
            required_permissions={GMAIL_READ},
            required_oauth_scopes={GMAIL_READONLY_SCOPE},
            requires_user_action=True,
            timeout_seconds=45,
        ),
        ToolDefinition(
            name="gmail_create_draft",
            description=(
                "Tạo bản thư nháp native trong Gmail sau khi người dùng duyệt đúng operation_id "
                "và approved_digest. Chỉ gọi từ API duyệt; Agent không được tự kích hoạt."
            ),
            input_model=EmailApprovalInput,
            output_model=GmailCreateDraftOutput,
            handler=gmail_create_draft,
            external_write=True,
            required_permissions={GMAIL_DRAFT},
            required_oauth_scopes={GMAIL_COMPOSE_SCOPE, DRIVE_READONLY_SCOPE},
            requires_user_action=True,
            timeout_seconds=35,
        ),
        ToolDefinition(
            name="gmail_prepare_native_draft",
            description="Chuẩn bị bản xem trước thư nháp Gmail; chưa ghi lên Gmail.",
            input_model=GmailDraftPrepareInput,
            output_model=EmailOperationResult,
            handler=gmail_prepare_native_draft,
            required_permissions={GMAIL_DRAFT},
            required_oauth_scopes={GMAIL_COMPOSE_SCOPE, DRIVE_READONLY_SCOPE},
            requires_user_action=True,
            timeout_seconds=30,
        ),
        ToolDefinition(
            name="gmail_reconcile_draft",
            description="Đọc lại thư nháp chưa xác định mà không tạo hoặc gửi thư mới.",
            input_model=OperationReference,
            output_model=EmailOperationResult,
            handler=gmail_reconcile_draft,
            required_permissions={GMAIL_DRAFT},
            required_oauth_scopes={GMAIL_COMPOSE_SCOPE},
            requires_user_action=True,
            max_attempts=1,
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
            external_write=True,
            required_permissions={GMAIL_SEND},
            required_oauth_scopes={GMAIL_SEND_SCOPE, DRIVE_READONLY_SCOPE},
            requires_user_action=True,
            timeout_seconds=45,
        ),
    ]
