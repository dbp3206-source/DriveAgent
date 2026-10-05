"""Read-only pre-meeting preview built from Calendar, Gmail and current web sources."""

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
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

    async def due_events(self, user: User, db, *, request_id: str) -> list:
        context = ToolContext(
            request_id=request_id,
            user=user,
            db=db,
            settings=self.settings,
            source="pre_meeting_briefing",
        )
        calendar = await self.registry.execute(
            "calendar_list_upcoming", {"days": 1, "max_results": 100}, context
        )
        return self._due_events(calendar.events, self._now())

    async def generate(
        self, user: User, db, *, request_id: str, expected_event: dict | None = None
    ) -> dict:
        now = self._now()
        context = ToolContext(
            request_id=request_id,
            user=user,
            db=db,
            settings=self.settings,
            source="pre_meeting_briefing",
        )
        # Always read Calendar again at execution. A queued snapshot is not
        # permission to research a cancelled, rescheduled or changed meeting.
        meetings = await self.due_events(user, db, request_id=request_id)
        if expected_event is not None:
            meetings = [event for event in meetings if self.event_identity(event) == expected_event]
        if not meetings:
            # No Gmail/web/model work and no empty conversation for a poll
            # with no timed meeting due. Past/all-day events are not meetings
            # that can be safely assigned an implicit preparation deadline.
            return {
                "meeting_count": 0,
                "source_count": 0,
                "warnings": [],
                "skipped": "event_not_due_or_changed",
            }
        blocks: list[str] = []
        citations: list[dict[str, str]] = []
        warnings: list[str] = []
        for event in meetings:
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
                    f"- {mail.sender} — {mail.subject} ({mail.date})" for mail in gmail.messages
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
        title = f"Chuẩn bị cuộc họp {now.date().isoformat()}"
        if expected_event is not None:
            event_id = hashlib.sha256(expected_event["id"].encode()).hexdigest()[:16]
            title += f" · {event_id}"
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
            select(ChatSession).where(ChatSession.user_id == user.id, ChatSession.title == title)
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
            "meeting_count": len(meetings),
            "source_count": len(citations),
            "warnings": warnings,
        }

    def _due_events(self, events, now: datetime) -> list:
        due = []
        for event in events:
            if getattr(event, "all_day", False) or getattr(event, "status", None) == "cancelled":
                continue
            try:
                start = datetime.fromisoformat(event.start.replace("Z", "+00:00"))
            except (TypeError, ValueError, AttributeError):
                continue
            # Naive timestamps and date-only values cannot establish the
            # event's timezone. Do not guess and schedule a wrong-time brief.
            if start.tzinfo is None:
                continue
            window = timedelta(minutes=self.settings.pre_meeting_lead_minutes)
            if event.id and now < start <= now + window:
                due.append(event)
        return sorted(
            due, key=lambda event: datetime.fromisoformat(event.start.replace("Z", "+00:00"))
        )

    @staticmethod
    def event_identity(event) -> dict[str, str]:
        # Provider revision is authoritative when supplied. The fallback is a
        # fingerprint of source fields, not an invented provider version.
        source = {
            field: getattr(event, field, None)
            for field in (
                "id",
                "title",
                "start",
                "end",
                "all_day",
                "location",
                "html_link",
                "status",
                "updated",
                "etag",
            )
        }
        fingerprint = hashlib.sha256(
            json.dumps(source, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        return {"id": event.id, "version": fingerprint}
