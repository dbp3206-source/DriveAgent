"""Audit API. User thường chỉ xem log của mình, super admin xem được toàn hệ thống."""

from datetime import UTC

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, or_, select

from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import AuditPage, AuditResponse
from app.auth.permissions import AUDIT_READ_ALL, permissions_for_role
from app.core.cursor import decode_cursor, encode_cursor
from app.core.json_utils import json_object
from app.db.models import AuditEvent

router = APIRouter(prefix="/api/audit", tags=["audit"])


def _serialize(row: AuditEvent) -> AuditResponse:
    return AuditResponse(
        id=row.id,
        request_id=row.request_id,
        user_email=row.user_email,
        role=row.role,
        tool_name=row.tool_name,
        arguments=json_object(row.arguments_json),
        result=json_object(row.result_json),
        status=row.status,
        latency_ms=row.latency_ms,
        error_type=row.error_type,
        error_message=row.error_message,
        created_at=(
            row.created_at.replace(tzinfo=UTC)
            if row.created_at.tzinfo is None
            else row.created_at
        ),
    )


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
    return [_serialize(row) for row in rows]


@router.get("/page", response_model=AuditPage)
async def list_audit_page(
    user: CurrentUser,
    db: DbSession,
    tool: str | None = None,
    status: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
):
    statement = select(AuditEvent)
    if AUDIT_READ_ALL not in permissions_for_role(user.role):
        statement = statement.where(AuditEvent.user_id == user.id)
    if tool:
        statement = statement.where(AuditEvent.tool_name == tool)
    if status:
        statement = statement.where(AuditEvent.status == status)
    try:
        key = decode_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Cursor phân trang không hợp lệ.") from exc
    if key:
        at, row_id = key
        statement = statement.where(
            or_(
                AuditEvent.created_at < at,
                and_(AuditEvent.created_at == at, AuditEvent.id < row_id),
            )
        )
    rows = list(
        (
            await db.scalars(
                statement.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(
                    limit + 1
                )
            )
        ).all()
    )
    more = len(rows) > limit
    items = rows[:limit]
    return AuditPage(
        items=[_serialize(row) for row in items],
        next_cursor=encode_cursor(items[-1].created_at, items[-1].id) if more and items else None,
    )
