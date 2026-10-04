"""Owner-only Gemini credential management for the local Settings page."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DbSession, is_trusted_ui_origin, require_permission
from app.auth.permissions import PROVIDER_CREDENTIAL_MANAGE
from app.core.config import APPROVED_GEMINI_MODELS, GEMINI_HTTP_TIMEOUT_MS, get_settings
from app.db.models import ProviderCredential, User
from app.services.provider_credentials import (
    MAX_GEMINI_CREDENTIALS,
    credential_fingerprint,
    decrypt_provider_secret,
    effective_gemini_key,
    encrypt_provider_secret,
    list_gemini_credentials,
    mark_validated,
)
from app.services.relational_circuit import circuit_store
from app.services.relational_quota import quota_guard

router = APIRouter(prefix="/api/settings/providers/gemini", tags=["provider-credentials"])
CredentialOwner = Depends(require_permission(PROVIDER_CREDENTIAL_MANAGE))


class CredentialCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    project_alias: str = Field(default="", max_length=120)
    api_key: str = Field(min_length=20, max_length=512)


class FailoverUpdate(BaseModel):
    enabled: bool


class CapacityView(BaseModel):
    configured: bool
    credential_source: str
    active_credential_id: str | None
    active_display_name: str | None
    effective_credential_id: str | None
    display_name: str | None
    project_alias: str | None
    fingerprint: str | None
    failover_active: bool
    primary_model: str
    fallback_model: str
    local_budget: dict[str, int | str] | None
    circuits: list[dict]
    provider_balance_available: bool = False
    provider_balance_note: str


class CredentialView(BaseModel):
    id: str
    display_name: str
    project_alias: str
    fingerprint: str
    status: str
    is_active: bool
    failover_enabled: bool
    last_validated_at: datetime | None
    last_error_class: str | None
    cooldown_until: datetime | None
    created_at: datetime
    daily_flash_used: int = 0
    circuit_open: bool = False
    retry_after_seconds: int = 0


def _view(row: ProviderCredential) -> CredentialView:
    settings = get_settings()
    secret = decrypt_provider_secret(row, settings)
    circuits = circuit_store(settings, secret).snapshot()
    open_states = [item for item in circuits if item["circuit_open"]]
    return CredentialView(
        id=row.id,
        display_name=row.display_name,
        project_alias=row.project_alias,
        fingerprint=row.fingerprint,
        status=row.status,
        is_active=row.is_active,
        failover_enabled=row.failover_enabled,
        last_validated_at=row.last_validated_at,
        last_error_class=row.last_error_class,
        cooldown_until=row.cooldown_until,
        created_at=row.created_at,
        daily_flash_used=quota_guard(settings, credential=secret).daily_count(
            "flash"
        ),
        circuit_open=bool(open_states),
        retry_after_seconds=max(
            (int(item["retry_after_seconds"]) for item in open_states), default=0
        ),
    )


def _require_ui(request: Request) -> None:
    if not is_trusted_ui_origin(request, get_settings()):
        raise HTTPException(403, "Chỉ có thể quản lý API key từ giao diện Veridra.")


async def _probe_key(api_key: str) -> None:
    settings = get_settings()
    client = genai.Client(
        api_key=api_key,
        vertexai=False,
        http_options=types.HttpOptions(
            timeout=GEMINI_HTTP_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    # Order models to test: primary model first, fallback next, then any remaining approved models
    probe_models = [settings.gemini_chat_model]
    if settings.gemini_fallback_model not in probe_models:
        probe_models.append(settings.gemini_fallback_model)
    for model in sorted(APPROVED_GEMINI_MODELS):
        if model not in probe_models:
            probe_models.append(model)

    last_error: Exception | None = None
    try:
        for model_name in probe_models:
            try:
                await asyncio.to_thread(client.models.get, model=model_name)
                # Successful response on any approved model confirms the key is valid and working
                return
            except errors.APIError as exc:
                last_error = exc
                code = int(getattr(exc, "code", 0) or 0)
                msg = str(getattr(exc, "message", "") or "").lower()
                # Google returns 400 (API key not valid) or 401/403 for credential errors
                if code in {401, 403} or (
                    code == 400
                    and any(
                        keyword in msg
                        for keyword in ("api key", "key", "invalid", "credential", "auth")
                    )
                ):
                    raise HTTPException(
                        400,
                        "Gemini từ chối API key này (API key không hợp lệ hoặc không có quyền).",
                    ) from exc
                if code == 429:
                    raise HTTPException(
                        429, "Key hợp lệ nhưng project đang bị giới hạn quota (429 Quota Exceeded)."
                    ) from exc
                if code in {404, 500, 502, 503, 504}:
                    # Transient provider failure or model unavailable: try the next candidate.
                    continue
                # Other deterministic errors
                raise HTTPException(
                    400, f"Gemini từ chối yêu cầu kiểm tra key: {getattr(exc, 'message', str(exc))}"
                ) from exc
            except TimeoutError as exc:
                last_error = exc
                continue

        # If all probe models returned 5xx or timeout
        raise HTTPException(
            503,
            "Cụm máy chủ Gemini đang quá tải (503 Service Unavailable). "
            "Key không bị từ chối xác thực nhưng dịch vụ Google tạm thời chưa phản hồi. "
            "Hãy thử lại sau ít phút.",
        ) from last_error
    finally:
        await client.aio.aclose()
        client.close()


@router.get("/credentials", response_model=list[CredentialView])
async def list_credentials(db: DbSession, _user: User = CredentialOwner):
    return [_view(row) for row in await list_gemini_credentials(db, _user.id)]


@router.get("/status", response_model=CapacityView)
async def capacity_status(db: DbSession, user: CurrentUser):
    settings = get_settings()
    rows = await list_gemini_credentials(db, user.id)
    active = next((row for row in rows if row.is_active), None)
    effective = await effective_gemini_key(db, user.id, settings)
    selected = None
    secret = settings.gemini_api_key.strip()
    failover_active = False
    source = "environment" if secret else "unconfigured"
    if effective is not None:
        effective_id, secret, failover_active = effective
        selected = next((row for row in rows if row.id == effective_id), None)
        source = "user"
    fallback = settings.gemini_fallback_model
    if fallback == settings.gemini_chat_model:
        fallback = next(
            model for model in sorted(APPROVED_GEMINI_MODELS) if model != settings.gemini_chat_model
        )
    return CapacityView(
        configured=bool(secret),
        credential_source=source,
        active_credential_id=active.id if active else None,
        active_display_name=active.display_name if active else None,
        effective_credential_id=selected.id if selected else None,
        display_name=selected.display_name if selected else None,
        project_alias=selected.project_alias if selected else None,
        fingerprint=selected.fingerprint if selected else None,
        failover_active=failover_active,
        primary_model=settings.gemini_chat_model,
        fallback_model=fallback,
        local_budget=(
            quota_guard(settings, credential=secret).snapshot("flash")
            if secret
            else None
        ),
        circuits=(
            circuit_store(settings, secret).snapshot()
            if secret
            else []
        ),
        provider_balance_note=(
            "Gemini không cung cấp số dư hạn mức qua kết nối này. Veridra chỉ hiển thị "
            "bộ đếm bảo vệ của ứng dụng và lỗi thực tế nhận từ Gemini."
        ),
    )


@router.post("/credentials", response_model=CredentialView, status_code=201)
async def create_credential(
    payload: CredentialCreate,
    request: Request,
    db: DbSession,
    _user: User = CredentialOwner,
):
    _require_ui(request)
    existing = await list_gemini_credentials(db, _user.id)
    if len(existing) >= MAX_GEMINI_CREDENTIALS:
        raise HTTPException(409, f"Chỉ lưu tối đa {MAX_GEMINI_CREDENTIALS} Gemini key.")
    secret = payload.api_key.strip()
    await _probe_key(secret)
    row = ProviderCredential(
        user_id=_user.id,
        provider="gemini",
        display_name=payload.display_name.strip(),
        project_alias=payload.project_alias.strip(),
        fingerprint=credential_fingerprint(secret),
        encrypted_secret=encrypt_provider_secret(secret, get_settings()),
        status="ready",
        last_validated_at=datetime.now(UTC),
        is_active=False,
        failover_enabled=True,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "API key này đã được lưu.") from exc
    await db.refresh(row)
    return _view(row)


async def _owned_row(db: DbSession, user_id: str, credential_id: str) -> ProviderCredential:
    row = await db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.id == credential_id,
            ProviderCredential.user_id == user_id,
            ProviderCredential.provider == "gemini",
        )
    )
    if not row:
        raise HTTPException(404, "Không tìm thấy credential.")
    return row


@router.post("/credentials/{credential_id}/validate", response_model=CredentialView)
async def validate_credential(
    credential_id: str,
    request: Request,
    db: DbSession,
    _user: User = CredentialOwner,
):
    _require_ui(request)
    row = await _owned_row(db, _user.id, credential_id)
    await _probe_key(decrypt_provider_secret(row, get_settings()))
    mark_validated(row)
    await db.commit()
    await db.refresh(row)
    return _view(row)


@router.put("/credentials/{credential_id}/failover", response_model=CredentialView)
async def update_failover(
    credential_id: str,
    payload: FailoverUpdate,
    request: Request,
    db: DbSession,
    _user: User = CredentialOwner,
):
    _require_ui(request)
    row = await _owned_row(db, _user.id, credential_id)
    row.failover_enabled = payload.enabled
    await db.commit()
    await db.refresh(row)
    return _view(row)


@router.post("/credentials/{credential_id}/activate", response_model=CredentialView)
async def activate_credential(
    credential_id: str,
    request: Request,
    db: DbSession,
    _user: User = CredentialOwner,
):
    _require_ui(request)
    row = await _owned_row(db, _user.id, credential_id)
    secret = decrypt_provider_secret(row, get_settings())
    # Creation/explicit validation already checked this immutable stored secret.
    # Re-probing every activation can serially wait on several unavailable model
    # endpoints and makes a harmless key switch look hung. Keep validation an
    # explicit action; probe here only for legacy/unvalidated records.
    if row.status != "ready" or row.last_validated_at is None:
        await _probe_key(secret)
        mark_validated(row)
    invalidate = getattr(request.app.state, "invalidate_user_gemini_runtime", None)
    rotate = getattr(request.app.state, "rotate_gemini_key", None)
    if invalidate is None and rotate is None:
        raise HTTPException(503, "Runtime chưa hỗ trợ chuyển key nóng.")
    await db.execute(
        update(ProviderCredential)
        .where(
            ProviderCredential.user_id == _user.id,
            ProviderCredential.provider == "gemini",
        )
        .values(is_active=False)
    )
    row.is_active = True
    await db.commit()
    await db.refresh(row)
    if invalidate is not None:
        await invalidate(_user.id)
    else:
        # Compatibility boundary for older embedded runtimes. New deployments
        # invalidate only this user's cached client instead of mutating a global key.
        await rotate(secret)
    return _view(row)


@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: str,
    request: Request,
    db: DbSession,
    _user: User = CredentialOwner,
):
    _require_ui(request)
    row = await _owned_row(db, _user.id, credential_id)
    if row.is_active:
        raise HTTPException(409, "Hãy kích hoạt key khác trước khi xóa key đang dùng.")
    await db.delete(row)
    await db.commit()
