"""Bounded live check: each explicitly named PDF must supply page evidence."""

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from qa_google_read_smoke import _cookie

request = Request(
    "http://127.0.0.1:8000/api/chat",
    data=json.dumps({
        "message": "Dựa trên hai tài liệu local Ngan-hang_20260330.pdf và "
        "DubaoKQKD_Nganhdien_20260408.pdf, so sánh các động lực tăng trưởng và rủi ro "
        "chính được nêu trong từng ngành. Tách rõ tài liệu nào hỗ trợ từng nhận định, "
        "không trộn số liệu và chỉ kết luận khi có citation theo trang.",
        "controls": {"source": "local", "agent": "research", "output": "chat"},
    }).encode(),
    headers={"Content-Type": "application/json", "Cookie": "drive_agent_session=" + _cookie()},
    method="POST",
)
try:
    with urlopen(request, timeout=120) as response:
        result = json.loads(response.read())
except HTTPError as error:
    print(json.dumps(json.loads(error.read()), ensure_ascii=True))
    raise SystemExit(1) from error
citations = result.get("citations", [])
files = {item.get("file_name") for item in citations}
report = {
    "run_at": datetime.now(UTC).isoformat(),
    "status": result.get("status"),
    "source_count": len(files),
    "citation_count": len(citations),
    "all_citations_have_page": bool(citations) and all(item.get("page_number") for item in citations),
    "answer_chars": len(result.get("answer", "")),
    "semantic_truth": "NOT VERIFIED",
}
folder = Path(__file__).resolve().parents[1] / "design-work/qa/private"
folder.mkdir(parents=True, exist_ok=True)
path = folder / f"multi-local-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.json"
path.write_text(json.dumps({"measurement": report, "response": result},
                           ensure_ascii=False, indent=2), encoding="utf-8")
report["private_report"] = path.name
print(json.dumps(report))
assert report["status"] == "completed", report
assert files == {"Ngan-hang_20260330.pdf", "DubaoKQKD_Nganhdien_20260408.pdf"}, report
assert report["all_citations_have_page"], report
