"""FastAPI dependencies dùng chung cho authentication và authorization."""

from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import permissions_for_role
from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request, db: DbSession, settings: Annotated[Settings, Depends(get_settings)]
) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bạn chưa đăng nhập.")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập không còn hợp lệ.",
        )
    if not settings.beta_identity_allowed(user.email, user.role):
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản hoặc vai trò không được phép trong closed beta.",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(permission: str):  # type: ignore[no-untyped-def]
    async def dependency(user: CurrentUser) -> User:
        if permission not in permissions_for_role(user.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Vai trò {user.role} không có quyền {permission}.",
            )
        return user

    return dependency


def is_trusted_ui_origin(request: Request, settings) -> bool:
    """Xác thực yêu cầu xuất phát từ giao diện người dùng đáng tin cậy."""

    def parsed_origin(value: str) -> tuple[str, str, int] | None:
        try:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                return None
            if parsed.username or parsed.password:
                return None
            return parsed.scheme, parsed.hostname.casefold(), parsed.port or (
                443 if parsed.scheme == "https" else 80
            )
        except ValueError:
            return None

    trusted_urls = [settings.frontend_origin, settings.public_base_url]
    if settings.is_local_environment:
        trusted_urls.extend(
            [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:8000",
                "http://127.0.0.1:8000",
            ]
        )
    trusted = {origin for value in trusted_urls if (origin := parsed_origin(value))}
    origin_header = request.headers.get("origin") or ""
    if origin_header:
        # An explicit foreign Origin must not be overridden by a plausible
        # Referer, localhost Host or freely supplied AJAX header.
        try:
            parsed = urlsplit(origin_header)
        except ValueError:
            return False
        return (
            not parsed.path
            and not parsed.query
            and not parsed.fragment
            and parsed_origin(origin_header) in trusted
        )
    referer = request.headers.get("referer") or ""
    if referer:
        return parsed_origin(referer) in trusted
    if not settings.is_local_environment:
        return False
    host = (request.headers.get("host") or "").rstrip("/")
    if host in {"localhost:8000", "127.0.0.1:8000", "localhost:5173", "127.0.0.1:5173"}:
        return True
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return True
    sec_site = request.headers.get("sec-fetch-site")
    if sec_site in {"same-origin", "same-site", "none"}:
        return True
    return False
