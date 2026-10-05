"""Authenticated wake endpoint intended for Supabase Cron."""

import secrets
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from app.api.dependencies import DbSession
from app.core.config import get_settings
from app.services.scheduled_jobs import enqueue_for_invited_users

router = APIRouter(prefix="/api/internal/scheduler", tags=["scheduler"])


class ScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["morning", "pre_meeting"]


def _authorize(value: str | None) -> None:
    settings = get_settings()
    configured = settings.scheduler_bearer_token
    expected = configured.get_secret_value() if configured is not None else ""
    supplied = value.removeprefix("Bearer ").strip() if value else ""
    if not expected or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@router.post("/enqueue", status_code=202)
async def enqueue_schedule(
    payload: ScheduleRequest,
    request: Request,
    db: DbSession,
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    settings = get_settings()
    now = datetime.now(ZoneInfo(settings.local_timezone))
    slot = now.strftime("%Y-%m-%d") if payload.kind == "morning" else now.strftime("%Y-%m-%dT%H")
    result = await enqueue_for_invited_users(
        db,
        settings,
        kind=payload.kind,
        dedupe_key=f"{payload.kind}:{slot}",
        registry=request.app.state.registry,
    )
    return {"status": "accepted", "request_id": request.state.request_id, **result}
