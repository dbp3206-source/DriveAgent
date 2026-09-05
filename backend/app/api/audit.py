"""Audit API. User thường chỉ xem log của mình, super admin xem được toàn hệ thống."""

import json

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import AuditResponse
from app.auth.permissions import AUDIT_READ_ALL, permissions_for_role
from app.db.models import AuditEvent

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditResponse])
async def list_audit_events(
    user: CurrentUser,
    db: DbSession,
    tool: str | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    statement = select(AuditEvent)
    if AUDIT_READ_ALL not in permissions_for_role(user.role):
        statement = statement.where(AuditEvent.user_id == user.id)
    if tool:
        statement = statement.where(AuditEvent.tool_name == tool)
    if status:
        statement = statement.where(AuditEvent.status == status)
    rows = list(
        (await db.scalars(statement.order_by(AuditEvent.created_at.desc()).limit(limit))).all()
    )
    return [
        AuditResponse(
            id=row.id,
            request_id=row.request_id,
            user_email=row.user_email,
            role=row.role,
            tool_name=row.tool_name,
            arguments=json.loads(row.arguments_json or "{}"),
            result=json.loads(row.result_json or "{}"),
            status=row.status,
            latency_ms=row.latency_ms,
            error_type=row.error_type,
            error_message=row.error_message,
            created_at=row.created_at,
        )
        for row in rows
    ]
