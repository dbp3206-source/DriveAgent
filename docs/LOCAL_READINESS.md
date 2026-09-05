# Local readiness — 2026-09-05

Phạm vi người dùng chọn: dùng thật local cho bản thân/nhóm nhỏ trước.

Đã chuẩn bị:

- `.env` local sinh APP_SECRET bằng Python secrets, không in giá trị, không commit.
- Runner loopback một tiến trình, build frontend, không reload, UI/API cùng cổng 8000.
- Kiểm tra trước khi chạy: key hiện diện, secret, demo off, callback/origin, OAuth Web JSON.
- Sửa đường dẫn frontend build và nạp `.env` theo repo root, hỗ trợ BOM và comma scopes.
- Setup dừng đúng khi lệnh cài dependency thất bại; không thay `.env` hiện hữu.

Kiểm chứng đã thực hiện:

- `python -m pytest backend/tests -q`: 20 passed.
- `python -m ruff check backend scripts/local_config.py`: passed.
- `npm.cmd run build --prefix frontend`: passed.
- PowerShell parser cho run-local.ps1: không có lỗi.
- FastAPI TestClient với DB/Qdrant tạm: GET / trả HTML 200, auth/status 200.
- Runner thực tế dừng trước startup với trạng thái MISSING khi thiếu credentials.
- `git check-ignore .env client_secret.json`: cả hai được ignore.
- `git diff --check`: passed.

Chưa kiểm chứng: đăng nhập OAuth thật, gọi Gemini thật, đọc Drive thật và
end-to-end RAG với dữ liệu Google. Chưa có API key và OAuth JSON trên máy tại thời điểm kiểm tra.
Không có thay đổi visual; smoke HTTP không thay thế kiểm chứng browser hoặc live OAuth.

Người dùng thực hiện docs/START_LOCAL.md bước 2–5, sau đó chạy bước 6–7.
