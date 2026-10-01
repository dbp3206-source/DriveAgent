"""Read-only model availability probe. Never prints credentials or private data."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


async def run():
    from google import genai
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.models import User
    from app.db.session import SessionFactory, engine
    from app.services.provider_credentials import active_gemini_key

    client = None
    try:
        settings = get_settings()
        async with SessionFactory() as db:
            owners = list(await db.scalars(select(User).where(
                User.role == "super_admin", User.is_active.is_(True),
                User.encrypted_google_credentials.is_not(None),
                User.encrypted_google_credentials != "")))
            if len(owners) != 1:
                return {"status": "NOT VERIFIED", "reason": "unique_owner_required"}
            credential = await active_gemini_key(db, owners[0].id, settings)
            if not credential:
                return {"status": "NOT VERIFIED", "reason": "active_byok_required"}
            client = genai.Client(api_key=credential[1], http_options={"timeout": 15000})
            names = []
            async for model in await client.aio.models.list():
                if model.name and "gemini-2.5-flash" in model.name:
                    names.append(model.name)
            expected = f"models/{settings.gemini_web_research_model}"
            return {"status": "model_list_received", "expected_model": expected,
                    "listed": expected in names, "matching_models": names,
                    "grounding_and_free_tier_verified": False}
    except (genai.errors.APIError, OSError, RuntimeError, ValueError) as exc:
        return {"status": "FAIL", "cause_type": type(exc).__name__,
                "provider_code": getattr(exc, "code", None)}
    finally:
        if client:
            await client.aio.aclose()
            client.close()
        await engine.dispose()


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run())))
