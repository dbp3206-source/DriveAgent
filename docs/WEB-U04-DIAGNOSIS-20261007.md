# Đối soát lỗi U04 — 07/10/2026

## Kết quả thật

- Bản đang chạy: 8c4de13b3e5a4bce2c76a25b9c706abf98f2ebd7.
- Yêu cầu: feeee879-1b26-4fad-a296-51fd1f48fdea, lúc 13:28:33 UTC.
- Trang ai.google.dev/gemini-api/docs/rate-limits trả HTTP 200 lúc 13:28:41 UTC.
- Bước tổng hợp thất bại: source_bundle_summary_failed. Không có câu trả lời để chấm.
- Trạng thái bộ ngắt của khóa đang dùng ghi generate/provider lúc 13:28:43.406412 UTC,
  không ghi quota. Điều này không chứng minh hạn mức Google còn bao nhiêu.

## Điều đã loại trừ và điều chưa biết

Đã loại trừ lỗi không tải được trang chính thức trong đúng lượt này.
Đã chạy chuyển đổi và gửi yêu cầu bằng SDK Google thật tới httpx.MockTransport,
với khóa giả, không kết nối Gemini: chuyển đổi cấu trúc và đọc phản hồi đều thành công.
Điều này chỉ loại trừ lỗi chuyển đổi cục bộ, không chứng minh máy chủ Google chấp nhận
cấu trúc gửi lên. Chưa xác định lỗi máy chủ, tên mô hình hay cấu trúc nào bị từ chối.

Nguyên nhân không thể chẩn đoán chính xác từ biên nhận hiện có: lớp bao lỗi đã bỏ
mã HTTP/loại lỗi gốc, chỉ giữ source_bundle_summary_failed. Không suy đoán sửa cấu trúc,
đổi mô hình hoặc yêu cầu đổi khóa khi chưa có bằng chứng.

## Thay đổi giới hạn

Giữ mã HTTP thuộc danh sách cố định hoặc loại lỗi cấu hình/dịch vụ trong mã lỗi công cụ.
Không lưu thông báo thô từ nhà cung cấp, nội dung nguồn, khóa, hoặc mật khẩu.
Không tự thử lại lỗi 400/404 không thể khắc phục bằng chờ. Không tăng hạn mức,
không gọi thêm nguồn hoặc mở rộng bộ kiểm. Đây là chẩn đoán, chưa phải sửa nguyên nhân
thất bại U04. Chưa đóng A/E/F hoặc gộp main.

## Kiểm chứng bản chẩn đoán

59 phép kiểm đạt trong test_web_reasoning.py và test_public_freshness.py.
Ruff và git diff --check đạt. Các ca mới kiểm mã 400/404/429/503, tính có thể
thử lại và không lộ nội dung riêng. Không phép nào gọi Gemini thật.

Nguồn đối soát: biên nhận lưu trong Supabase, nhật ký ứng dụng Render đúng lượt,
SDK Google cài trong backend/.venv. Thao tác đã thực hiện bằng Supabase và Render;
không tuyên bố đã xem trực tiếp giao diện thanh bên.
