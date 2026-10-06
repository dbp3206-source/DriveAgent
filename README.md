# Veridra

**Veridra — Trợ lý chuẩn bị tư vấn khách hàng doanh nghiệp.**

Đối tượng chính là chuyên viên tư vấn giải pháp AI/phần mềm trước bán hàng. Sản phẩm đang được chuẩn hóa theo ba quy trình: đọc yêu cầu khách hàng, chuẩn bị báo cáo trước cuộc hẹn, phản hồi và lưu kết quả sau khi duyệt. Gmail, Drive/tài liệu riêng, thông tin doanh nghiệp và Calendar là nguồn; Gemini hỗ trợ phân tích và tổng hợp. Mọi công cụ đi qua kiểm tra đầu vào, xác thực, phân quyền, hạn mức và nhật ký.

Định vị và phương pháp đã chốt tại [nền tảng sản phẩm](docs/PRODUCT-FOUNDATION.md); các hành vi chưa được triển khai/kiểm chứng không được coi là đã hoàn thiện chỉ vì có trong tài liệu. Đợt demo hiện tại dùng [bốn nhóm nghiệm thu A, B, E, F](docs/RELEASE-CLOSURE.md). [Bộ kiểm đầy đủ trước đó](docs/ACCEPTANCE-CHECKLIST.md) được giữ để tham chiếu lịch sử.

**Trạng thái phát hành: chưa nghiệm thu toàn bộ.** Đã có URL thử nghiệm
[Veridra trên Render](https://veridra-closed-beta.onrender.com), nhưng chưa đủ bằng chứng
cho toàn bộ nghiệp vụ, bốn người dùng thật và cùng bản phát hành. Kết quả kiểm thử mẫu
không thay thế nghiệm thu thực tế. Theo dõi bằng chứng ở checklist và `design-work/qa/`,
không đưa danh sách công việc nội bộ lên giao diện hoặc dùng điểm trung bình mẫu làm nhãn sẵn sàng.

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
- Google ADK coordinator với bảy vai trò Email, Web Research, Company Info, Calendar,
  Report Generation, Memory và Human Approval; Skill Agent được thêm khi chọn Skill.
  Các lượt deterministic có thể đi qua compiler thay vì gọi mọi Agent; việc có cấu trúc
  Agent không chứng minh tất cả workflow đã đạt nghiệm thu live.
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

Yêu cầu: Python 3.11 hoặc 3.12 bản chính thức từ python.org, Node.js 22.12 trở lên (hoặc 20.19 trở lên). Script cài dùng `backend/uv.lock` và `frontend/package-lock.json`, cùng bộ phiên bản đã kiểm trên GitHub.

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

- [Kịch bản trình bày 10 phút và phương án khi dịch vụ lỗi](docs/DEMO-10-PHUT.md)
- [Bộ mẫu giả lập và đáp án đối chiếu](docs/demo/README.md)
- [Thiết lập Google và Gemini](docs/SETUP_GOOGLE.md)
- [Triển khai closed beta Render + Supabase](docs/DEPLOY_CLOSED_BETA.md)
- [Kiến trúc](docs/ARCHITECTURE.md)
- [Tool Registry sáu cổng](docs/TOOL_REGISTRY.md)
- [RAG và Memory](docs/RAG_AND_MEMORY.md)
- [Hướng dẫn đọc code](docs/CODE_TOUR.md)
- [Bảo mật](docs/SECURITY.md)
- [Dependency và giấy phép](docs/THIRD_PARTY_LICENSES.md)
- [Evaluation Harness](backend/evals/README.md)
- [Biên bản nghiệm thu và giới hạn còn lại](docs/RELEASE-CLOSURE.md)
