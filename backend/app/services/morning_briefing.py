"""Build an idempotent daily brief through the governed Tool Registry."""

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from app.core.config import Settings
from app.db.models import ChatSession, Message, User
from app.tools.contracts import ToolContext
from app.tools.registry import ToolRegistry


class MorningBriefingService:
    """Compose a daily summary without bypassing permission, scope or audit gates."""

    # The morning job is deliberately bounded.  It must add useful body context without
    # turning an unattended digest into an unbounded mailbox export.
    MAX_EMAIL_THREADS = 5
    MAX_BODY_CHARS_PER_THREAD = 2400
    MAX_BODY_CHARS_TOTAL = 10_000

    def __init__(self, settings: Settings, registry: ToolRegistry):
        self.settings = settings
        self.registry = registry

    def _now(self) -> datetime:
        try:
            return datetime.now(ZoneInfo(self.settings.local_timezone))
        except ZoneInfoNotFoundError:
            return datetime.now(UTC)

    async def generate_brief(
        self,
        user: User,
        db,
        *,
        request_id: str,
    ) -> dict[str, Any]:
        """Read Gmail and Drive through audited tools, then upsert today's chat."""

        context = ToolContext(
            request_id=request_id,
            user=user,
            db=db,
            settings=self.settings,
            source="morning_briefing",
        )
        unread_count = 0
        recent_emails: list[Any] = []
        recent_files: list[Any] = []
        read_emails: list[dict[str, Any]] = []
        body_failures: list[dict[str, str]] = []
        selected_thread_count = 0
        gmail_notice = ""
        drive_notice = ""
        gmail_has_next_page = False

        try:
            gmail = await self.registry.execute(
                "gmail_list_messages",
                {"query": "is:unread newer_than:1d", "max_results": 5},
                context,
            )
            unread_count = int(self._value(gmail, "total_found", 0) or 0)
            recent_emails = list(self._value(gmail, "messages", []) or [])[: self.MAX_EMAIL_THREADS]
            selected_thread_count = len(self._unique_thread_ids(recent_emails))
            gmail_has_next_page = bool(self._value(gmail, "next_page_token"))
            read_emails, body_failures = await self._read_email_bodies(
                context, recent_emails
            )
        except Exception as exc:
            gmail_notice = self._safe_notice(getattr(exc, "code", "error"), "Gmail")

        try:
            drive = await self.registry.execute(
                "drive_list_files",
                {"page_size": 20, "exclude_folders": True},
                context,
            )
            threshold = datetime.now(UTC) - timedelta(hours=24)
            recent_files = [
                item
                for item in drive.files
                if item.modified_time
                and datetime.fromisoformat(item.modified_time.replace("Z", "+00:00")) >= threshold
            ][:5]
        except Exception:
            drive_notice = "Chưa đọc được thay đổi gần đây trên Google Drive."

        now = self._now()
        today = now.strftime("%d/%m/%Y")
        lines = [
            f"# ☀️ Bản tin buổi sáng ngày {today}",
            "",
            "Chào bạn! Dưới đây là tổng hợp nhanh các thông tin và cập nhật mới trong 24 giờ qua:",
            "",
            "## 📬 Hộp thư Gmail",
        ]
        if gmail_notice:
            lines.append(f"- *{gmail_notice}*")
        elif unread_count:
            if selected_thread_count:
                body_scope = (
                    f"đã đọc nội dung **{len(read_emails)}/{selected_thread_count} "
                    "cuộc trao đổi được chọn**"
                )
            else:
                body_scope = "chưa đọc được nội dung cuộc trao đổi nào"
            lines.append(
                f"- Có **{unread_count} thư chưa đọc** trong kết quả hiện tại; "
                f"{body_scope}."
            )
            if read_emails:
                lines.extend(["", "### Nội dung đã đọc"])
                for index, item in enumerate(read_emails, start=1):
                    self._append_email_block(lines, index, item)
            else:
                lines.append(
                    "- Chưa đọc được phần nội dung; hiện chỉ có thông tin tiêu đề/người gửi."
                )
            if gmail_has_next_page:
                lines.append(
                    "- Còn trang thư tiếp theo; bản tin này không tự đọc vượt giới hạn "
                    "5 cuộc trao đổi."
                )
            if body_failures:
                lines.extend(["", "### Thiếu dữ kiện cần kiểm tra"])
                for failure in body_failures:
                    if failure.get("partial") == "true":
                        lines.append(
                            f"- **{failure['label']}**: một phần nội dung chưa đọc được; "
                            "phần đã đọc vẫn được giữ riêng bên trên."
                        )
                    else:
                        lines.append(
                            f"- **{failure['label']}**: chưa đọc được nội dung; "
                            "chỉ nên dùng thông tin tiêu đề/người gửi cho đến khi mở lại thư."
                        )
        else:
            lines.append("- *Không có email chưa đọc trong 24 giờ gần nhất.*")

        lines.extend(["", "## 📂 Google Drive cập nhật"])
        if drive_notice:
            lines.append(f"- *{drive_notice}*")
        elif recent_files:
            lines.append(f"- Có **{len(recent_files)} tệp** vừa được cập nhật:")
            for item in recent_files:
                if item.web_view_link:
                    lines.append(f"  - 📄 [{item.name}]({item.web_view_link})")
                else:
                    lines.append(f"  - 📄 {item.name}")
        else:
            lines.append("- *Không có tệp nào được cập nhật trong 24 giờ gần nhất.*")

        lines.extend(
            [
                "",
                "## 💡 Gợi ý hành động hôm nay",
                "- Yêu cầu tóm tắt một thư hoặc tài liệu cụ thể bằng cách nêu tên.",
                "- Tra cứu số liệu, biểu bảng tài chính nhanh qua công cụ RAG biểu bảng.",
                "- Tạo bản thảo Google Docs hoặc Sheets rồi duyệt trước khi ghi.",
            ]
        )
        if gmail_notice:
            lines.extend(
                [
                    "",
                    "## ⚠️ Phạm vi chưa xác minh",
                    "- Gmail không đọc được trong lượt này; không suy diễn nội dung từ "
                    "thông tin tiêu đề/người gửi.",
                ]
            )
        elif not unread_count:
            lines.extend(
                [
                    "",
                    "## ⚠️ Phạm vi chưa xác minh",
                    "- Không có thư chưa đọc để đọc nội dung; bản tin không kết luận "
                    "về thư đã đọc.",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "## ⚠️ Phạm vi chưa xác minh",
                    "- Ảnh và tệp đính kèm chưa được đọc; chỉ phần văn bản trong "
                    "cuộc trao đổi đã trả về được dùng.",
                ]
            )
        summary = "\n".join(lines)
        title = f"Bản tin ngày {now.strftime('%Y-%m-%d')}"
        citations = self._citations(read_emails)

        session = await db.scalar(
            select(ChatSession)
            .where(ChatSession.user_id == user.id, ChatSession.title == title)
            .order_by(ChatSession.updated_at.desc())
        )
        if session is None:
            session = ChatSession(user_id=user.id, title=title)
            db.add(session)
            await db.flush()
        else:
            existing = await db.scalar(
                select(Message)
                .where(
                    Message.session_id == session.id,
                    Message.user_id == user.id,
                    Message.role == "assistant",
                )
                .order_by(Message.created_at.desc())
            )
            if existing is not None:
                existing.content = summary
                existing.citations_json = json.dumps(citations, ensure_ascii=False)
                session.updated_at = datetime.now(UTC)
                await db.commit()
                return self._result(
                    session,
                    existing,
                    summary,
                    unread_count,
                    recent_files,
                    read_email_count=len(read_emails),
                    body_failure_count=len(body_failures),
                    selected_thread_count=selected_thread_count,
                )

        message = Message(
            session_id=session.id,
            user_id=user.id,
            role="assistant",
            content=summary,
            citations_json=json.dumps(citations, ensure_ascii=False),
        )
        db.add(message)
        session.updated_at = datetime.now(UTC)
        await db.commit()
        return self._result(
            session,
            message,
            summary,
            unread_count,
            recent_files,
            read_email_count=len(read_emails),
            body_failure_count=len(body_failures),
            selected_thread_count=selected_thread_count,
        )

    async def _read_email_bodies(
        self, context: ToolContext, messages: list[Any]
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        """Read a bounded set of selected threads through the read-only tool harness.

        ``gmail_list_messages`` intentionally returns metadata.  The morning job may
        enrich those rows with body text, but it must never call the Gmail client
        directly or follow pagination indefinitely.  The registry remains responsible
        for the current user's OAuth scope, permission, owner and audit checks.
        """

        selected: list[tuple[Any, str]] = [
            (item, thread_id)
            for item, thread_id in self._unique_thread_items(messages)
        ]

        read: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        total_chars = 0
        for header, thread_id in selected:
            try:
                thread = await self.registry.execute(
                    "gmail_read_thread", {"thread_id": thread_id}, context
                )
            except Exception:
                failures.append({"label": self._email_label(header)})
                continue

            thread_messages = list(self._value(thread, "messages", []) or [])
            body_messages: list[dict[str, Any]] = []
            unreadable_count = 0
            omitted_count = 0
            remaining = max(
                0, min(self.MAX_BODY_CHARS_PER_THREAD, self.MAX_BODY_CHARS_TOTAL - total_chars)
            )
            for index, message in enumerate(thread_messages):
                body = str(
                    self._value(message, "plain_body", "")
                    or self._value(message, "body", "")
                    or ""
                ).strip()
                if not body:
                    unreadable_count += 1
                    continue
                if remaining <= 0:
                    omitted_count += len(thread_messages) - index
                    break
                truncated = len(body) > remaining
                excerpt_limit = remaining - 1 if truncated else remaining
                excerpt = body[: max(0, excerpt_limit)].rstrip()
                if truncated:
                    excerpt += "…"
                body_messages.append(
                    {
                        "message": message,
                        "body": excerpt,
                        "truncated": truncated,
                    }
                )
                total_chars += len(excerpt)
                remaining = min(
                    self.MAX_BODY_CHARS_PER_THREAD - sum(len(row["body"]) for row in body_messages),
                    self.MAX_BODY_CHARS_TOTAL - total_chars,
                )
                if remaining <= 0:
                    omitted_count += len(thread_messages) - index - 1
                    break

            if not body_messages:
                if omitted_count:
                    failures.append(
                        {
                            "label": (
                                f"{self._email_label(header)} "
                                f"({omitted_count} thư chưa được đưa vào bản tin "
                                "do giới hạn nội dung)"
                            ),
                            "partial": "true",
                        }
                    )
                else:
                    failures.append({"label": self._email_label(header)})
                continue
            partial_notes: list[str] = []
            if unreadable_count:
                partial_notes.append(f"{unreadable_count} thư thiếu phần văn bản")
            if omitted_count:
                partial_notes.append(
                    f"{omitted_count} thư chưa được đưa vào bản tin do giới hạn nội dung"
                )
            if partial_notes:
                failures.append(
                    {
                        "label": f"{self._email_label(header)} ({'; '.join(partial_notes)})",
                        "partial": "true",
                    }
                )
            read.append(
                {
                    "header": header,
                    "thread": thread,
                    "thread_id": thread_id,
                    "messages": body_messages,
                    "omitted_message_count": omitted_count,
                }
            )
        return read, failures

    @classmethod
    def _append_email_block(cls, lines: list[str], index: int, item: dict[str, Any]) -> None:
        header = item["header"]
        thread = item["thread"]
        subject = str(
            cls._value(thread, "subject", "")
            or cls._value(header, "subject", "(Không có tiêu đề)")
        )
        sender = str(cls._value(header, "sender", "Không rõ"))
        thread_id = item["thread_id"]
        lines.extend(
            [
                f"#### {index}. {subject}",
                f"- Người gửi: {sender}",
                f"- {cls._source_line(thread_id)}",
                "- Trích nội dung:",
            ]
        )
        for row in item["messages"]:
            message = row["message"]
            date = str(cls._value(message, "date", "") or "").strip()
            message_sender = str(cls._value(message, "sender", sender) or sender)
            label = f"  - {message_sender}"
            if date:
                label += f" ({date})"
            lines.append(label + ":")
            for content_line in str(row["body"]).splitlines() or [""]:
                lines.append(f"    > {content_line}")
            if row.get("truncated"):
                lines.append("    - Nội dung đã rút gọn theo giới hạn bản tin (ký hiệu …).")
            attachments = cls._value(message, "attachments", []) or []
            if attachments:
                lines.append(f"    - Tệp đính kèm: {len(attachments)} (chưa đọc nội dung)")
        if item.get("omitted_message_count"):
            lines.append(
                f"- Còn {item['omitted_message_count']} thư trong cuộc trao đổi "
                "chưa được đưa vào bản tin do giới hạn nội dung."
            )

    @staticmethod
    def _value(item: Any, key: str, default: Any = None) -> Any:
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    @classmethod
    def _email_label(cls, item: Any) -> str:
        sender = str(cls._value(item, "sender", "Không rõ"))
        subject = str(cls._value(item, "subject", "(Không có tiêu đề)"))
        return f"{sender} — {subject}"

    @classmethod
    def _unique_thread_items(cls, messages: list[Any]) -> list[tuple[Any, str]]:
        selected: list[tuple[Any, str]] = []
        seen_threads: set[str] = set()
        for item in messages:
            thread_id = str(cls._value(item, "thread_id", "") or "").strip()
            if not thread_id or thread_id in seen_threads:
                continue
            seen_threads.add(thread_id)
            selected.append((item, thread_id))
            if len(selected) >= cls.MAX_EMAIL_THREADS:
                break
        return selected

    @classmethod
    def _unique_thread_ids(cls, messages: list[Any]) -> set[str]:
        return {thread_id for _item, thread_id in cls._unique_thread_items(messages)}

    @staticmethod
    def _gmail_link(thread_id: str) -> str | None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{5,200}", thread_id):
            return None
        return f"https://mail.google.com/mail/u/0/#all/{thread_id}"

    @classmethod
    def _source_line(cls, thread_id: str) -> str:
        link = cls._gmail_link(thread_id)
        if link:
            return f"Nguồn: [Mở cuộc trao đổi trên Gmail]({link})"
        return "Nguồn Gmail: mã cuộc trao đổi không đủ điều kiện tạo liên kết."

    @classmethod
    def _citations(cls, read_emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for item in read_emails:
            thread_id = str(item["thread_id"])
            thread = item["thread"]
            subject = str(
                cls._value(thread, "subject", "")
                or cls._value(item["header"], "subject", "(Không có tiêu đề)")
            )
            snippets = " ".join(
                str(row.get("body", "")).strip() for row in item["messages"]
            ).strip()
            citation: dict[str, Any] = {
                "file_id": thread_id,
                "file_name": subject,
                "chunk_index": 0,
                "snippet": snippets[:500],
                "web_view_link": cls._gmail_link(thread_id),
                "score": 1.0,
            }
            citations.append(citation)
        return citations

    @staticmethod
    def _safe_notice(code: str, provider: str) -> str:
        if code in {"access_denied", "oauth_scope_missing", "gmail_insufficient_permissions"}:
            return f"{provider} chưa được cấp đủ quyền. Hãy kết nối lại tài khoản."
        if code == "gmail_api_disabled":
            return "Gmail API chưa được bật trong Google Cloud Console."
        return f"{provider} tạm thời không phản hồi. Hãy thử lại sau."

    @staticmethod
    def _result(
        session: ChatSession,
        message: Message,
        summary: str,
        unread_count: int,
        recent_files: list[Any],
        *,
        read_email_count: int = 0,
        body_failure_count: int = 0,
        selected_thread_count: int = 0,
    ) -> dict[str, Any]:
        return {
            "session_id": session.id,
            "title": session.title,
            "summary": summary,
            "answer": summary,
            "unread_emails": unread_count,
            "modified_files": len(recent_files),
            "read_email_count": read_email_count,
            "body_failure_count": body_failure_count,
            "selected_thread_count": selected_thread_count,
            "message_id": message.id,
        }
