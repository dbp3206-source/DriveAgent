# Veridra — phạm vi triển khai nhẹ

Quyết định người dùng ngày 30/09/2026: không cần triển khai thành phần Docker quá tốn tài nguyên. Không tự động xóa image, cache, container hoặc volume.

## Đo thực tế tại máy phát triển

Lệnh chỉ đọc: `docker stats --no-stream` và `docker system df`.

| Thành phần | Kết quả quan sát |
|---|---:|
| Container `veridra-packaging-qa` | RAM 284,6 MiB; giới hạn 1 GiB; CPU 0,27% |
| Images, 7 image | 6,878 GB; Docker báo 5,228 GB có thể thu hồi |
| Build cache, 61 mục | 7,943 GB; không có mục active |
| Local volumes, 5 volume | 297,1 MB |

Đây là snapshot, không phải peak RAM khi OCR hoặc benchmark đồng thời. Không cộng các số dung lượng thành kích thước chắc chắn thu hồi: layer có thể được chia sẻ, và ổ đĩa ảo Docker không nhất thiết co lại sau cleanup.

Kiểm tra lại sau yêu cầu giảm tài nguyên: `docker stats --no-stream` ghi nhận chỉ một container `veridra-packaging-qa` đang chạy, RAM **284,4 MiB / 1 GiB**, CPU **0,88%**. Không có container Langfuse/ClickHouse/MinIO/Redis đang chạy tại thời điểm kiểm tra. Đây không phải RAM tổng của Docker Desktop/WSL và không chứng minh tải đỉnh; cần phân biệt bộ nhớ engine với bộ nhớ container.

## Phạm vi mới

- Ưu tiên ứng dụng native/local để phát triển và demo.
- Không khởi động lại toàn bộ Langfuse/ClickHouse/MinIO/Redis chỉ để phục vụ Chat.
- Không build thêm image lớn khi ổ C còn ít dung lượng.
- Giữ Docker packaging là bước tùy chọn theo tài nguyên; chưa được đánh dấu PASS cho build mới.
- Cloud app nhẹ dùng PostgreSQL + private Supabase Storage; không đưa SQLite/Qdrant lên filesystem tạm để đổi lấy một URL.
- Cloud không chạy Qdrant, OCR, Langfuse, Grafana, Redis hay Kafka. Embedding được lưu trong PostgreSQL và truy hồi bằng SQL + cosine/RRF trong tiến trình, phù hợp beta tối đa bốn user nhưng không được gọi là pgvector.
- Các yêu cầu ProtonX về observability vẫn phải có bằng chứng; loại stack nặng không tự biến yêu cầu chưa kiểm chứng thành PASS.
- Docker Desktop không phải dependency để dùng Veridra local. CI chịu trách nhiệm build/test image phát hành; máy owner chỉ chạy packaging QA khi có đủ tài nguyên. Không để stack observability nặng là điều kiện bắt buộc cho Chat, ingestion hay UI.

## Dọn dung lượng (owner tùy chọn)

Chưa có dữ liệu nào bị xóa trong lượt này. Owner có thể xem Docker Desktop → Images / Builds để chọn xóa build cache cũ. Không chọn xóa volume khi chưa có backup đã kiểm tra. Không cần dọn để tiếp tục sửa/test mã backend hiện tại.
