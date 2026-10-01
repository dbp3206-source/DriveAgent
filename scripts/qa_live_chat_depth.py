"""Small, quota-bounded live QA for synthetic chat and multi-turn depth.

Uses no Gmail, Drive, local-file, or memory source and persists no QA artifact.
Chat turns remain in the owner's normal local conversation history.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from app.db.session import SessionFactory, settings
from app.services.provider_credentials import active_gemini_key
from app.services.quota import QuotaGuard
from evaluate_gate2_live import _session_cookie, _tool_names
from qa_google_read_smoke import _connected_owner_id

BASE_URL = "http://127.0.0.1:8000"
MODEL = settings.gemini_chat_model
SOFT_RESERVE_FLOOR = 13
CASES = [
    (
        "inventory_decision",
        (
            "Tình huống giả lập, không dùng dữ liệu ngoài: kho có 1.600 sản phẩm; nhu cầu "
            "trung bình 420/tuần, có thể dao động ±100; lead time 3 tuần; safety stock 250; "
            "đơn nhập 500 chiếc dự kiến đến sau 2 tuần. Tính nhu cầu kỳ vọng trong lead time, "
            "tồn dự kiến cuối kỳ, phần đệm so với safety stock và nêu rõ giả định. Viết một "
            "bản tư vấn tiếng Việt chuyên sâu 700–900 từ: phân tích rủi ro theo kịch bản, "
            "phân biệt dữ kiện với suy luận, đề xuất hành động khả thi và trigger định lượng; "
            "không bịa chi phí hay độ chắc chắn."
        ),
        None,
    ),
    (
        "onboarding_root_cause",
        (
            "Tình huống giả lập: churn tháng của người dùng mới tăng từ 3,1% ở control lên "
            "5,1% ở nhóm thấy onboarding mới (n=420); người dùng trưởng thành là 2,1% control "
            "và 2,2% treatment (n=1.200). Trong nhóm mới, 63% dùng Safari; completion của "
            "Safari là 62%, Chrome là 81%. Chưa có phân bổ ngẫu nhiên được xác nhận. Hãy viết "
            "phân tích nguyên nhân tối thiểu 600 từ, gồm kiểm tra tính hợp lệ của so sánh, "
            "giả thuyết có thể/không thể kết luận, phép tính chênh lệch theo nhóm, kiểm tra dữ "
            "liệu cần làm, kế hoạch triage 48 giờ và thiết kế thử nghiệm xác nhận. Không khẳng "
            "định Safari hoặc onboarding là nguyên nhân đã chứng minh."
        ),
        None,
    ),
    (
        "onboarding_followup_no_rollback",
        (
            "Cập nhật ràng buộc cho cùng tình huống: không thể rollback onboarding trong 3 "
            "tuần vì phải chờ duyệt app store. Hãy tiếp tục dựa trên số liệu đã nêu, không lặp "
            "lại báo cáo trước. Đưa ra kế hoạch giảm rủi ro có thể thực hiện trong tuần này "
            "mà không cần rollback; chia việc theo 24 giờ/tuần này/3 tuần, nêu chủ sở hữu "
            "dạng vai trò, chỉ số theo dõi, ngưỡng dừng hoặc escalation, và phần nào cần thử "
            "nghiệm trước. Nếu một đề xuất cần quyền/kỹ thuật chưa biết, ghi rõ phụ thuộc."
        ),
        "onboarding_root_cause",
    ),
]


async def _runtime_credential(owner_id: str) -> str:
    async with SessionFactory() as db:
        stored = await active_gemini_key(db, owner_id, settings)
    return stored[1] if stored else settings.gemini_api_key


def _reservation_count(credential: str) -> tuple[str, int]:
    day = datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    used = QuotaGuard(
        settings.data_dir / "quota.db", credential=credential
    ).daily_count("flash")
    return day, used


def _post_chat(cookie: str, message: str, session_id: str | None) -> dict:
    body = json.dumps(
        {
            "message": message,
            "model": MODEL,
            "session_id": session_id,
            "controls": {"source": "general", "agent": "auto", "output": "chat"},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}/api/chat",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Cookie": f"drive_agent_session={cookie}",
        },
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def main(*, resume_followup: str | None = None, selected_case: str | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    owner_id = _connected_owner_id()
    credential = asyncio.run(_runtime_credential(owner_id))
    cookie = _session_cookie(owner_id)
    outputs = []
    sessions: dict[str, str] = {}
    selected_cases = CASES
    if resume_followup:
        selected_cases = [CASES[2]]
    elif selected_case:
        selected_cases = [case for case in CASES if case[0] == selected_case]
    for case_id, prompt, followup_of in selected_cases:
        pacific_day, used = _reservation_count(credential)
        if used >= SOFT_RESERVE_FLOOR:
            print(
                json.dumps(
                    {
                        "status": "stopped_conservative_quota_floor",
                        "pacific_day": pacific_day,
                        "used": used,
                        "results": outputs,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2
        session_id = (
            resume_followup
            if case_id == "onboarding_followup_no_rollback" and resume_followup
            else sessions.get(followup_of) if followup_of else None
        )
        try:
            result = _post_chat(cookie, prompt, session_id)
        except urllib.error.HTTPError as exc:
            outputs.append(
                {
                    "case": case_id,
                    "status": "http_error",
                    "http_status": exc.code,
                    "session_id": session_id,
                }
            )
            break
        except (TimeoutError, OSError) as exc:
            outputs.append(
                {"case": case_id, "status": "transport_error", "type": type(exc).__name__}
            )
            break
        answer = str(result.get("answer") or "")
        actual_session = str(result.get("session_id") or "")
        if not followup_of and actual_session:
            sessions[case_id] = actual_session
        outputs.append(
            {
                "case": case_id,
                "status": result.get("status"),
                "session_reused": bool(followup_of and actual_session == session_id),
                "answer_chars": len(answer),
                "answer_words": len(answer.split()),
                "citation_count": len(result.get("citations") or []),
                "tool_calls": _tool_names(result),
                "answer": answer,
            }
        )
        if case_id == "inventory_decision":
            oracle_passed = all(re.search(rf"\b{value}\b", answer) for value in ("840", "590"))
            oracle_passed = oracle_passed and "410" not in answer and "…" not in answer
            outputs[-1]["numeric_oracle_passed"] = oracle_passed
        if result.get("status") != "completed" or not actual_session:
            break
    _, final_used = _reservation_count(credential)
    print(
        json.dumps(
            {
                "status": "completed" if len(outputs) == len(selected_cases) and all(
                    item.get("status") == "completed" and item.get("numeric_oracle_passed", True)
                    for item in outputs
                ) else "incomplete",
                "model_requested": MODEL,
                "pacific_day": _reservation_count(credential)[0],
                "reservations_used_after": final_used,
                "results": outputs,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    cloud_tool_names = ("gmail", "drive", "local_source", "memory")
    return 0 if len(outputs) == len(selected_cases) and all(
        item.get("status") == "completed"
        and item.get("numeric_oracle_passed", True)
        and not any(
            name.startswith(cloud_tool_names) for name in item.get("tool_calls", [])
        )
        for item in outputs
    ) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resume-followup",
        metavar="SESSION_ID",
        help="retry only the synthetic follow-up in its existing local chat session",
    )
    parser.add_argument(
        "--case",
        choices=[case_id for case_id, _prompt, followup in CASES if followup is None],
        help="run one synthetic case within the conservative quota floor",
    )
    args = parser.parse_args()
    raise SystemExit(main(resume_followup=args.resume_followup, selected_case=args.case))
