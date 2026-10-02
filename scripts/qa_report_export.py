"""Exercise the application's real exporter with an explicitly fictional report."""
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.report_exports import export_report  # noqa: E402

content = (
    "## Dữ kiện đã xác nhận\n\nKhách hàng mẫu có **42 nhân viên**. Ngân sách chưa biết.\n\n"
    "| Hạng mục | Giá trị |\n| --- | --- |\n| Nhân viên | 42 |\n"
    "| Cuộc hẹn | 15 tháng 10 năm 2026 |\n| Ngân sách | Chưa xác nhận |\n\n"
    "## Việc cần làm\n\n- Xác nhận phạm vi trước khi đề xuất giải pháp.\n"
    "- Đối chiếu thông tin và không suy đoán ngân sách.\n\n"
    "## Nguồn\n\n[Nguồn mẫu](https://example.com/source) [1]\n"
)
folder = ROOT / "design-work/qa" / f"report-export-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}"
folder.mkdir(parents=True)
outputs = []
for extension in ("md", "docx", "pdf"):
    body, media_type = export_report("Chuẩn bị cuộc hẹn tư vấn mẫu", content, extension)
    path = folder / f"consultation.{extension}"
    path.write_bytes(body)
    outputs.append({"format": extension, "bytes": len(body), "media_type": media_type})
report = {"run_at": datetime.now(UTC).isoformat(), "fictional_input": True,
          "outputs": outputs, "visual_review": "NOT VERIFIED"}
(folder / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(folder)
