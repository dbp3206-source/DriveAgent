# Tool Registry sáu cổng

Mọi đường vào tool, gồm REST API, agent và ingestion lồng nhau, đều gọi `ToolRegistry.execute`.

1. **Validate schema**: Pydantic từ chối argument thiếu, sai kiểu hoặc vượt giới hạn.
2. **Authentication**: context phải có user đang active.
3. **Authorization**: RBAC permission và OAuth scopes được kiểm tra độc lập.
4. **Rate limit**: sliding window theo `(user_id, tool_name)`.
5. **Audit log**: ghi `STARTED` trước khi gọi dịch vụ; arguments đã redaction.
6. **Execute**: timeout và retry có exponential backoff + jitter.

Chỉ retry timeout, network error và HTTP 408/429/500/502/503/504. Không retry 400/401/403/404 vì đây là permanent failure cần sửa request hoặc quyền.

Các tool hiện có: `drive_list_files`, `drive_search_files`, `drive_read_file`, `rag_index_drive_file`, `rag_search`, `memory_save` và `memory_search`.

Endpoint `/api/tools` trả về JSON Schema, permission, OAuth scope và rate limit thật của registry.
