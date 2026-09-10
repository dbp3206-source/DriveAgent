# Local readiness — 2026-09-06

Phạm vi người dùng chọn: dùng thật local cho bản thân/nhóm nhỏ trước.

Đã chuẩn bị:

- `.env` local sinh APP_SECRET bằng Python secrets, không in giá trị, không commit.
- Runner loopback một tiến trình, build frontend, không reload, UI/API cùng cổng 8000.
- Kiểm tra trước khi chạy: key hiện diện, secret, demo off, callback/origin, OAuth Web JSON.
- Sửa đường dẫn frontend build và nạp `.env` theo repo root, hỗ trợ BOM và comma scopes.
- Setup dừng đúng khi lệnh cài dependency thất bại; không thay `.env` hiện hữu.

Kiểm chứng đã thực hiện:

- `python -m pytest backend/tests -q`: 29 passed (gồm chat/RAG/Memory multi-user,
  Tool Registry, OAuth callback, encryption/redaction và loop guard của orchestrator).
- `python -m ruff check backend scripts/local_config.py`: passed.
- `npm run lint` và `npm run build`: passed.
- `pip check`: không có dependency hỏng.
- `pip-audit`: không có lỗ hổng đã biết sau khi nâng `cryptography` lên 50.0.1
  và `pytest` lên 9.1.1. Package nội bộ `drive-agent-backend` không có trên PyPI nên
  được auditor bỏ qua đúng dự kiến.
- `npm audit --omit=dev`: 0 vulnerability.
- PowerShell parser cho run-local.ps1: không có lỗi.
- Local config: toàn bộ key cấu hình trả `OK` mà không in secret.
- `/api/health`: SQLite, Qdrant embedded, Gemini và Google OAuth đều ready; endpoint
  trả đúng primary `gemini-3.5-flash-lite`, fallback `gemini-3.5-flash-lite`, embedding
  `gemini-embedding-2` 768 chiều.
- Gọi live trực tiếp cả primary và fallback: đều trả kết quả thành công.
- Google Drive live: liệt kê 50 tệp có phân trang; tìm và đọc notebook thành công.
- Notebook ingestion chỉ giữ Markdown/code source, bỏ output/base64; index 17 chunks,
  re-index không đổi được skip đúng; RAG trả lời State/Nodes/Edges kèm citation Drive.
- Memory live: save, semantic search, gọi qua Agent và persistence sau restart đều đạt.
- Audit UI hiển thị tool, user, status, latency và request ID của các flow live.
- Browser thật: dark/light, loading, mobile 390 px, intermediate 768 px, desktop,
  không horizontal overflow; focus ring 2.4 px; console không có warning/error.
- `git check-ignore .env client_secret.json`: cả hai được ignore.
- `git diff --check`: passed.

Tài khoản hiện tại đã đăng nhập OAuth thật và sử dụng được. Tệp hướng dẫn
`DriveAgent smoke test` chưa tồn tại trên Drive, nên nghiệm thu dùng notebook thật
`langgraph-react-agent.ipynb` thay thế. Cách ly user B được kiểm chứng bằng integration
test server-side; muốn nghiệm thu thủ công với hai tài khoản Google vẫn cần người dùng
đăng nhập profile thứ hai vì agent không được tự chấp thuận OAuth thay người dùng.
