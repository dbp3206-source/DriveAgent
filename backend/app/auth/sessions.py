"""Server-side revocation for signed login cookies (all sessions of one user)."""

import secrets

from app.db.models import User


def session_is_current(session: dict, user: User) -> bool:
    version = session.get("auth_version")
    current = getattr(user, "auth_version", None)
    return bool(
        isinstance(version, str) and isinstance(current, str) and current
        and secrets.compare_digest(version, current)
    )


def establish_session(session: dict, user: User) -> None:
    if not user.auth_version:
        user.auth_version = secrets.token_hex(32)
    session.clear()
    session.update(user_id=user.id, auth_version=user.auth_version)


def revoke_user_sessions(user: User) -> None:
    user.auth_version = secrets.token_hex(32)
