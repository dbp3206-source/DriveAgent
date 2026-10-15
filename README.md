# Veridra

**Veridra — Trợ lý AI cho công việc nội bộ doanh nghiệp.**

Giúp người thường xuyên xử lý tài liệu, thư và họp: hiểu tài liệu, nắm tình hình, phân tích phương án, chuẩn bị cuộc họp và hoàn thiện nội dung. Trợ lý cần đề xuất hướng làm và bước tiếp hữu ích khi tham vấn, không chỉ tóm tắt hoặc hỏi gì đáp nấy. Nguồn dùng theo quyền và yêu cầu; không tự thực hiện đề xuất. Bản đầu giới hạn tối đa bốn tài khoản được mời, dữ liệu riêng; chưa phải không gian cộng tác toàn doanh nghiệp.

Định hướng hiện hành ngày 13/10: [nền tảng sản phẩm](docs/PRODUCT-FOUNDATION.md), [hợp đồng trợ lý](docs/ASSISTANT-CONTRACT.md), [ba bộ giả lập và mười ca nghiệm thu](docs/verification/internal-assistant/README.md), [sổ triển khai](docs/PRODUCTION-EXECUTION-20261013.md). Cập nhật15/10: linh vật đã có bằng chứng triển khai; bản sửa tên tài liệu `ed3fa6a` đã qua CI/PostgreSQL, còn chờ triển khai và nghiệm thu URL. Đọc [bản ứng viên hiện tại](docs/RELEASE-CANDIDATE-ed3fa6a.md); **chưa đủ điều kiện ký Production**. Báo cáo bên dưới giữ nguyên phạm vi lịch sử, không tự chuyển thành đạt theo định hướng mới.

## Xem và kiểm chứng nhanh

- [Mở sản phẩm](https://veridra-closed-beta.onrender.com/) — bản thử giới hạn người được mời; không có tài khoản hoặc khóa API dùng chung. Dịch vụ miễn phí có thể cần thời gian khởi động sau khi ngủ.
- [Kịch bản demo 10 phút](docs/DEMO-10-PHUT.md) và [bộ dữ liệu giả lập, 10 ca kiểm, đáp án độc lập](docs/verification/golden/README.md).
- [Báo cáo chạy thật ngày 11/10/2026](docs/verification/DEMO-REPORT-20261011.md), không chỉ kiểm phần trò chuyện: có Drive, nhập tệp, bộ nhớ, quy trình, Gmail, lịch, kết quả đã lưu và nhật ký.
- [Các bộ kiểm chất lượng, bảo mật và kiểm soát hành động](docs/verification/README.md), kèm kết quả có ngày đo và phạm vi cụ thể.
- [Kiến trúc và lựa chọn kỹ thuật](docs/ARCHITECTURE.md), [hướng dẫn đọc mã](docs/CODE_TOUR.md), [mục lục tài liệu](docs/README.md).

**Kết quả cần đọc đúng phạm vi:** bộ kiểm chạy thật ngày 11/10 có 3 ca đạt,
6 ca đạt một phần và 1 ca chưa đạt. Kiểm nội bộ cùng ngày đạt 200/200 kiểm hồi quy
và 78/78 kiểm được chọn về bảo mật, phân quyền, duyệt và thực thi. Các kiểm nội bộ
không gọi mô hình hoặc Google, không thay thế nghiệm thu chạy thật và không phải
chứng nhận bảo mật hay sẵn sàng vận hành toàn diện. Bản báo cáo Word và ảnh gốc
có dữ liệu riêng được giữ nội bộ; kho công khai chỉ chứa dữ liệu giả lập và bản
tổng hợp đã loại định danh riêng.

Quy trình tiêu biểu: nhận việc cần hoàn thành → chọn đúng nguồn →
đối chiếu, phân tích hoặc soạn → kiểm kết quả → xem trước, duyệt
nếu cần tạo tài liệu → đọc lại và kiểm nhật ký. Giá trị hướng tới là giảm thao tác
tìm, ghép và kiểm lại thông tin; chưa công bố số giờ tiết kiệm thực tế khi chưa đo.

Định vị và phương pháp ở [nền tảng sản phẩm](docs/PRODUCT-FOUNDATION.md) không thay thế bằng chứng thực thi. [Bốn nhóm nghiệm thu A, B, E, F](docs/RELEASE-CLOSURE.md) và [bộ kiểm đầy đủ trước đó](docs/ACCEPTANCE-CHECKLIST.md) giữ để tham chiếu lịch sử; đợt triển khai hiện hành dùng mười ca T01–T10 trong bộ chuẩn mới.

**Trạng thái bàn giao: người dùng đã chấp nhận bản demo có giới hạn ngày 10/10/2026.**
Mở [Veridra trên Render](https://veridra-closed-beta.onrender.com).
Đợt cuối đã đóng lỗi mất liên kết nguồn và thống nhất tỷ lệ Nhật ký.
Bản f1c91ea đã qua kiểm GitHub, chạy đúng ảnh trên Render và được kiểm gộp
trong thanh bên ngày 10/10/2026. Đã kết thúc đợt sửa; biên nhận nằm tại
[biên bản nghiệm thu cuối](docs/FINAL-ACCEPTANCE-20261010.md).
[Biên bản bàn giao](docs/DEMO-HANDOFF-20261010.md) ghi phạm vi, bằng chứng,
giới hạn và cách quay lui; [kịch bản 10 phút](docs/DEMO-10-PHUT.md) chỉ dùng
các kết quả có biên nhận. Đây không phải chứng nhận toàn bộ sản phẩm sẵn sàng
vận hành: chưa có điểm tổng hợp hợp lệ của bộ nghiệm thu, chưa kiểm đủ bốn
người dùng và một số chuỗi nghiệp vụ. Giữ nguyên các kết quả chưa đủ bằng chứng,
không dùng kiểm mã hoặc trạng thái triển khai thành công để đổi chúng thành đạt.

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

Bắt đầu ở [hồ sơ kiểm chứng công khai](docs/verification/README.md). Hồ sơ phân biệt
kiểm hồi quy, kiểm bảo mật/kiểm soát hành động bằng dữ liệu thử và kết quả chạy
thật. Bộ dữ liệu chuẩn, đáp án và kết quả không yêu cầu công khai thư, khóa hoặc
tài khoản riêng. Những ca dùng nguồn Google thật cần quyền và chấp thuận riêng.

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
