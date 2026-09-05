# QA Report

## Tóm tắt

DriveAgent đã được triển khai thành ứng dụng local hoàn chỉnh với FastAPI, React/TypeScript,
Google OAuth2, Tool Registry, RAG, Memory và LangGraph. Bản production build được mở trong
trình duyệt thật, kiểm tra ở desktop 1280x720 và mobile 390x844, cả light/dark mode.

## Input và nguồn sự thật

- Yêu cầu và slide Tool Harness, OAuth2, RBAC, audit, MCP, Orchestration Harness, LangGraph.
- `RAG.pdf`, `Memories.pdf`, `ingestion-qdrant.ipynb`, `search-qdrant.ipynb` do người dùng cung cấp.
- `Assignment-1-TODO`, `demo-tool-registry`, `rag-demo` trong workspace cha.
- Notebook ReAct Gemini/LangGraph: `https://github.com/philschmid/gemini-samples/blob/main/guides/langgraph-react-agent.ipynb`.

Không sao chép tài sản nguồn vào repo. Chi tiết ánh xạ kiến thức nằm ở
`design-work/source-notes/README.md`.

## Route thiết kế

- Skill: `design-taste-frontend` tại
  `C:/Users/Bao Phuc/.agents/skills/design-taste-frontend/SKILL.md`.
- Design system duy nhất: Fluent UI React v9, phù hợp dashboard dày dữ liệu.
- Visual direction: calm technical workspace, cobalt accent, ít card, không gradient/glow
  hoặc bố cục SaaS đại trà.
- Design dials: variance 4/10, motion 3/10, density 6/10.
- Không dùng ImageGen vì ứng dụng không cần ảnh trang trí để truyền đạt thông tin.

## Kiểm tra cấu trúc và runtime

| Kiểm tra | Kết quả |
|---|---|
| Ruff | Pass, không có lỗi |
| Pytest | Pass, 18/18 test |
| Coverage đo tham khảo | 55% toàn app; core RAG 86%, Memory 95%, Registry 85%, Drive 75% |
| ESLint | Pass, không có lỗi |
| TypeScript + Vite production build | Pass, 2.140 module transformed |
| FastAPI health | HTTP 200, SQLite true, Qdrant `qdrant-embedded` |
| Drive list/search/read | Pass bằng Google API mock, gồm query escape và tải nội dung |
| RAG | Pass ingestion idempotent, hybrid retrieval và user isolation |
| Memory | Pass dedup, secret rejection, Qdrant user filter và SQLite fallback |
| Tool Registry | Pass permission, audit, retry transient và rollback phần ghi dở |

`scripts/verify.ps1` là entry point lặp lại Ruff, Pytest coverage, ESLint và build.
CI GitHub Actions chạy cùng nhóm kiểm tra trên Python 3.12 và Node 22.

## QA trình duyệt thật

Chrome DevTools MCP được dùng trên build do FastAPI phục vụ tại `http://127.0.0.1:8000`.

- Lighthouse desktop: Accessibility 100, Best Practices 100, SEO 100,
  Agentic Browsing 100; 47 pass, 0 fail.
- Lighthouse mobile: cùng bốn điểm 100; 47 pass, 0 fail.
- Console sau navigation cuối: không có message.
- Network sau navigation cuối: 10/10 request trả HTTP 200, gồm document, JS/CSS chunks,
  `/api/auth/status`, `/api/health` và `/api/chat/sessions`.
- Desktop không overflow ngang.
- Mobile 390px: document và chat đều có `scrollWidth == clientWidth` sau sửa.
- Keyboard: textarea nhận focus bằng Tab, `:focus-visible` true, outline đo được 2.4px.
- Menu mobile mở được, điều hướng được và tự đóng sau khi chọn trang.
- Loading, empty, missing-permission, disabled và success state đã quan sát trực tiếp.

Lighthouse JSON/HTML nằm trong `design-work/qa/validation/`.

## Findings đã sửa

1. React effect từng trả về kết quả `scrollIntoView`, gây lỗi cleanup trong StrictMode.
   Effect đã đổi sang block body hợp lệ.
2. Trang Drive từng hiện đồng thời error và empty state; điều kiện render đã tách đúng.
3. Demo user từng bị ghi nhãn Drive đã kết nối; header nay dựa trên OAuth scope thật.
4. Chat mobile từng bị min-content grid làm cắt nội dung. Đã khóa cột
   `minmax(0, 1fr)` và đo lại không overflow.
5. Form field thiếu `id/name`; đã bổ sung và console issue về form field biến mất.
6. Heading chat từng nhảy từ h1 sang h3; EmptyState đổi sang h2 và Lighthouse từ 98 lên 100.
7. OAuth token exchange đồng bộ từng có thể chặn event loop; đã chuyển sang worker thread.
8. Memory update/delete nay đồng bộ Qdrant và từ chối secret có dạng giá trị, nhưng không
   chặn nhầm câu hướng dẫn an toàn.
9. LangGraph nay chỉ đưa message mới vào checkpointer, tránh nhân đôi lịch sử ở lượt sau.
10. OAuth JSON, SQLite và Qdrant path tương đối nay luôn tính từ root repo; smoke test xác
    nhận data tạo ở `data/qa-final`, không lệch vào `backend/data`.

## Content fidelity và bảo mật

- Tất cả tool đi qua sáu cổng: schema, auth, RBAC + scope, rate limit, audit, execute/retry.
- Chỉ lỗi tạm thời được retry; 400/401/403/404 không retry.
- Dữ liệu riêng có `user_id`; server không nhận user ID tùy ý từ frontend.
- OAuth credential mã hóa bằng Fernet dẫn xuất từ APP_SECRET.
- Audit redaction che secret theo key; Memory từ chối nội dung giống secret có giá trị.
- Scope mặc định `drive.readonly`; không có tool ghi/xóa Drive.
- Dependency chính dùng license MIT, Apache-2.0 hoặc BSD-3-Clause. Xem
  `docs/THIRD_PARTY_LICENSES.md`. Repo chưa có project license và được ghi rõ.

## Ảnh QA

- `screenshots/setup-desktop.png` (1280x720)
- `screenshots/chat-desktop-dark.png` (1280x720)
- `screenshots/chat-mobile-dark.png` (390x844)
- `screenshots/memory-desktop-light.png` (1280x720)
- `screenshots/drive-permission-state.png` (1280x720)

## Quality gate

| Tiêu chí | Điểm |
|---|---:|
| Content fidelity và đúng sự thật | 19/20 |
| Visual specificity | 18/20 |
| Cấu trúc và information architecture | 14/15 |
| Typography và readability | 14/15 |
| Composition, spacing, hierarchy | 14/15 |
| Technical finish và verification | 13/15 |
| **Tổng** | **92/100** |

Không có automatic fail: build mở được trong target environment, ảnh cuối được render,
không có lỗi console/network/overflow, source vẫn editable và không bịa dữ liệu.

## Giới hạn còn lại

- Chưa thể xác minh end-to-end với Drive thật hoặc Gemini thật khi chưa có API key và
  OAuth client của người dùng. Setup gate hiển thị đúng điều này; unit/integration tests
  không giả vờ là live verification.
- Export Google Sheets dạng CSV theo bản Google xuất mặc định; workbook nhiều sheet cần
  mở rộng nếu sau này có yêu cầu đọc từng sheet.
- Drive write operations và code sandbox không triển khai vì là phần tùy chọn/rủi ro cao,
  đúng quyết định phạm vi của người dùng.
