"""Privacy-minimal live read smoke for the Google Calendar tool."""


from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select

from app.core.config import Settings
from app.db.models import User
from app.db.session import SessionFactory
from app.tools.calendar import CalendarUpcomingInput, calendar_list_upcoming
from app.tools.contracts import ToolContext, ToolError


async def main() -> None:
    settings = Settings()
    async with SessionFactory() as db:
        user = await db.scalar(
            select(User).where(User.email == "dbp3206@gmail.com", User.is_active.is_(True))
        )
        if user is None:
            raise RuntimeError("Connected owner not found")
        try:
            result = await calendar_list_upcoming(
                CalendarUpcomingInput(days=14, max_results=20),
                ToolContext(request_id="qa-calendar-read", user=user, db=db, settings=settings),
            )
        except ToolError as exc:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_code": exc.code,
                        "cloud_writes": 0,
                        "passed": False,
                    }
                )
            )
            return
    print(
        json.dumps(
            {
                "status": "ok",
                "events_returned": len(result.events),
                "window_days": 14,
                "cloud_writes": 0,
                "passed": True,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
