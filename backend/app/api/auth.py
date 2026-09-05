"""REST endpoints cho Google OAuth2."""

import asyncio
import json
import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from requests.exceptions import ConnectionError as GoogleConnectionError
from requests.exceptions import Timeout as GoogleTimeout
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AuthStatusResponse, UserResponse
from app.auth.google_oauth import (
    build_flow,
    credentials_to_dict,
    fetch_google_profile,
)
from app.core.config import Settings, get_settings
from app.core.security import decrypt_json, encrypt_json
from app.db.models import User, UserRole
from app.db.session import get_db

router = APIRouter(prefix="/api/auth", tags=["authentication"])
logger = logging.getLogger(__name__)


def user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        role=user.role,
        scopes=json.loads(user.oauth_scopes_json or "[]"),
    )


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthStatusResponse:
    user = None
    if user_id := request.session.get("user_id"):
        user = await db.get(User, user_id)
    return AuthStatusResponse(
        authenticated=bool(user and user.is_active),
        oauth_configured=settings.oauth_is_configured,
        gemini_configured=settings.gemini_is_configured,
        demo_login_enabled=settings.enable_demo_login and settings.environment == "development",
        user=user_response(user) if user and user.is_active else None,
    )


@router.post("/demo")
async def demo_login(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Tạo user QA local. Endpoint không tồn tại về mặt hành vi khi flag mặc định tắt."""

    if settings.environment != "development" or not settings.enable_demo_login:
        raise HTTPException(status_code=404, detail="Demo login không được bật.")
    user = await db.scalar(select(User).where(User.email == "demo@driveagent.local"))
    if not user:
        user = User(
            email="demo@driveagent.local",
            display_name="Nguyễn Minh An",
            role=UserRole.SUPER_ADMIN.value,
            oauth_scopes_json="[]",
        )
        db.add(user)
        await db.commit()
    request.session["user_id"] = user.id
    return user_response(user)


@router.get("/google")
async def google_login(request: Request, settings: Settings = Depends(get_settings)):
    try:
        flow = build_flow(settings)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    nonce = secrets.token_urlsafe(24)
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=nonce,
    )
    request.session["oauth_state"] = state
    # Flow được tạo lại ở callback. Giữ verifier của đúng lần đăng nhập này;
    # mã hóa trước khi lưu vì session cookie được ký nhưng không tự mã hóa.
    request.session["oauth_pkce"] = encrypt_json({"verifier": flow.code_verifier}, settings)
    return RedirectResponse(authorization_url)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    expected_state = request.session.pop("oauth_state", None)
    encrypted_pkce = request.session.pop("oauth_pkce", None)
    returned_state = request.query_params.get("state")
    if not expected_state or not secrets.compare_digest(expected_state, returned_state or ""):
        raise HTTPException(status_code=400, detail="OAuth state không hợp lệ.")
    flow = build_flow(settings, state=expected_state)
    try:
        flow.code_verifier = decrypt_json(encrypted_pkce, settings)["verifier"]
        if not flow.code_verifier:
            raise ValueError("Missing verifier")
    except (ValueError, TypeError, KeyError):
        raise HTTPException(
            status_code=400, detail="Phiên đăng nhập đã cũ. Về trang chủ và kết nối Google lại."
        ) from None
    try:
        # google-auth-oauthlib dùng HTTP đồng bộ. Chạy ở worker thread để một callback
        # OAuth chậm không chặn các request của người dùng khác trên event loop.
        await asyncio.to_thread(
            flow.fetch_token, authorization_response=str(request.url), timeout=20
        )
        credentials = flow.credentials
        profile = await fetch_google_profile(credentials.token)
    except (GoogleConnectionError, GoogleTimeout, httpx.TransportError) as exc:
        logger.warning("Google OAuth network failure: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Server chưa kết nối được Google. Kiểm tra mạng server rồi kết nối Google lại.",
        ) from None
    except Exception as exc:
        # Provider error có thể chứa chi tiết request nhạy cảm. Chỉ ghi server log,
        # không phản chiếu nguyên văn về trình duyệt.
        logger.error("Google OAuth callback failure: %s", type(exc).__name__)
        raise HTTPException(
            status_code=400,
            detail="Google OAuth thất bại. Kiểm tra cấu hình và log server.",
        ) from exc

    email = profile.get("email")
    if not email or not profile.get("email_verified", False):
        raise HTTPException(status_code=400, detail="Google chưa xác minh email của tài khoản.")
    user = await db.scalar(select(User).where(User.email == email))
    if not user:
        total_users = await db.scalar(select(func.count()).select_from(User)) or 0
        user = User(
            email=email,
            display_name=profile.get("name") or email.split("@")[0],
            avatar_url=profile.get("picture"),
            role=(UserRole.SUPER_ADMIN.value if total_users == 0 else UserRole.EDITOR.value),
        )
        db.add(user)
    previous_refresh_token = None
    if user.encrypted_google_credentials:
        previous_refresh_token = decrypt_json(user.encrypted_google_credentials, settings).get(
            "refresh_token"
        )
    credential_payload = credentials_to_dict(credentials)
    credential_payload["refresh_token"] = (
        credential_payload.get("refresh_token") or previous_refresh_token
    )
    user.display_name = profile.get("name") or user.display_name
    user.avatar_url = profile.get("picture")
    user.oauth_scopes_json = json.dumps(list(credentials.scopes or []))
    user.encrypted_google_credentials = encrypt_json(credential_payload, settings)
    await db.commit()
    request.session["user_id"] = user.id
    return RedirectResponse(f"{settings.frontend_origin}/?connected=1")


@router.post("/logout", status_code=204)
async def logout(request: Request):
    request.session.clear()
