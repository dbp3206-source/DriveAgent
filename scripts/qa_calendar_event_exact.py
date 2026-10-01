"""Verify the single approved QA Calendar event without printing private fields."""


from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings
from app.db.models import User
from app.db.session import SessionFactory
from app.tools.calendar import (
    CalendarUpcomingInput,
    calendar_list_upcoming,
)
from app.tools.contracts import ToolContext

MARKER = "QA-CALENDAR-20260928"
TITLE = "[Veridra QA] Meeting prep test — không có khách mời"


async def main() -> None:
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
            CalendarUpcomingInput(days=14, max_results=20, query=MARKER),
            ToolContext(
                request_id="qa-calendar-event-exact",
                user=user,
                db=db,
                settings=settings,
            ),
        )
    matches = [event for event in calendar.events if event.title == TITLE]
    result = {
        "cloud_writes": 0,
        "exact_matches": len(matches),
        "has_no_attendee_details": all(
            not hasattr(event, "attendees") for event in matches
        ),
        "passed": len(matches) == 1,
    }
    print(json.dumps(result, ensure_ascii=False))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
