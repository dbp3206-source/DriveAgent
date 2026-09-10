# QA Report — DriveAgent local release candidate

Ngày kiểm tra: 2026-09-10 · Phạm vi: dùng thật trên máy local cho cá nhân/nhóm nhỏ.

## Kết luận

Release candidate đã qua toàn bộ automated gate và một vòng nghiệm thu thật bằng
tài khoản Google đã kết nối. Không có lỗi blocking được quan sát trong luồng chính.
Không dùng câu “không thể còn bug” như một cam kết tuyệt đối; bằng chứng và các ranh
giới chưa kiểm tra bằng thao tác ngoài được ghi rõ bên dưới.

## Nguồn yêu cầu và route thiết kế

- Các slide OAuth, Authorization/RBAC, Tool Harness, RAG, Memory, Orchestration,
  LangGraph và Evaluation Harness do người dùng cung cấp.
- `C:/Users/Bao Phuc/Downloads/Evaluation-Harness.pdf` là nguồn chính cho taxonomy eval.
- UI hiện tại dùng design system nội bộ React/Fluent và tham khảo interaction từ
  `https://ui.shopviet247.xyz/elements`; không sao chép component source.
- Không dùng Hallmark trong vòng thiết kế này theo yêu cầu người dùng.
- Source note/attribution: `design-work/source-notes/ui-shopviet247-elements.md`.

## Automated quality gates

| Gate | Kết quả |
|---|---|
| Backend pytest | **182 passed**, 13 cảnh báo deprecation từ dependency |
| `scripts/verify.ps1` | Pass toàn bộ Ruff + 182 tests + coverage + lint + build |
| Statement coverage | 67% toàn backend; core RAG 91%, Memory 96%, Registry 89%, compiler 85% |
| Targeted ADK/atomicity/eval/harness/security | **17 passed** |
| Ruff | Pass |
| Frontend ESLint | Pass |
| TypeScript + Vite production build | Pass, 2,404 modules |
| `pip check` | Không có dependency hỏng |
| `pip-audit` | Không có vulnerability đã biết |
| `npm audit --omit=dev` | 0 vulnerability trên production dependencies |
| Local config | 10/10 mục `OK`, không in secret |
| Routing golden set | **12/12** |
| `git diff --check` | Pass |

Các warning còn lại là API deprecation trong Google ADK/A2A/Starlette dependency,
không phải test failure. Chúng cần được theo dõi khi nâng phiên bản package.

## Nghiệm thu trình duyệt và dịch vụ thật

Build production được phục vụ loopback và thao tác bằng browser automation:

| Luồng | Bằng chứng |
|---|---|
| Auth/session | User thật hiển thị đúng role `super_admin`; Drive và Gmail connected |
| Drive list | Tải danh sách thật thành công |
| Drive search | `DriveAgent QA` trả đúng hai tệp QA |
| Drive read | Sheet trả `Mục,Số tiền / Sách,120 / Xe buýt,30`; Doc trả mã QA và lịch ôn |
| RAG ingest | `DriveAgent QA kế hoạch 2` index thành công 1 chunk |
| RAG answer | Trả đúng `DA-CREATE-2026`, `thứ Sáu` và citation mở đúng Google Doc |
| Slides create | Tạo thật `DriveAgent QA Slides 2026-09-10`, 2 slide; kiểm tra lại title, bullet và speaker notes |
| Slides edit | Phát hiện false-negative khi text mới chứa text cũ, thêm regression test, tạo operation mới và sửa/hoàn nguyên thành công với revision lock + read-back |
| Docs/Sheets edit | Sửa và hoàn nguyên dữ liệu QA thật qua preview → approve → read-back; Sheets đọc số bằng `UNFORMATTED_VALUE` |
| ADK multi-agent | Live trace có coordinator → specialist handoff → governed tool → synthesis |
| Calculator | Live tool trả 150.0 từ 125.5 + 24.5 |
| Memory | Tải 2 mục, semantic search còn 1 mục, donut/line chart chuyển được |
| Human feedback | Nút “Hữu ích” ghi backend thành công; Harness cập nhật 1 lượt, 100% helpful |
| Harness | 7 mục Context/RAG/Tool/Orchestration/Creation/Multi-Agent+MCP+A2A/Evaluation dùng dữ liệu thật |
| Audit | Tải 100 event, chart/trend, filter và thao tác export JSON hoạt động |
| Local sources | Tải danh sách, hiển thị giới hạn/nhận diện tính năng đúng sự thật |
| Artifacts | Tải workbench và bản lưu có version |
| RBAC | Quyền app và 7 OAuth scopes hiển thị tách biệt |
| Settings | Hiển thị model, embedding, OAuth và vector backend thực tế |
| Responsive/a11y | 12/12 màn hình qua desktop/intermediate và mobile 390×844, không overflow/console error; light/dark và skip-link bàn phím đạt |
| Security headers | CSP, XFO DENY, nosniff, referrer, COOP và Permissions-Policy có trên response |
| Favicon/assets | `/favicon.svg` HTTP 200; không còn favicon 404 ở build mới |

