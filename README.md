# Veridra

Veridra là trợ lý học tập và công việc chạy local, dùng Gemini để biến Drive, Gmail và tài liệu riêng thành câu trả lời có nguồn, Google Docs/Sheets có thể duyệt và các quy trình dùng lại được. Mọi tool đều đi qua Tool Registry có schema, xác thực, phân quyền, giới hạn, audit và retry có chọn lọc.

**Trạng thái phát hành: HOLD.** Bản local đang được hoàn thiện; chưa có URL closed beta
đã kiểm chứng. Kết quả unit/regression không chứng nhận toàn bộ chất lượng câu trả lời,
OAuth/BYOK cloud hay khả năng phục vụ nhiều người dùng thật. Theo dõi gate tại Nhật ký
và các báo cáo trong `design-work/qa/`; không dùng điểm trung bình suite làm nhãn ready.

Chạy local không cần Docker. Stack quan sát nặng là tùy chọn; xem
[phạm vi tài nguyên](docs/RESOURCE-PROFILE.md). PDF có lớp text tối đa 25 MiB được xử lý nền
và theo dõi theo trang; OCR đã bị loại khỏi phạm vi vì chất lượng không đủ. Xem
[PDF ingestion](docs/PDF-INGESTION.md) và [ranh giới BYOK](docs/BYOK-BOUNDARIES.md).

Bộ model mặc định: `gemini-3.5-flash-lite` cho chat/planning, fallback cấu hình riêng;
`gemini-embedding-2` với vector 768 chiều cho RAG/Memory.

## Có gì trong project

- Liệt kê và tìm kiếm Google Drive theo tên hoặc nội dung.
- Đọc Google Docs, Sheets, Slides, PDF, DOCX, XLSX, PPTX, CSV, Markdown, HTML và text.
- Lập chỉ mục RAG bền vững, tách riêng theo user và file.
- Hybrid retrieval: Gemini dense embedding + lexical score + Reciprocal Rank Fusion.
- Trả lời có citation dẫn tới tệp Drive gốc.
- Bộ nhớ dài hạn có loại, dedup, semantic search, archive và delete.
- Google Docs/Sheets theo hai pha: chuẩn bị bản xem trước, người dùng duyệt rồi mới tạo hoặc sửa.
- Reusable Skills lưu goal, procedure, constraint và output theo phiên bản; mỗi lần chạy dùng input/context mới.
- Gmail tìm, phân trang, đọc chuỗi và tệp đính kèm, tóm tắt, trả lời đúng thread, CC/BCC, soạn trước và chỉ gửi sau khi người dùng duyệt đúng nội dung.
- Google ADK coordinator với bốn Agent chuyên trách; LangGraph và compiler vẫn là backend so sánh.
- MCP và A2A read-only dùng SDK thật, cùng ranh giới Tool Registry/RBAC/audit.
- Harness dashboard thể hiện Context, RAG, Tool, Orchestration, Multi-Agent/MCP/A2A và Evaluation bằng số liệu thật.
- RBAC tách biệt với Google OAuth scopes.
- Audit log có request ID, latency, status và redaction secret, kể cả lần gọi tool bị từ chối.
- React + Fluent UI, responsive, light/dark, tiếng Việt.

## Chạy nhanh trên Windows

Để dùng thật local với UI đã build và một cổng duy nhất, làm theo
[hướng dẫn từng bước](docs/START_LOCAL.md), rồi chạy `scripts/run-local.ps1`.
Các lệnh run-dev bên dưới dành cho phát triển giao diện; dùng origin 5173 trong `.env`
nếu chọn chế độ dev thay cho runner local.

Yêu cầu: Python 3.11 hoặc 3.12 bản chính thức từ python.org, Node.js 20 trở lên.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
```

Sau đó chạy bản local một tiến trình:

1. Điền `DRIVE_AGENT_GEMINI_API_KEY` trong `.env`.
2. Tạo OAuth client và lưu file thành `client_secret.json`. Xem [docs/SETUP_GOOGLE.md](docs/SETUP_GOOGLE.md).
3. Chạy:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-local.ps1
```

Mở [http://localhost:8000](http://localhost:8000). API docs ở
[http://localhost:8000/docs](http://localhost:8000/docs). Chỉ dùng `run-dev.ps1`
khi đang phát triển frontend và đã đổi origin sang cổng 5173.

## Chạy bằng lệnh thủ công

Terminal 1:

```powershell
.\backend\.venv\Scripts\Activate.ps1
Set-Location backend
uvicorn app.main:app --reload --port 8000
```

Terminal 2:

```powershell
Set-Location frontend
npm run dev
```

## Cấu trúc

```text
backend/app/
  agent/       ADK multi-agent, LangGraph và deterministic compiler
  api/         REST API và session auth
  auth/        Google OAuth2, RBAC
  core/        Settings, encryption, redaction
  db/          SQLAlchemy models, migration ledger và session SQLite/PostgreSQL
  services/    RAG, memory, Workspace creators và skill store
  tools/       Tool Registry và toàn bộ governed capabilities
frontend/src/
  components/  App shell và shared states
  pages/       Chat, Drive, Gmail, Docs/Sheets approval, Skills, Memory, Harness, Audit
design-work/   Design brief và bằng chứng QA
docs/          Hướng dẫn cho người mới
scripts/       Setup, run và verify trên Windows
```

## Quyền và dữ liệu

- `drive.readonly` dùng để tìm/đọc; `drive.file` chỉ cho file app tạo hoặc người dùng chọn. App không xóa, di chuyển hay đổi chia sẻ.
- Gmail gửi và Docs/Sheets ghi đều có human-in-the-loop hai pha; Agent không tự bấm duyệt.
- Ở chế độ local, người đăng nhập đầu tiên là `super_admin`; ở closed beta,
  `DRIVE_AGENT_BETA_OWNER_EMAIL` mới là `super_admin` bất kể thứ tự đăng nhập,
  các email được mời khác là `editor`.
- Dữ liệu riêng luôn có `user_id`. Query RAG, memory, chat và audit đều filter theo user.
- OAuth credentials được mã hóa bằng `DRIVE_AGENT_APP_SECRET` trước khi ghi database.
- Không commit `.env`, OAuth JSON, database hoặc Qdrant data.

## Kiểm thử

```powershell
.\scripts\verify.ps1
```

Kiểm thử live Google Drive cần API key và OAuth client của chính bạn. Unit/integration tests mặc định không gọi dịch vụ ngoài.

## Tài liệu

- [Thiết lập Google và Gemini](docs/SETUP_GOOGLE.md)
- [Triển khai closed beta Render + Supabase](docs/DEPLOY_CLOSED_BETA.md)
- [Kiến trúc](docs/ARCHITECTURE.md)
- [Tool Registry sáu cổng](docs/TOOL_REGISTRY.md)
- [RAG và Memory](docs/RAG_AND_MEMORY.md)
- [Hướng dẫn đọc code](docs/CODE_TOUR.md)
- [Bảo mật](docs/SECURITY.md)
- [Dependency và giấy phép](docs/THIRD_PARTY_LICENSES.md)
- [Evaluation Harness](backend/evals/README.md)
- [QA report mới nhất](design-work/qa/qa-report.md)
