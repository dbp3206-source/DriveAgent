# Kiến trúc DriveAgent

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
  -> Google Drive / Docs / Slides / Sheets / Gmail / RAG / Memory / Visuals / Skills
  -> Citation + execution trace
  -> React UI
```

## Lưu trữ

- SQLite: users, encrypted credentials, chat sessions, messages, file index, chunks, memory, audit.
- Qdrant embedded: vector index trong `data/qdrant`. Không cần Docker.
- SQLite giữ bản sao embedding. Nếu Qdrant không khởi tạo được, cosine search vẫn chạy từ SQLite và health báo `sqlite-fallback`.
- ADK SQLite session service lưu trạng thái hội thoại. LangGraph SQLite checkpointer
  vẫn tồn tại khi chọn backend `langgraph` để so sánh/khôi phục dữ liệu cũ.

## Multi-user

Chạy local không đồng nghĩa với thiết kế single-user. Các bảng dữ liệu riêng có `user_id`; mọi query đều filter server-side. Frontend không được quyền truyền `user_id` để tránh đọc dữ liệu của người khác.

## Orchestration Harness

- Planning/routing: ADK coordinator hiểu ý định và chuyển cho đúng specialist.
- State: message, user/session/request ID, tool trace và ADK session tách theo user.
- Execution: mọi specialist chỉ nhìn thấy tool phù hợp; Tool Registry vẫn là cổng bắt buộc.
- Recovery: registry chỉ retry lỗi tạm thời; model/tool loop có giới hạn; fallback dùng
  cùng `gemini-3.5-flash-lite` để không tự chuyển sang model trả phí.
- Checkpoint: định danh session luôn ghép với user; history cũ vẫn đọc được trong UI.
- Protocols: MCP và A2A chỉ công bố tool read-only, dùng SDK thật và cùng RBAC/audit.

## Creation & Execution Harness

- Một structured compiler call có thể trả tối đa bốn proposal trong cùng bundle.
- Docs, Slides và Sheets dùng ledger `prepare -> digest approval -> claim -> execute -> read-back`.
- Slides và Sheets edit chỉ patch vùng/đoạn được chọn; bản cũ không khớp thì fail với conflict.
- VisualSpec được render quyết định thành PNG và SVG trên máy, không gọi model lần hai.
- Skills lưu procedure có placeholder; `skill_run` chỉ nạp procedure với context mới, không chạy code.

## Vì sao không có Code Sandbox

Project tập trung vào Google Drive và dữ liệu người dùng. Thực thi code do model sinh ra làm tăng đáng kể bề mặt tấn công nhưng không tạo đủ giá trị cho các use case bắt buộc, nên được loại khỏi phạm vi theo quyết định của người dùng.
