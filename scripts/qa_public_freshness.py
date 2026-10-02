"""One real public grounding request through the harness; no private content exported."""

import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


async def run() -> dict:
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.models import User
    from app.db.session import SessionFactory, engine
    from app.services.provider_credentials import active_gemini_key
    from app.services.quota import QuotaGuard
    from app.tools.contracts import ToolContext, ToolError
    from app.tools.registry import ToolRegistry
    from app.tools.web_research import web_research_tool_definitions

    settings = get_settings()
    started = time.monotonic()
    request_id = str(uuid4())
    try:
        async with SessionFactory() as db:
            owners = list(
                await db.scalars(
                    select(User).where(
                        User.role == "super_admin",
                        User.is_active.is_(True),
                        User.encrypted_google_credentials.is_not(None),
                        User.encrypted_google_credentials != "",
                    )
                )
            )
            if len(owners) != 1:
                return {"status": "NOT VERIFIED", "reason": "unique_owner_required"}
            owner = owners[0]
            selected = await active_gemini_key(db, owner.id, settings)
            if not selected:
                return {"status": "NOT VERIFIED", "reason": "owner_byok_required"}
            settings = settings.model_copy(update={"gemini_api_key": selected[1]})
            budget = QuotaGuard(settings.data_dir / "quota.db", credential=selected[1])
            if budget.snapshot("flash")["daily_remaining"] <= 1:
                return {
                    "status": "NOT VERIFIED",
                    "reason": "conservative_budget_reserved",
                }
            registry = ToolRegistry()
            for definition in web_research_tool_definitions():
                registry.register(definition)
            try:
                output = await registry.execute(
                    "web_research",
                    {
                        "question": "Lịch thi đấu bóng đá nam ASIAD hôm nay là gì? "
                        "Chỉ xác nhận lịch có nguồn, nếu chưa xác minh được hãy nói rõ.",
                        "timezone": settings.local_timezone,
                    },
                    ToolContext(
                        request_id=request_id, user=owner, db=db, settings=settings
                    ),
                )
                return {
                    "status": "public_response_received",
                    "request_id": request_id,
                    "model": output.model,
                    "sources": len(output.sources),
                    "answer_characters": len(output.summary),
                    "answer": output.summary,
                    "source_details": [source.model_dump(mode="json") for source in output.sources],
                    "collection_method": (
                        "public_source_bundle" if output.model.endswith("+source-bundle")
                        else "google_search_grounding"
                    ),
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                    "claim_truth_review": "NOT VERIFIED",
                    "observed_at": output.observed_at.isoformat(),
                }
            except ToolError as exc:
                cause = exc.__cause__
                return {
                    "status": "FAIL",
                    "code": exc.code,
                    "request_id": request_id,
                    "cause_type": type(cause).__name__ if cause else None,
                    "provider_code": getattr(cause, "code", None),
                    "provider_message": str(getattr(cause, "message", "") or "")
                    .replace(selected[1], "[REDACTED]")[:600],
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                }
    finally:
        await engine.dispose()


if __name__ == "__main__":
    result = asyncio.run(run())
    directory = ROOT / "design-work/qa/RELEASE-20261002"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"public-freshness-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items()
                      if key not in {"answer", "source_details"}}, ensure_ascii=False))
    print(json.dumps({"report": path.name}))
    raise SystemExit(0 if result["status"] == "public_response_received" else 1)
