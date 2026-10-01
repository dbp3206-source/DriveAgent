"""Encrypted local provider-key storage without exposing plaintext secrets."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import decrypt_json, encrypt_json
from app.db.models import ProviderCredential
from app.services.relational_circuit import circuit_store
from app.services.relational_quota import quota_guard

MAX_GEMINI_CREDENTIALS = 5


def credential_fingerprint(secret: str) -> str:
    normalized = secret.strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


def encrypt_provider_secret(secret: str, settings: Settings) -> str:
    return encrypt_json({"api_key": secret.strip()}, settings)


def decrypt_provider_secret(row: ProviderCredential, settings: Settings) -> str:
    value = decrypt_json(row.encrypted_secret, settings).get("api_key")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Credential đã lưu không hợp lệ.")
    return value.strip()


async def list_gemini_credentials(db: AsyncSession, user_id: str) -> list[ProviderCredential]:
    rows = await db.scalars(
        select(ProviderCredential)
        .where(
            ProviderCredential.user_id == user_id,
            ProviderCredential.provider == "gemini",
        )
        .order_by(ProviderCredential.is_active.desc(), ProviderCredential.created_at.asc())
    )
    return list(rows)


async def active_gemini_key(
    db: AsyncSession, user_id: str, settings: Settings
) -> tuple[str, str] | None:
    row = await db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.user_id == user_id,
            ProviderCredential.provider == "gemini",
            ProviderCredential.is_active.is_(True),
        )
    )
    if not row:
        return None
    return row.id, decrypt_provider_secret(row, settings)


def _credential_locally_available(secret: str, settings: Settings) -> bool:
    budget = quota_guard(settings, credential=secret).snapshot("flash")
    circuits = circuit_store(settings, secret).snapshot()
    return bool(
        int(budget["daily_remaining"]) > 0
        and int(budget["minute_used"]) < int(budget["minute_limit"])
        and not any(item["circuit_open"] for item in circuits)
    )


async def effective_gemini_key(
    db: AsyncSession, user_id: str, settings: Settings
) -> tuple[str, str, bool] | None:
    """Resolve active key, or an explicitly opted-in local failover key.

    Failover happens only before a request when the local budget/circuit already
    proves the active project unavailable. It never replays a partially emitted
    model response or a Google write.
    """

    rows = await list_gemini_credentials(db, user_id)
    active = next((row for row in rows if row.is_active), None)
    if active is None:
        return None
    active_secret = decrypt_provider_secret(active, settings)
    if _credential_locally_available(active_secret, settings) or not active.failover_enabled:
        return active.id, active_secret, False
    for candidate in rows:
        if (
            candidate.id != active.id
            and candidate.status == "ready"
            and candidate.failover_enabled
        ):
            secret = decrypt_provider_secret(candidate, settings)
            if _credential_locally_available(secret, settings):
                return candidate.id, secret, True
    return active.id, active_secret, False


async def alternate_gemini_key(
    db: AsyncSession,
    user_id: str,
    settings: Settings,
    *,
    exclude_credential_ids: set[str],
) -> tuple[str, str] | None:
    """Return one opted-in, locally available alternate after a clean failure."""

    rows = await list_gemini_credentials(db, user_id)
    active = next((row for row in rows if row.is_active), None)
    if active is None or not active.failover_enabled:
        return None
    for candidate in rows:
        if (
            candidate.id not in exclude_credential_ids
            and candidate.status == "ready"
            and candidate.failover_enabled
        ):
            secret = decrypt_provider_secret(candidate, settings)
            if _credential_locally_available(secret, settings):
                return candidate.id, secret
    return None


def mark_validated(row: ProviderCredential) -> None:
    row.status = "ready"
    row.last_error_class = None
    row.last_validated_at = datetime.now(UTC)
