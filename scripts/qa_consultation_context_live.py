"""Bounded real Chat: synthetic consultation context, no Google writes or source reads."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError

from evaluate_gate2_live import _session_cookie, _tool_names
from qa_google_read_smoke import _connected_owner_id
from qa_live_chat_depth import _post_chat, _reservation_count, _runtime_credential

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = [
    "Tình huống tư vấn giả lập, chỉ dùng dữ kiện tôi cung cấp, không đọc nguồn ngoài "
    "và không lưu bộ nhớ dài hạn. Khách hàng tên Sao Mai Mẫu QA, có 27 nhân viên, "
    "cuộc hẹn ngày 15/10/2026. Chưa biết ngân sách. Trả lời ngắn dưới dạng JSON "
    "với đúng các khóa: customer, employees, meeting_date (YYYY-MM-DD), budget "
    "(null nếu chưa biết). Không suy đoán dữ liệu thiếu.",
    "Sửa số nhân viên thành 42, giữ nguyên các thông tin khác. "
    "Trả lại JSON cùng cấu trúc, không đọc nguồn ngoài hay lưu bộ nhớ.",
    "Tiếp tục hồ sơ đó: nhắc lại tên khách hàng, số nhân viên đã sửa, "
    "ngày hẹn và ngân sách theo JSON cùng cấu trúc. Không đọc nguồn ngoài hay lưu bộ nhớ.",
]


def parse_answer(answer: str) -> dict:
    text = answer.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def main() -> int:
    owner = _connected_owner_id()
    credential = asyncio.run(_runtime_credential(owner))
    cookie = _session_cookie(owner)
    session = None
    turns = []
    for index, prompt in enumerate(PROMPTS):
        if _reservation_count(credential)[1] >= 13:
            turns.append(
                {"turn": index + 1, "status": "quota_budget_stop", "passed": False}
            )
            break
        started = time.perf_counter()
        try:
            result = _post_chat(cookie, prompt, session)
            actual_session = result.get("session_id")
            tools = _tool_names(result)
            forbidden = any(
                name.startswith(("gmail", "drive", "memory", "local_source"))
                for name in tools
            )
            expected = {
                "customer": "Sao Mai Mẫu QA",
                "employees": 27 if index == 0 else 42,
                "meeting_date": "2026-10-15",
                "budget": None,
            }
            try:
                actual = parse_answer(result.get("answer", ""))
            except (ValueError, IndexError):
                actual = None
            passed = (
                result.get("status") == "completed"
                and actual == expected
                and bool(actual_session)
                and (session is None or session == actual_session)
                and not forbidden
            )
            turns.append(
                {
                    "turn": index + 1,
                    "status": result.get("status"),
                    "passed": passed,
                    "tools": tools,
                    "actual": actual,
                    "latency_seconds": round(time.perf_counter() - started, 3),
                    "session_reused": session is not None and session == actual_session,
                }
            )
            session = actual_session
            if not passed:
                break
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            turns.append(
                {
                    "turn": index + 1,
                    "status": "request_error",
                    "passed": False,
                    "error_type": type(exc).__name__,
                    "http_status": getattr(exc, "code", None),
                }
            )
            break
    report = {
        "scope": "three_turn_synthetic_consultation_not_full_acceptance",
        "run_at": datetime.now(UTC).isoformat(),
        "turns": turns,
        "passed": len(turns) == len(PROMPTS) and all(item["passed"] for item in turns),
    }
    output = ROOT / "design-work" / "qa" / "RELEASE-20261002"
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"consultation-context-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "turn_count": len(turns),
                "report": path.name,
                "statuses": [item["status"] for item in turns],
            }
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
