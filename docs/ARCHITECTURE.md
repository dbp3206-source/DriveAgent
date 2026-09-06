# Kiến trúc DriveAgent

## Request lifecycle

```text
React UI
  -> FastAPI session auth
  -> LangGraph planner / ReAct router
  -> Tool Registry
       1. Resolve registered tool
       2. Audit STARTED + redact arguments
       3. Validate schema + authentication
       4. RBAC + OAuth scopes
       5. Per-user rate limit
       6. Execute + selective retry
  -> Google Drive / RAG / Memory
  -> Citation + execution trace
  -> React UI
```

## Lưu trữ

- SQLite: users, encrypted credentials, chat sessions, messages, file index, chunks, memory, audit.
- Qdrant embedded: vector index trong `data/qdrant`. Không cần Docker.
- SQLite giữ bản sao embedding. Nếu Qdrant không khởi tạo được, cosine search vẫn chạy từ SQLite và health báo `sqlite-fallback`.
- LangGraph SQLite checkpointer: `data/langgraph_checkpoints.db`.

## Multi-user

Chạy local không đồng nghĩa với thiết kế single-user. Các bảng dữ liệu riêng có `user_id`; mọi query đều filter server-side. Frontend không được quyền truyền `user_id` để tránh đọc dữ liệu của người khác.

## Orchestration Harness

- Planning: model tạo kế hoạch 1-5 hành động trước vòng ReAct.
- Workflow: StateGraph có node planner, agent, tools và limit.
- State: messages, user/session/request ID, plan, số vòng tool, trace.
- Routing: conditional edge dựa vào tool calls.
- Execution: ToolNode có thể chạy các tool calls độc lập song song; mỗi call dùng database session riêng.
- Recovery: registry retry lỗi tạm thời; ToolNode trả lỗi về model để điều chỉnh; hard stop sau 6 vòng.
- Model recovery: `gemini-3.8-flash` là primary; lỗi provider/model được chuyển sang
  `gemini-3.5-flash-lite`. Vòng lặp tool lặp lại bị chặn trước hard stop.
- Checkpoint: graph state được lưu theo `user_id:session_id`.

## Vì sao không có Code Sandbox

Project tập trung vào Google Drive và dữ liệu người dùng. Thực thi code do model sinh ra làm tăng đáng kể bề mặt tấn công nhưng không tạo đủ giá trị cho các use case bắt buộc, nên được loại khỏi phạm vi theo quyết định của người dùng.
