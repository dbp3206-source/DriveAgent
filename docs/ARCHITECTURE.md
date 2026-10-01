# Kiến trúc Veridra

## Request lifecycle

```text
React UI
  -> FastAPI session auth
  -> Google ADK coordinator
       -> Research / Communication / Study / Workspace specialist
  -> Tool Registry
       1. Resolve registered tool
       2. Audit STARTED + redact arguments
       3. Validate schema + authentication
       4. RBAC + OAuth scopes
       5. Per-user rate limit
       6. Execute + selective retry
  -> Google Drive / Docs / Sheets / Gmail / RAG / Memory / Skills
  -> Citation + execution trace
  -> React UI
```

## Lưu trữ

- Local: SQLite giữ dữ liệu ứng dụng và state phụ; Qdrant embedded tăng tốc vector search.
  SQLite vẫn giữ embedding để cosine fallback hoạt động khi Qdrant không sẵn sàng.
- Closed beta cloud: một Supabase PostgreSQL project giữ dữ liệu ứng dụng, Skill, quota,
  circuit, approval ledger, evaluation queue/checkpoint và ADK session trong schema riêng.
  PDF gốc nằm trong bucket Supabase Storage private, owner được kiểm tra ở backend.
- Cloud không phụ thuộc Qdrant/Redis/Kafka. Embedding JSON bền trong PostgreSQL được truy
  hồi bằng SQL + cosine/RRF ở dịch vụ. Đây không phải pgvector và được giới hạn cho tối đa
  bốn user; hiệu năng phải được đo trên Render Free trước khi phát hành.
- LangGraph SQLite checkpointer chỉ là backend so sánh local. Profile cloud bắt buộc ADK.

## Multi-user

Chạy local không đồng nghĩa với thiết kế single-user. Các bảng dữ liệu riêng có `user_id`; mọi query đều filter server-side. Frontend không được quyền truyền `user_id` để tránh đọc dữ liệu của người khác.

Cloud có allowlist tối đa bốn email. Owner được cấu hình rõ ràng, không suy từ thứ tự đăng
nhập. Google OAuth và Gemini BYOK là riêng theo user; credentials được mã hóa trước khi lưu.

## Orchestration Harness

- Planning/routing: ADK coordinator hiểu ý định và chuyển cho đúng specialist.
- State: message, user/session/request ID, tool trace và ADK session tách theo user.
- Execution: mọi specialist chỉ nhìn thấy tool phù hợp; Tool Registry vẫn là cổng bắt buộc.
- Recovery: registry chỉ retry lỗi tạm thời; model/tool loop có giới hạn. Runtime
  chọn model dự phòng khác model chính từ danh sách free-tier được phê duyệt;
  failover sang key khác chỉ áp dụng với key của cùng user đã bật lựa chọn này.
- Checkpoint: định danh session luôn ghép với user; history cũ vẫn đọc được trong UI.
- Protocols: MCP và A2A chỉ công bố tool read-only, dùng SDK thật và cùng RBAC/audit.

## Vòng đời Gemini key và request đang chạy

- Mỗi user có một runtime theo credential hiệu lực; key lưu mã hóa phía server,
  không trả lại frontend sau khi lưu. Settings phân biệt key người dùng đã chọn
  và key thực sự đang phục vụ khi failover.
- Chat pin vòng đời inference **trước khi resolve runtime**, theo `user_id`.
  Khi đổi key, cache của user đó bị vô hiệu hóa, nhưng runtime cũ được đưa
  vào hàng chờ đóng cho đến khi các request đã pin của **user đó** hoàn tất.
  Request dài của user khác không cản trở dọn runtime này. Lượt chat mới
  resolve credential mới; lượt đang chạy không bị đóng client giữa chừng.
- Ledger quota trong UI là số request được ghi nhận ở máy theo key/tuyến hiệu lực,
  không phải số dư chính thức từ Google. Trạng thái 429 và thời điểm reset từ
  Google vẫn phải được phân loại riêng; không thể suy diễn số dư thực từ local ledger.

## Creation & Execution Harness

- Một structured compiler call có thể trả tối đa bốn proposal trong cùng bundle.
- Docs và Sheets dùng ledger `prepare -> digest approval -> claim -> execute -> read-back`.
- Docs và Sheets edit chỉ patch vùng/đoạn được chọn; bản cũ không khớp thì fail với conflict.
- Gmail reply giữ thread metadata; recipient, CC/BCC, subject, body và attachment đều nằm trong digest được duyệt.
- Skills lưu procedure có placeholder; `skill_run` chỉ nạp procedure với context mới, không chạy code.

Slides và Visual Studio là mã lịch sử, không còn route, navigation hoặc tool được đăng ký. Lịch sử chat cũ vẫn đọc được nhưng không thể tạo side effect mới.

## Vì sao không có Code Sandbox

Project tập trung vào Google Drive và dữ liệu người dùng. Thực thi code do model sinh ra làm tăng đáng kể bề mặt tấn công nhưng không tạo đủ giá trị cho các use case bắt buộc, nên được loại khỏi phạm vi theo quyết định của người dùng.
