# RAG và Memory

## Ingestion

1. Đọc file qua `drive_read_file`, không bỏ qua registry.
2. Chuyển Google Workspace file sang text/CSV/PDF; MarkItDown xử lý PDF và Office.
3. Chuẩn hóa khoảng trắng rồi chia theo paragraph, câu và hard split cuối cùng.
4. Dùng overlap để giữ ý qua biên chunk.
5. Sinh Gemini embedding 768 chiều với task type `RETRIEVAL_DOCUMENT`.
6. Lưu chunk + metadata vào SQLite và vector vào Qdrant embedded.
7. Stable UUID giúp ingestion idempotent; content hash tránh index lại file không đổi.

## Retrieval

- Dense score tìm đoạn gần nghĩa.
- Lexical score giữ độ chính xác cho tên riêng, mã và từ khóa hiếm.
- Reciprocal Rank Fusion gộp thứ hạng mà không trộn trực tiếp hai thang điểm.
- Filter `user_id` là bắt buộc; `file_ids` là filter tùy chọn.
- Citation gồm file ID, tên, chunk index, snippet, link Drive và score.

## Memory

Các loại: FACT, PREFERENCE, CONTEXT, EPISODIC, PROCEDURAL, SUMMARY.

- Raw chat messages nằm ở SQLite theo session.
- Long-term memory có normalized hash để chống trùng.
- Tìm memory kết hợp semantic và keyword overlap.
- Secret-looking content bị từ chối trước khi lưu.
- User có thể xem, archive và delete.