Lần đầu mở Memory sau khi build lại ngay trong lúc server đang chạy trả lazy-chunk 404
vì tab cũ giữ hash của bundle trước. Reload lấy manifest mới và trang hoạt động bình
thường. Quy trình `run-local.ps1` build trước rồi mới serve, nên không tạo race này.

## Coverage theo Harness

- **Context Harness:** session server-side, user-scoped history, long-term memory,
  ADK session state và atomic rollback khi model failure.
- **Tool Harness:** 28 tool definitions; schema, auth, RBAC/OAuth, rate limit,
  timeout, selective retry, audit/redaction và approval policy.
- **RAG Harness:** Drive/local ingestion, revision freshness, hybrid dense + lexical
  + RRF, Gemini Embedding 2 (768D), citation và user isolation.
- **Orchestration Harness:** ADK coordinator + 4 specialist agents, handoff trace,
  planning/routing/execution/synthesis/recovery; LangGraph/compiler giữ làm backend so sánh.
- **MCP/A2A:** SDK thật, discovery/call read-only, cùng Tool Registry và user context;
  test protocol xác nhận auth và không bypass policy.
- **Evaluation Harness:** routing golden set, audit success/latency, human feedback,
  RAG/citation tests và live task evidence. Dashboard không đánh đồng routing với accuracy.

## Bảo mật và dữ liệu

- Credential OAuth mã hóa bằng Fernet dẫn xuất từ `APP_SECRET`; cookie HttpOnly/SameSite.
- Dữ liệu riêng đều gắn `user_id`; API không tin `user_id` từ frontend.
- Docs/Slides/Sheets/Gmail dùng prepare → digest → explicit approve → execute → read-back.
- Không log secret; Memory từ chối chuỗi giống token/key; audit redaction có test.
- Runner chỉ bind `127.0.0.1`, demo login tắt, HTTP OAuth chỉ bật trong loopback process.
- `.env`, OAuth JSON, SQLite/Qdrant và backup không được commit.

## UX và accessibility

- Hệ thống chữ Be Vietnam Pro, dark workspace, hierarchy theo tác vụ thay vì card SaaS.
- Sidebar có nhãn rõ cho nontechnical user; controls/input/composer dùng bán kính lớn,
  assistant answer phẳng như document thay vì từng bubble/card.
- Loading/empty/error/disabled/approval states đều có copy giải thích.
- Skip link, focus-visible, keyboard mobile menu và semantic headings đã có.
- Toàn bộ 12 màn hình đã được browser-verified lại sau thay đổi cuối ở mobile 390×844
  và viewport mặc định; không có horizontal overflow hoặc console error.
- Light/dark, skip-link, focus bàn phím, preview diff và trạng thái pending/running/
  uncertain/failed/succeeded đã được kiểm tra trực tiếp.

## Quality score

| Tiêu chí | Điểm |
|---|---:|
| Content fidelity và tính đúng đắn | 19/20 |
| Visual specificity cho sinh viên/nontech | 19/20 |
| Kiến trúc và information hierarchy | 15/15 |
| Typography, readability, accessibility | 15/15 |
| Composition và interaction consistency | 14/15 |
| Technical finish và verification | 14/15 |
| **Tổng** | **96/100 (9.6/10)** |

Điểm này là benchmark nội bộ có bằng chứng theo quality gate, không phải chứng nhận độc lập.

## Giới hạn còn lại không phải release blocker

1. Không tự động gửi Gmail trong QA vì người dùng đã hoãn phần sandbox/Gmail; unit/integration
   test đã cover attachments và 2-phase send, còn live send phải được user duyệt ở thời điểm gửi.
2. User B isolation được chứng minh bằng integration tests; vòng OAuth thủ công profile B
   không được tự động hóa thay người dùng.
3. Audit dashboard giữ trung thực lịch sử lỗi QA cũ nên tỷ lệ 100 lượt gần nhất hiện là 93%
   và citation integrity lịch sử là 83%; operation hiện tại đã có regression test và live pass.
4. Evaluation chưa tuyên bố semantic accuracy cho mọi tài liệu tương lai; chất lượng đó phải
   được duy trì bằng golden cases theo dữ liệu/use case mới và human feedback liên tục.
5. Đây là cấu hình production-like chạy loopback cho nhóm nhỏ, chưa phải public web service
   có managed database, centralized secrets, SLO/alerting và quy trình triển khai nhiều máy.

## Artifact và bằng chứng

- Editable source: `frontend/src/`, `backend/app/`, `backend/evals/`.
- Manifest: `design-work/qa/run-manifest.json`.
- Curated command summary: `design-work/qa/command-log.txt`.
- Historical rendered screenshots/Lighthouse: `design-work/qa/screenshots/` và
  `design-work/qa/validation/`; browser capture mới nhất nằm trong phiên QA hiện tại.
- Google Slides live artifact: `https://docs.google.com/presentation/d/1ff8ak-LoPVCAtbaGEWZRlucwVUZW2kRm58ueaW5sTfU/edit`.
