"""One-shot, read-only live QA of the saved daily Gmail skill.

Creates a normal local chat turn and may consume model quota. It never sends,
drafts, labels, or modifies a Gmail message. Do not run repeatedly by default.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.error
import urllib.request

from evaluate_gate2_live import _session_cookie, _tool_names
from qa_google_read_smoke import _connected_owner_id

from app.core.config import APPROVED_GEMINI_MODELS
from app.db.session import SessionFactory, settings
from app.services.provider_credentials import active_gemini_key
from app.services.quota import QuotaGuard


def main(model: str = "gemini-3.5-flash-lite") -> int:
    # Windows PowerShell may expose cp1252 even when the tested answer is UTF-8.
    # Keep Vietnamese QA output from crashing after a successful persisted turn.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    owner_id = _connected_owner_id()

    async def runtime_credential() -> str:
        async with SessionFactory() as db:
            stored = await active_gemini_key(db, owner_id, settings)
        return stored[1] if stored else settings.gemini_api_key

    credential = asyncio.run(runtime_credential())
    used = QuotaGuard(
        settings.data_dir / "quota.db", credential=credential
    ).daily_count("flash")
    if used > 13:
        print(json.dumps({"status": "skipped_conservative_quota", "used": used}))
        return 2

    body = json.dumps(
        {
            "message": (
                "Dùng skill daily_news_brief để tổng hợp tất cả email “Bản chi tiết” "
                "của Bảo Phúc Đinh đã nhận hôm nay đến thời điểm hiện tại thành báo cáo "
                "chi tiết. Ghi rõ số thư thực tế, dẫn nguồn, không ép đủ mốc 8h/12h/15h/21h."
            ),
            "model": model,
            "controls": {
                "source": "gmail",
                "agent": "communication",
                "skill_name": "daily_news_brief",
            },
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:8000/api/chat",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Cookie": f"drive_agent_session={_session_cookie(owner_id)}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(json.dumps({"status": "http_error", "http_status": exc.code}))
        return 1
    except (TimeoutError, OSError) as exc:
        print(
            json.dumps({"status": "transport_error", "error_type": type(exc).__name__})
        )
        return 1
    answer = str(result.get("answer") or "")
    print(
        json.dumps(
            {
                "status": result.get("status"),
                "answer_chars": len(answer),
                "citation_count": len(result.get("citations") or []),
                "tools": _tool_names(result),
                "answer": answer,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        choices=sorted(APPROVED_GEMINI_MODELS),
        default="gemini-3.5-flash-lite",
    )
    raise SystemExit(main(parser.parse_args().model))
