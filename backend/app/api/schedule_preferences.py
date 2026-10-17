"""Per-user opt-in controls for recurring Google-source briefings."""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import update

from app.api.dependencies import CurrentUser, DbSession
from app.db.models import ScheduledJob, User

router = APIRouter(prefix="/api/settings/schedules", tags=["schedule-preferences"])


class SchedulePreferences(BaseModel):
    morning_enabled: bool
    pre_meeting_enabled: bool


class SchedulePreferencesUpdate(SchedulePreferences):
    model_config = ConfigDict(extra="forbid")


def _view(user: User) -> SchedulePreferences:
    return SchedulePreferences(
        morning_enabled=user.scheduled_morning_enabled,
        pre_meeting_enabled=user.scheduled_pre_meeting_enabled,
    )


@router.get("", response_model=SchedulePreferences)
async def get_schedule_preferences(user: CurrentUser) -> SchedulePreferences:
    return _view(user)


@router.put("", response_model=SchedulePreferences)
async def update_schedule_preferences(
    payload: SchedulePreferencesUpdate, user: CurrentUser, db: DbSession
) -> SchedulePreferences:
    user.scheduled_morning_enabled = payload.morning_enabled
    user.scheduled_pre_meeting_enabled = payload.pre_meeting_enabled

    disabled_kinds = []
    if not payload.morning_enabled:
        disabled_kinds.append("morning")
    if not payload.pre_meeting_enabled:
        disabled_kinds.append("pre_meeting")
    if disabled_kinds:
        await db.execute(
            update(ScheduledJob)
            .where(
                ScheduledJob.user_id == user.id,
                ScheduledJob.kind.in_(disabled_kinds),
                ScheduledJob.status == "queued",
            )
            .values(
                status="cancelled",
                error_code="schedule_disabled",
                lease_until=None,
                lease_token=None,
                updated_at=datetime.now(UTC),
            )
        )
    await db.commit()
    await db.refresh(user)
    return _view(user)
