"""Read-only Google Calendar tool for upcoming-meeting context."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel, ConfigDict, Field

from app.auth.google_oauth import refresh_and_store_if_needed
from app.auth.permissions import CALENDAR_READ
from app.tools.contracts import ToolContext, ToolDefinition, ToolError

CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"


class CalendarUpcomingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days: int = Field(default=14, ge=1, le=90)
    max_results: int = Field(default=20, ge=1, le=100)
    query: str | None = Field(default=None, max_length=240)


class CalendarEventView(BaseModel):
    id: str
    title: str
    start: str
    end: str
    all_day: bool
    location: str | None = None
    html_link: str | None = None
    status: str | None = None
    updated: str | None = None
    etag: str | None = None


class CalendarUpcomingOutput(BaseModel):
    events: list[CalendarEventView]
    window_start: str
    window_end: str


def _translate(exc: HttpError) -> ToolError:
    status = int(getattr(exc.resp, "status", 500))
    return ToolError(
        "Google Calendar tạm thời không thể đọc sự kiện.",
        code=f"google_calendar_{status}",
        retryable=status in {408, 429, 500, 502, 503, 504},
    )


async def calendar_list_upcoming(
    payload: CalendarUpcomingInput, context: ToolContext
) -> CalendarUpcomingOutput:
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)
    service = await asyncio.to_thread(
        build, "calendar", "v3", credentials=credentials, cache_discovery=False
    )
    start = datetime.now(UTC)
    end = start + timedelta(days=payload.days)
    try:
        response: dict[str, Any] = await asyncio.to_thread(
            service.events()
            .list(
                calendarId="primary",
                timeMin=start.isoformat().replace("+00:00", "Z"),
                timeMax=end.isoformat().replace("+00:00", "Z"),
                maxResults=payload.max_results,
                singleEvents=True,
                orderBy="startTime",
                q=payload.query,
                fields="items(id,summary,start,end,location,htmlLink,status,updated,etag)",
            )
            .execute
        )
    except HttpError as exc:
        raise _translate(exc) from exc
    events = []
    for item in response.get("items", []):
        if item.get("status") == "cancelled":
            continue
        start_data, end_data = item.get("start", {}), item.get("end", {})
        all_day = "date" in start_data
        events.append(
            CalendarEventView(
                id=str(item.get("id", "")),
                title=str(item.get("summary") or "(Không có tiêu đề)"),
                start=str(start_data.get("date") or start_data.get("dateTime") or ""),
                end=str(end_data.get("date") or end_data.get("dateTime") or ""),
                all_day=all_day,
                location=item.get("location"),
                html_link=item.get("htmlLink"),
                status=item.get("status"),
                updated=item.get("updated"),
                etag=item.get("etag"),
            )
        )
    return CalendarUpcomingOutput(
        events=events,
        window_start=start.isoformat(),
        window_end=end.isoformat(),
    )


def calendar_tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="calendar_list_upcoming",
            description="Đọc các lịch hẹn sắp tới từ Google Calendar, không thay đổi lịch.",
            input_model=CalendarUpcomingInput,
            output_model=CalendarUpcomingOutput,
            handler=calendar_list_upcoming,
            required_permissions={CALENDAR_READ},
            required_oauth_scopes={CALENDAR_READONLY_SCOPE},
            rate_limit_per_minute=30,
            max_attempts=3,
        )
    ]
