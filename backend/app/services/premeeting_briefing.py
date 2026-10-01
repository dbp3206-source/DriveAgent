"""Read-only pre-meeting preview built from Calendar, Gmail and current web sources."""

import json
import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from app.db.models import ChatSession, Message, User
from app.tools.contracts import ToolContext, ToolError


class PreMeetingBriefingService:
    def __init__(self, settings, registry):
        self.settings = settings
        self.registry = registry

    def _now(self) -> datetime:
        try:
            return datetime.now(ZoneInfo(self.settings.local_timezone))
        except ZoneInfoNotFoundError:
            return datetime.now(UTC)

    async def generate(self, user: User, db, *, request_id: str) -> dict:
        context = ToolContext(
            request_id=request_id,
            user=user,
            db=db,
            settings=self.settings,
            source="pre_meeting_briefing",
        )
        calendar = await self.registry.execute(
            "calendar_list_upcoming", {"days": 2, "max_results": 10}, context
        )
        blocks: list[str] = []
        citations: list[dict[str, str]] = []
        warnings: list[str] = []
        for event in calendar.events[:3]:
            term = re.sub(r"[\"{}()]", " ", event.title)
            term = re.sub(r"\s+", " ", term).strip()[:120]
            mail_lines: list[str] = []
            try:
                gmail = await self.registry.execute(
                    "gmail_list_messages",
                    {"query": f'newer_than:30d "{term}"', "max_results": 3},
                    context,
                )
                mail_lines = [
                    f"- {mail.sender} — {mail.subject} ({mail.date})"
                    for mail in gmail.messages
                ]
            except ToolError as exc:
                warnings.append(f"Gmail {event.id}: {exc.code}")
            research = "Chưa có nguồn web đã xác minh."
            try:
                web = await self.registry.execute(
                    "web_research",
                    {
                        "news_query": term,
                        "question": (
                            f"Thông tin mới trong 30 ngày liên quan đến cuộc họp {event.title}"
                        ),
                        "max_sources": 4,
                        "timezone": self.settings.local_timezone,
                        "time_range": "30 ngày gần đây",
                    },
                    context,
                )
                research = web.summary
                citations.extend(
                    {"title": source.title, "url": source.url} for source in web.sources
                )
            except ToolError as exc:
                warnings.append(f"Web {event.id}: {exc.code}")
            blocks.append(
                "\n".join(
                    [
                        f"## {event.title}",
                        f"- Thời gian: {event.start}",
                        f"- Địa điểm: {event.location or 'Chưa có'}",
                        "- Email liên quan:",
                        *(mail_lines or ["  - Không tìm thấy trong phạm vi 30 ngày."]),
                        "",
                        "### Thông tin mới có nguồn",
                        research,
                    ]
                )
            )
        if not blocks:
            blocks.append("Không có cuộc họp nào trong 48 giờ tới.")
        now = self._now()
        title = f"Chuẩn bị cuộc họp {now.date().isoformat()}"
        summary = "\n\n".join(
            [
                f"# {title}",
                "Bản xem trước read-only; hãy mở nguồn và kiểm tra trước mọi hành động.",
                *blocks,
                "## Cảnh báo thu thập",
                *(f"- {warning}" for warning in warnings),
            ]
        )
        session = await db.scalar(
            select(ChatSession).where(
                ChatSession.user_id == user.id, ChatSession.title == title
            )
        )
        if session is None:
            session = ChatSession(user_id=user.id, title=title)
            db.add(session)
            await db.flush()
        existing = await db.scalar(
            select(Message)
            .where(
                Message.session_id == session.id,
                Message.user_id == user.id,
                Message.role == "assistant",
            )
            .order_by(Message.created_at.desc())
        )
        if existing is None:
            existing = Message(session_id=session.id, user_id=user.id, role="assistant")
            db.add(existing)
        existing.content = summary
        existing.citations_json = json.dumps(citations, ensure_ascii=False)
        session.updated_at = datetime.now(UTC)
        await db.commit()
        return {
            "session_id": session.id,
            "message_id": existing.id,
            "meeting_count": len(calendar.events),
            "source_count": len(citations),
            "warnings": warnings,
        }
