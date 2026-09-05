"""Google OAuth2 web-server flow và vòng đời credential của từng người dùng."""

import json
from datetime import UTC
from typing import Any

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import decrypt_json, encrypt_json
from app.db.models import User


class OAuthNotConfiguredError(RuntimeError):
    pass


def build_flow(settings: Settings, *, state: str | None = None) -> Flow:
    """Tạo Flow mới cho từng request để state không bị dùng chung giữa người dùng."""

    if not settings.oauth_is_configured:
        raise OAuthNotConfiguredError(
            "Chưa tìm thấy OAuth client JSON. Hãy làm theo hướng dẫn trong docs/SETUP_GOOGLE.md."
        )
    return Flow.from_client_secrets_file(
        str(settings.resolved_google_oauth_client_file),
        scopes=settings.google_drive_scopes,
        state=state,
        redirect_uri=settings.google_redirect_uri,
    )


def credentials_to_dict(credentials: Credentials) -> dict[str, Any]:
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or []),
        "expiry": credentials.expiry.astimezone(UTC).isoformat() if credentials.expiry else None,
    }


def credentials_from_user(user: User, settings: Settings) -> Credentials:
    if not user.encrypted_google_credentials:
        raise PermissionError("Tài khoản chưa kết nối Google Drive.")
    info = decrypt_json(user.encrypted_google_credentials, settings)
    return Credentials.from_authorized_user_info(info, scopes=json.loads(user.oauth_scopes_json))


async def refresh_and_store_if_needed(
    user: User, db: AsyncSession, settings: Settings
) -> Credentials:
    """Refresh access token ở worker thread vì thư viện Google dùng HTTP đồng bộ."""

    import asyncio

    credentials = credentials_from_user(user, settings)
    if credentials.expired and credentials.refresh_token:
        await asyncio.to_thread(credentials.refresh, GoogleAuthRequest())
        user.encrypted_google_credentials = encrypt_json(credentials_to_dict(credentials), settings)
        await db.commit()
    if not credentials.valid:
        raise PermissionError("Phiên Google đã hết hạn. Vui lòng kết nối lại.")
    return credentials


async def fetch_google_profile(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()
