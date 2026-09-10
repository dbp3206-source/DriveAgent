"""Build an idempotent daily brief through the governed Tool Registry."""

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from app.core.config import Settings
from app.db.models import ChatSession, Message, User
from app.tools.contracts import ToolContext, ToolError
from app.tools.registry import ToolRegistry


class MorningBriefingService:
    """Compose a daily summary without bypassing permission, scope or audit gates."""

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
        gmail_notice = ""
        drive_notice = ""

        try:
            gmail = await self.registry.execute(
                "gmail_list_messages",
                {"query": "is:unread newer_than:1d", "max_results": 5},
                context,
            )
            unread_count = gmail.total_found
            recent_emails = gmail.messages[:3]
        except ToolError as exc:
            gmail_notice = self._safe_notice(exc.code, "Gmail")

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
        except (ToolError, ValueError):
            drive_notice = "Chưa đọc được thay đổi gần đây trên Google Drive."

        now = self._now()
        today = now.strftime("%d/%m/%Y")
        lines = [
            f"# Bản tin ngày {today}",
            "",
            "Dưới đây là những việc mới trong 24 giờ gần nhất.",
            "",
            "## Gmail",
        ]
        if gmail_notice:
            lines.append(f"- {gmail_notice}")
        elif unread_count:
            lines.append(f"- Có **{unread_count} email chưa đọc** trong kết quả hiện tại.")
            for email in recent_emails:
                lines.append(f"  - **{email.sender}** — {email.subject}")
        else:
            lines.append("- Không có email chưa đọc trong 24 giờ gần nhất.")

        lines.extend(["", "## Google Drive"])
        if drive_notice:
            lines.append(f"- {drive_notice}")
        elif recent_files:
            lines.append(f"- Có **{len(recent_files)} tệp** vừa được cập nhật:")
            for item in recent_files:
                if item.web_view_link:
                    lines.append(f"  - [{item.name}]({item.web_view_link})")
                else:
                    lines.append(f"  - {item.name}")
        else:
            lines.append("- Không có tệp nào được cập nhật trong 24 giờ gần nhất.")

        lines.extend(
            [
                "",
                "## Bạn có thể làm tiếp",
                "- Yêu cầu tóm tắt một email hoặc tài liệu cụ thể.",
                "- Lập chỉ mục tài liệu quan trọng để hỏi lại bằng RAG.",
            ]
        )
        summary = "\n".join(lines)
        title = f"Bản tin ngày {now.strftime('%Y-%m-%d')}"

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
                await db.commit()
                return self._result(session, existing, summary, unread_count, recent_files)

        message = Message(
            session_id=session.id,
            user_id=user.id,
            role="assistant",
            content=summary,
        )
        db.add(message)
        await db.commit()
        return self._result(session, message, summary, unread_count, recent_files)

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
    ) -> dict[str, Any]:
        return {
            "session_id": session.id,
            "title": session.title,
            "summary": summary,
            "unread_emails": unread_count,
            "modified_files": len(recent_files),
            "message_id": message.id,
        }
