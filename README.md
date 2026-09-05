# DriveAgent

DriveAgent là trợ lý Google Drive chạy local, dùng Gemini để lập kế hoạch và trả lời. Mọi thao tác với Drive, RAG và memory đều đi qua Tool Registry có validate, xác thực, phân quyền, rate limit, audit và cơ chế retry có chọn lọc.

## Có gì trong project

- Liệt kê và tìm kiếm Google Drive theo tên hoặc nội dung.
- Đọc Google Docs, Sheets, Slides, PDF, DOCX, XLSX, PPTX, CSV, Markdown, HTML và text.
- Lập chỉ mục RAG bền vững, tách riêng theo user và file.
- Hybrid retrieval: Gemini dense embedding + lexical score + Reciprocal Rank Fusion.
- Trả lời có citation dẫn tới tệp Drive gốc.
- Bộ nhớ dài hạn có loại, dedup, semantic search, archive và delete.
- LangGraph orchestration: planning, state, conditional routing, tool execution, checkpoint và recovery.
- RBAC tách biệt với Google OAuth scopes.
- Audit log có request ID, latency, status và redaction secret.
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

Sau đó:

1. Điền `DRIVE_AGENT_GEMINI_API_KEY` trong `.env`.
2. Tạo OAuth client và lưu file thành `client_secret.json`. Xem [docs/SETUP_GOOGLE.md](docs/SETUP_GOOGLE.md).
3. Chạy:

```powershell
.\scripts\run-dev.ps1
```

Mở [http://localhost:5173](http://localhost:5173). API docs ở [http://localhost:8000/docs](http://localhost:8000/docs).

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
  agent/       LangGraph orchestration
  api/         REST API và session auth
  auth/        Google OAuth2, RBAC
  core/        Settings, encryption, redaction
  db/          SQLite models và session
  services/    RAG, embedding, memory, vector store
  tools/       Tool Registry và Drive tools
frontend/src/
  components/  App shell và shared states
  pages/       Chat, Drive, Memory, Audit, Access, Settings
design-work/   Design brief và bằng chứng QA
docs/          Hướng dẫn cho người mới
scripts/       Setup, run và verify trên Windows
```

## Quyền và dữ liệu

- Scope mặc định là `drive.readonly`. Project không tạo, sửa, xóa, di chuyển hoặc chia sẻ tệp.
- Người đăng nhập đầu tiên là `super_admin`; người tiếp theo là `editor`.
- Dữ liệu riêng luôn có `user_id`. Query RAG, memory, chat và audit đều filter theo user.
- OAuth credentials được mã hóa bằng `DRIVE_AGENT_APP_SECRET` trước khi ghi SQLite.
- Không commit `.env`, OAuth JSON, database hoặc Qdrant data.

## Kiểm thử

```powershell
.\scripts\verify.ps1
```

Kiểm thử live Google Drive cần API key và OAuth client của chính bạn. Unit/integration tests mặc định không gọi dịch vụ ngoài.

## Tài liệu

- [Thiết lập Google và Gemini](docs/SETUP_GOOGLE.md)
- [Kiến trúc](docs/ARCHITECTURE.md)
- [Tool Registry sáu cổng](docs/TOOL_REGISTRY.md)
- [RAG và Memory](docs/RAG_AND_MEMORY.md)
- [Hướng dẫn đọc code](docs/CODE_TOUR.md)
- [Bảo mật](docs/SECURITY.md)
- [Dependency và giấy phép](docs/THIRD_PARTY_LICENSES.md)
