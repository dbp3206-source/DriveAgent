# Tool Registry sáu cổng

Mọi đường vào tool, gồm REST API, agent và ingestion lồng nhau, đều gọi `ToolRegistry.execute`.

1. **Resolve tool**: chỉ thực thi tool đã đăng ký với contract rõ ràng.
2. **Audit log**: ghi `STARTED` và redact arguments trước các cổng còn lại.
3. **Validate + Authentication**: Pydantic chặn payload sai; context phải có user active.
4. **Authorization**: RBAC permission và OAuth scopes được kiểm tra độc lập.
5. **Rate limit**: sliding window theo `(user_id, tool_name)`.
6. **Execute**: timeout và retry có exponential backoff + jitter.

Audit được hoàn tất với `success`, `error` hoặc `denied`, nên cả lần gọi có schema sai,
thiếu quyền hoặc vượt rate limit cũng truy vết được mà không gọi dịch vụ bên ngoài.

Chỉ retry timeout, network error và HTTP 408/429/500/502/503/504. Không retry 400/401/403/404 vì đây là permanent failure cần sửa request hoặc quyền.

Các tool hiện có: `drive_list_files`, `drive_search_files`, `drive_read_file`, `rag_index_drive_file`, `rag_search`, `memory_save` và `memory_search`.

Endpoint `/api/tools` trả về JSON Schema, permission, OAuth scope và rate limit thật của registry.
