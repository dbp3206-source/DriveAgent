"""Dịch vụ giám sát Gmail từ xa và quản trị tương tác qua Remote Action Tokens.

Tạo bản tin Gmail và link thao tác có xác nhận, token một lần.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import Settings
from app.db.models import User
from app.services.relational_operations import operation_store_for
from app.tools.contracts import ToolContext, ToolError
from app.tools.gmail import GmailCreateDraftInput
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

URGENT_KEYWORDS = [
    "khẩn",
    "gấp",
    "urgent",
    "asap",
    "deadline",
    "quan trọng",
    "hạn chót",
    "phê duyệt",
    "duyệt gấp",
    "báo cáo",
    "họp",
    "meeting",
    "review",
]


class RemoteActionSigner:
    """Ký số và xác thực các Action Token dùng một lần hoặc có thời hạn an toàn."""

    @staticmethod
    def sign_action(
        action: str,
        payload: dict[str, Any],
        user_id: str,
        secret: str,
        ttl_seconds: int = 300,
    ) -> str:
        data = {
            "action": action,
            "payload": payload,
            "user_id": user_id,
            "exp": int(time.time()) + ttl_seconds,
            "nonce": uuid4().hex,
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        sig = hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{encoded}.{sig}"

    @staticmethod
    def verify_action(token: str, secret: str) -> dict[str, Any]:
        parts = token.strip().split(".")
        if len(parts) != 2:
            raise ToolError(
                "Mã thao tác từ xa (Remote Action Token) không hợp lệ.", code="invalid_token"
            )
        encoded, sig = parts
        expected_sig = hmac.new(
            secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            raise ToolError(
                "Chữ ký bảo mật của thao tác từ xa không hợp lệ.", code="invalid_signature"
            )
        try:
            data = json.loads(base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8"))
        except Exception as exc:
            raise ToolError("Không thể giải mã dữ liệu token.", code="token_decode_error") from exc
        if not isinstance(data, dict):
            raise ToolError("Nội dung token không hợp lệ.", code="token_decode_error")
        now = int(time.time())
        try:
            expires_at = int(data.get("exp", 0))
        except (TypeError, ValueError) as exc:
            raise ToolError("Thời hạn token không hợp lệ.", code="token_expired") from exc
        if expires_at < now:
            raise ToolError("Mã thao tác từ xa đã hết hạn.", code="token_expired")
        if expires_at > now + 600:
            raise ToolError("Thời hạn token vượt giới hạn cho phép.", code="token_ttl_invalid")
        if not isinstance(data.get("nonce"), str) or len(data["nonce"]) != 32:
            raise ToolError("Mã thao tác từ xa thiếu nonce.", code="token_nonce_missing")
        if not isinstance(data.get("payload"), dict) or not isinstance(data.get("user_id"), str):
            raise ToolError("Nội dung token không hợp lệ.", code="token_decode_error")
        return data


class RemoteActionLedger:
    """Persistent at-most-once ledger for signed remote action capabilities."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS consumed_remote_actions (
                    nonce_hash TEXT PRIMARY KEY,
                    expires_at INTEGER NOT NULL,
                    consumed_at INTEGER NOT NULL
                )"""
            )

    def consume(self, nonce: str, expires_at: int) -> None:
        nonce_hash = hashlib.sha256(nonce.encode("utf-8")).hexdigest()
        now = int(time.time())
        try:
            with sqlite3.connect(self.path, timeout=10) as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("DELETE FROM consumed_remote_actions WHERE expires_at < ?", (now,))
                db.execute(
                    "INSERT INTO consumed_remote_actions(nonce_hash, expires_at, consumed_at) "
                    "VALUES (?, ?, ?)",
                    (nonce_hash, expires_at, now),
                )
        except sqlite3.IntegrityError as exc:
            raise ToolError(
                "Thao tác đã được dùng; hãy mở một yêu cầu mới.", code="remote_action_replayed"
            ) from exc


def remote_action_ledger(settings: Settings):
    from app.services.relational_remote_actions import relational_remote_action_ledger

    relational = relational_remote_action_ledger(settings)
    return relational or RemoteActionLedger(settings.data_dir / "remote_actions.db")


class GmailRemoteService:
    """Dịch vụ tổng hợp bản tin email từ xa và xử lý tương tác đa kênh."""

    def __init__(self, settings: Settings, registry: ToolRegistry):
        self.settings = settings
        self.registry = registry

    def score_urgency(self, subject: str, snippet: str, sender: str) -> tuple[int, list[str]]:
        """Đánh giá điểm khẩn cấp từ 1 đến 10 và trích xuất lý do."""
        score = 1
        reasons = []
        text = f"{subject} {snippet}".casefold()
        for kw in URGENT_KEYWORDS:
            if kw in text:
                score += 2
                reasons.append(f"Chứa từ khóa: '{kw}'")
        if "?" in subject or "yêu cầu" in text:
            score += 1
            reasons.append("Yêu cầu phản hồi thông tin")
        final_score = min(score, 10)
        return final_score, reasons

    async def get_executive_digest(
        self,
        user: User,
        db: Any,
        request_id: str,
        query: str = "is:unread newer_than:2d",
        max_results: int = 10,
    ) -> dict[str, Any]:
        """Tạo bản tóm tắt email điều hành phục vụ xem từ xa."""
        context = ToolContext(
            request_id=request_id,
            user=user,
            db=db,
            settings=self.settings,
            source="remote_digest",
        )
        try:
            result = await self.registry.execute(
                "gmail_list_messages",
                {"query": query, "max_results": max_results},
                context,
            )
        except Exception as exc:
            logger.warning("Không thể đọc email từ xa; type=%s", type(exc).__name__)
            return {
                "status": "error",
                "message": "Không thể tải Gmail lúc này. Hãy mở Veridra và thử lại.",
                "total_unread": 0,
                "priority_items": [],
            }

        priority_items = []
        for msg in result.messages:
            score, reasons = self.score_urgency(msg.subject, msg.snippet, msg.sender)
            reply_token = RemoteActionSigner.sign_action(
                action="create_reply_draft",
                payload={
                    "thread_id": msg.thread_id,
                    "subject": f"Re: {msg.subject}",
                    "recipient": msg.sender,
                    "source_snippet": msg.snippet,
                    "display_name": user.display_name or "Veridra",
                },
                user_id=user.id,
                secret=self.settings.app_secret,
            )
            export_doc_token = RemoteActionSigner.sign_action(
                action="export_to_doc",
                payload={
                    "title": f"Tóm tắt Email: {msg.subject}",
                    "sender": msg.sender,
                    "date": msg.date,
                    "content": msg.snippet,
                },
                user_id=user.id,
                secret=self.settings.app_secret,
            )

            priority_items.append(
                {
                    "id": msg.id,
                    "thread_id": msg.thread_id,
                    "sender": msg.sender,
                    "subject": msg.subject,
                    "date": msg.date,
                    "snippet": msg.snippet,
                    "urgency_score": score,
                    "is_high_priority": score >= 3,
                    "reasons": reasons,
                    "actions": {
                        "reply_draft_token": reply_token,
                        "export_doc_token": export_doc_token,
                    },
                }
            )

        priority_items.sort(key=lambda x: x["urgency_score"], reverse=True)
        high_priority_count = sum(1 for x in priority_items if x["is_high_priority"])

        return {
            "status": "success",
            "timestamp": datetime.now(UTC).isoformat(),
            "total_unread": result.total_found,
            "high_priority_count": high_priority_count,
            "items": priority_items,
        }

    async def execute_remote_token(
        self,
        token: str,
        db: Any,
        request_id: str,
    ) -> dict[str, Any]:
        """Thực thi hành động từ xa được ủy quyền bằng chữ ký token."""
        data = RemoteActionSigner.verify_action(token, self.settings.app_secret)
        action = data["action"]
        payload = data["payload"]
        user_id = data["user_id"]

        user = await db.get(User, user_id)
        if not user or not user.is_active:
            raise ToolError("Người dùng không hợp lệ hoặc tài khoản đã khóa.", code="user_invalid")

        action = data.get("action")
        if action not in {"create_reply_draft", "export_to_doc"}:
            raise ToolError("Hành động từ xa không được hỗ trợ.", code="unsupported_action")
        await asyncio.to_thread(
            remote_action_ledger(self.settings).consume,
            data["nonce"],
            int(data["exp"]),
        )

        context = ToolContext(
            request_id=request_id,
            user=user,
            db=db,
            settings=self.settings,
            # The signed token is shown as a preview first; the user explicitly
            # submits the confirmation form before this handler is reached.
            source="api",
        )

        if action == "create_reply_draft":
            subject = payload.get("subject", "Re: Email")
            recipient = payload.get("recipient", "")
            thread_id = payload.get("thread_id", "")
            snippet = payload.get("source_snippet", "")
            body = reply_draft_body(
                recipient, snippet, payload.get("display_name") or user.display_name or "Veridra"
            )
            draft_input = GmailCreateDraftInput(
                recipient=recipient,
                subject=subject,
                body=body,
                thread_id=thread_id or None,
            )
            operation = await asyncio.to_thread(
                operation_store_for(self.settings).prepare,
                user.id,
                f"remote-{data['nonce']}",
                "gmail_draft_create",
                draft_input.model_dump(mode="json"),
            )
            draft_res = await self.registry.execute(
                "gmail_create_draft",
                {
                    "operation_id": operation["id"],
                    "approved_digest": operation["digest"],
                },
                context,
            )
            return {
                "action": action,
                "status": "success",
                "message": f"Đã tạo thư nháp trả lời thành công cho {recipient}.",
                "draft_id": draft_res.draft_id,
                "gmail_draft_url": draft_res.gmail_draft_url,
            }

        if action == "export_to_doc":
            title = payload.get("title", "Tóm tắt Email")
            content = payload.get("content", "")
            sender = payload.get("sender", "")
            date = payload.get("date", "")
            blocks = [
                {"text": title, "style": "HEADING_1"},
                {"text": f"Người gửi: {sender} | Thời gian: {date}", "style": "NORMAL_TEXT"},
                {"text": "Nội dung tóm tắt:", "style": "HEADING_2"},
                {"text": content, "style": "NORMAL_TEXT"},
            ]
            doc_res = await self.registry.execute(
                "docs_prepare",
                {
                    "request_key": f"remote-{request_id}",
                    "action": "create",
                    "document": {"title": title, "blocks": blocks},
                },
                context,
            )
            return {
                "action": action,
                "status": "success",
                "message": "Đã chuẩn bị bản xuất Google Docs từ email thành công.",
                "preview": doc_res.data.get("preview"),
            }

        raise ToolError(f"Hành động từ xa không được hỗ trợ: {action}", code="unsupported_action")


def reply_draft_body(recipient: str, snippet: str, display_name: str = "Veridra") -> str:
    """Create the same deterministic draft text shown by the remote approval page."""

    return (
        f"Kính gửi {recipient},\n\n"
        f"Tôi đã nhận được thông tin từ bạn liên quan đến: '{snippet}'.\n"
        "Tôi sẽ phản hồi chi tiết tới bạn sớm nhất có thể.\n\n"
        f"Trân trọng,\n{display_name}"
    )
