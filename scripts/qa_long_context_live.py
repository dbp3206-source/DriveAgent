"""One real model call against labelled, synthetic, persisted long Chat history.

The intermediate turns are seeded fixtures, not claimed as model-generated answers.
No Google write or long-term memory write is requested.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from evaluate_gate2_live import _session_cookie, _tool_names
from qa_consultation_context_live import parse_answer
from qa_google_read_smoke import _connected_owner_id
from qa_live_chat_depth import _post_chat, _reservation_count, _runtime_credential

from app.db.models import ChatSession, Message
from app.db.session import SessionFactory


async def seed(owner: str) -> str:
    async with SessionFactory() as db:
        session = ChatSession(user_id=owner, title="QA — lịch sử dài giả lập")
        db.add(session)
        await db.flush()
        texts = [
            "Dữ liệu giả lập tư vấn: khách hàng Sao Mai Mẫu QA, có 27 nhân viên. "
            "Ngày hẹn 15/10/2026. " + "Ghi chú bối cảnh không chứa số liệu. " * 180
            + "Ngân sách chưa biết, không được tự suy đoán ngân sách.",
            "Đã ghi nhận dữ liệu giả lập, chưa biết ngân sách.",
            "Sửa số nhân viên thành 42, các dữ kiện khác giữ nguyên.",
            "Đã ghi nhận số nhân viên là 42.",
        ]
        texts.extend(
            "Ghi chú giả lập: chỉ làm rõ câu hỏi tư vấn, chưa thêm dữ kiện khách hàng."
            for _ in range(10)
        )
        started = datetime.now(UTC) - timedelta(minutes=1)
        for index, text in enumerate(texts):
            db.add(Message(
                session_id=session.id, user_id=owner,
                role="user" if index % 2 == 0 else "assistant",
                content=text, created_at=started + timedelta(seconds=index),
            ))
        await db.commit()
        return session.id


async def seed_correction(owner: str, session: str) -> None:
    """Simulate a canonical correction made outside this framework's event store."""
    async with SessionFactory() as db:
        db.add(Message(
            session_id=session, user_id=owner, role="user",
            content="Sửa số nhân viên thành 48. Giữ tên khách hàng, ngày hẹn và ngân sách.",
        ))
        await db.commit()


def main() -> int:
    owner = _connected_owner_id()
    credential = asyncio.run(_runtime_credential(owner))
    if _reservation_count(credential)[1] >= 13:
        print(json.dumps({"status": "quota_budget_stop", "passed": False}))
        return 1
    session = asyncio.run(seed(owner))
    result = _post_chat(
        _session_cookie(owner),
        "Chỉ dùng lịch sử cuộc trò chuyện, không đọc nguồn ngoài hoặc lưu bộ nhớ. "
        "Nhắc lại hồ sơ khách hàng theo JSON, đúng các khóa customer, employees, "
        "meeting_date (YYYY-MM-DD), budget (null nếu chưa biết). "
        "Giữ những thông tin đã sửa, không suy đoán.",
        session,
    )
    try:
        actual = parse_answer(result.get("answer", ""))
    except (ValueError, IndexError):
        actual = None
    tools = _tool_names(result)
    expected = {"customer": "Sao Mai Mẫu QA", "employees": 42,
                "meeting_date": "2026-10-15", "budget": None}
    passed = (result.get("status") == "completed" and actual == expected
              and result.get("session_id") == session and not tools)
    correction = None
    if passed and _reservation_count(credential)[1] < 13:
        asyncio.run(seed_correction(owner, session))
        followup = _post_chat(
            _session_cookie(owner),
            "Nhắc lại hồ sơ sau đính chính mới nhất, cùng JSON bốn khóa. "
            "Chỉ dùng cuộc trò chuyện, không đọc nguồn ngoài hoặc lưu bộ nhớ.",
            session,
        )
        try:
            correction = parse_answer(followup.get("answer", ""))
        except (ValueError, IndexError):
            correction = None
        expected["employees"] = 48
        passed = (followup.get("status") == "completed" and correction == expected
                  and followup.get("session_id") == session and not _tool_names(followup))
    else:
        passed = False
    report = {
        "scope": "two_live_calls_with_seeded_history_and_canonical_handoff_not_full_acceptance",
        "run_at": datetime.now(UTC).isoformat(), "seeded_turns": 14,
        "first_request_over_4000_characters": True,
        "status": result.get("status"), "actual": actual,
        "tools": tools, "correction": correction, "passed": passed,
    }
    directory = Path(__file__).resolve().parents[1] / "design-work/qa/RELEASE-20261002"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"long-context-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": passed, "status": report["status"], "report": path.name}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
