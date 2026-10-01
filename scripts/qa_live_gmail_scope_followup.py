"""One bounded real follow-up: expand today's skill sources to latest five mails."""

import asyncio
import json
import sqlite3
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from qa_google_read_smoke import DB, _connected_owner_id, _cookie
from qa_live_chat_depth import _reservation_count, _runtime_credential, settings

root = Path(__file__).resolve().parents[1]
owner = _connected_owner_id()
_, used = _reservation_count(asyncio.run(_runtime_credential(owner)))
if used >= 13:
    raise SystemExit("Conservative reserve floor reached; no model request sent")
with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as db:
    session = db.execute(
        "SELECT session_id FROM messages WHERE user_id=? AND role='user' "
        "AND content LIKE 'Dùng skill daily_news_brief%' "
        "ORDER BY created_at DESC LIMIT 1",
        (owner,),
    ).fetchone()
if not session:
    raise SystemExit("Daily skill session missing")
body = {
    "message": "Bây giờ đổi phạm vi: tóm tắt 5 email gần nhất trong Gmail của tôi, "
    "không giới hạn người gửi hay ngày hôm nay và không chỉ lấy ba thư Bản chi tiết trước đó. "
    "Nêu số thư thực đọc, tóm tắt từng thư với nguồn riêng. Không thay đổi Gmail.",
    "session_id": session[0],
    # This QA verifies scope replacement, not an experimental model. Use the
    # configured primary so a provider-specific fallback outage cannot be
    # mistaken for a Gmail follow-up regression.
    "model": settings.gemini_chat_model,
    "controls": {"source": "gmail", "agent": "communication", "output": "chat"},
}
request = Request(
    "http://127.0.0.1:8000/api/chat",
    data=json.dumps(body).encode(),
    method="POST",
    headers={
        "Content-Type": "application/json",
        "Cookie": "drive_agent_session=" + _cookie(),
    },
)
try:
    with urlopen(request, timeout=90) as response:
        payload = json.loads(response.read())
except HTTPError as exc:
    payload = {"status": "http_error", "http_status": exc.code}
evidence = root / "design-work/qa/private/gmail-scope-followup-native-20260930.json"
evidence.parent.mkdir(parents=True, exist_ok=True)
evidence.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(
    json.dumps(
        {
            "status": payload.get("status"),
            "http_status": payload.get("http_status"),
            "citation_count": len(payload.get("citations", [])),
            "answer_chars": len(payload.get("answer", "")),
            "session_reused": payload.get("session_id") == session[0],
        }
    )
)
raise SystemExit(0 if payload.get("status") == "completed" else 1)
