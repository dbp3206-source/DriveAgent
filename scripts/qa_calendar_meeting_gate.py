"""Read-only acceptance gate for a real Calendar event and meeting briefing.

The test prints aggregate assertions only. It does not persist or print Google
resource IDs, email content, OAuth credentials, or session cookies.
"""

from __future__ import annotations

import asyncio
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from qa_google_read_smoke import BASE, _cookie, _read

from app.core.config import Settings
from app.db.models import User
from app.db.session import SessionFactory
from app.tools.calendar import (
    CalendarUpcomingInput,
    calendar_list_upcoming,
)
from app.tools.contracts import ToolContext

EVENT_MARKER = "QA-CALENDAR-20260928"
EVENT_TITLE = "[Veridra QA] Meeting prep test — không có khách mời"


def _post(path: str, payload: dict[str, object], cookie: str) -> dict[str, object]:
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Cookie": f"drive_agent_session={cookie}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "http://localhost:8000",
            "Referer": "http://localhost:8000/#/home",
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


async def main() -> None:
    cookie = _cookie()
    settings = Settings()
    async with SessionFactory() as db:
        user = await db.scalar(
            select(User).where(
                User.email == "dbp3206@gmail.com", User.is_active.is_(True)
            )
        )
        if user is None:
            raise RuntimeError("Connected owner not found")
        calendar = await calendar_list_upcoming(
            CalendarUpcomingInput(days=14, max_results=20, query=EVENT_MARKER),
            ToolContext(
                request_id="qa-calendar-meeting-gate",
                user=user,
                db=db,
                settings=settings,
            ),
        )
    matching_events = [
        event
        for event in calendar.events
        if event.title == EVENT_TITLE
    ]

    gmail_query = urllib.parse.urlencode(
        {
            "query": 'from:"Bảo Phúc Đinh" subject:"Bản chi tiết" newer_than:14d',
            "max_results": 10,
        }
    )
    gmail = _read(f"/api/gmail/messages?{gmail_query}", cookie)
    candidates = gmail.get("messages", [])
    if len(matching_events) != 1 or not candidates:
        result = {
            "cloud_writes": 0,
            "calendar_matches": len(matching_events),
            "email_source_available": bool(candidates),
            "passed": False,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    briefing = _post(
        "/api/briefings/customer",
        {
            "gmail_thread_id": str(candidates[0]["thread_id"]),
            "company_name": "ProtonX Demo",
            "calendar_query": EVENT_MARKER,
            "research_question": "Tổng quan phục vụ buổi kiểm thử meeting-prep",
        },
        cookie,
    )
    report = str(briefing.get("report_markdown") or "")
    result = {
        "cloud_writes": 0,
        "calendar_matches": len(matching_events),
        "email_source_available": True,
        "meeting_count": briefing.get("meeting_count"),
        "email_message_count_positive": (
            int(briefing.get("email_message_count") or 0) > 0
        ),
        "source_count": int(briefing.get("source_count") or 0),
        "web_research_degraded": briefing.get("web_research_degraded") is True,
        "degradation_warning_present": bool(briefing.get("warnings")),
        "event_present_in_report": EVENT_TITLE in report,
        "human_approval_section_present": "## Human approval" in report,
        "ready_for_human_approval": briefing.get("ready_for_human_approval") is True,
    }
    result["passed"] = all(
        (
            result["calendar_matches"] == 1,
            result["meeting_count"] == 1,
            result["email_message_count_positive"],
            result["source_count"] > 0
            or (
                result["web_research_degraded"]
                and result["degradation_warning_present"]
            ),
            result["event_present_in_report"],
            result["human_approval_section_present"],
            result["ready_for_human_approval"],
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
