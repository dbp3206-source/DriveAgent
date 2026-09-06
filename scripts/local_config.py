"""Chuẩn bị/kiểm tra local mà không in API key hoặc OAuth secret ra terminal."""

import argparse
import json
import secrets

from app.core.config import PROJECT_ROOT, Settings
from pydantic import ValidationError
from pydantic_settings import SettingsError


def prepare() -> None:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        print("[OK] .env already exists; preserved.")
        return
    template = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    template = template.replace(
        "DRIVE_AGENT_APP_SECRET=", f"DRIVE_AGENT_APP_SECRET={secrets.token_urlsafe(48)}"
    ).replace("http://localhost:5173", "http://localhost:8000")
    # Exclusive creation prevents accidentally replacing an existing encryption key.
    with env_path.open("x", encoding="utf-8") as target:
        target.write(template)
    print("[OK] Created local .env with a random secret. No secrets printed.")


def check() -> int:
    try:
        settings = Settings()
    except (SettingsError, ValidationError, OSError):
        print("[MISSING] Invalid .env format. See docs/START_LOCAL.md.")
        return 1
    checks = {
        ".env exists": (PROJECT_ROOT / ".env").is_file(),
        "Gemini API key configured (not a live verification)": settings.gemini_is_configured,
        "Gemini chat model is approved": settings.gemini_chat_model
        in {"gemini-3.8-flash", "gemini-3.5-flash-lite"},
        "Gemini fallback model is approved": settings.gemini_fallback_model
        in {"gemini-3.8-flash", "gemini-3.5-flash-lite"},
        "Gemini Embedding 2 selected": settings.gemini_embedding_model
        == "gemini-embedding-2",
        "Random APP_SECRET configured": (
            len(settings.app_secret) >= 32
            and settings.app_secret != "local-development-change-me-before-sharing"
        ),
        "Demo login disabled": not settings.enable_demo_login,
        "Local HTTP profile": settings.environment != "production",
        "OAuth callback matches local runner": settings.google_redirect_uri
        == "http://localhost:8000/api/auth/google/callback",
        "Frontend origin matches local runner": settings.frontend_origin
        == "http://localhost:8000",
    }
    try:
        data = json.loads(settings.resolved_google_oauth_client_file.read_text(encoding="utf-8-sig"))
        web = data.get("web", {})
        valid = bool(web.get("client_id") and web.get("client_secret"))
        valid = valid and settings.google_redirect_uri in web.get("redirect_uris", [])
    except (OSError, ValueError, AttributeError, TypeError):
        valid = False
    checks["OAuth Web client JSON and redirect URI configured"] = valid
    for label, passed in checks.items():
        print(f"[{'OK' if passed else 'MISSING'}] {label}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        prepare()
    else:
        raise SystemExit(check())
