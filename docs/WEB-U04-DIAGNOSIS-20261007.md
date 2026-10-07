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

## Lỗi cấu hình xác định thêm sau đối soát

Đã đọc mô tả API công khai của Google tại
https://generativelanguage.googleapis.com/$discovery/rest?version=v1beta:
Schema của responseSchema không có additionalProperties. SDK thật gửi
additional_properties=false vào responseSchema từ PublicAnswer(extra='forbid').
Đây là lệch định dạng xác định được bằng dữ liệu gửi thật và hợp đồng API,
không phải lỗi chuyển đổi cục bộ. Phần compiler của sản phẩm đã dùng
response_json_schema vì chính ràng buộc này. Tuy nhiên biên nhận U04 cũ không
giữ mã lỗi máy chủ, nên chưa thể chứng minh đây là nguyên nhân duy nhất của lượt đó.

Đã chuyển tổng hợp web sang response_json_schema, giữ đầy đủ kiểm trích đoạn
và kiểm dữ liệu cục bộ. Không đổi mô hình, không gọi thêm lượt, không bỏ bước
suy luận. Phép kiểm mới dùng SDK thật và MockTransport để xác nhận trường
responseJsonSchema có ràng buộc đúng, không gửi responseSchema cũ.

## Thay đổi giới hạn

Giữ mã HTTP thuộc danh sách cố định hoặc loại lỗi cấu hình/dịch vụ trong mã lỗi công cụ.
Không lưu thông báo thô từ nhà cung cấp, nội dung nguồn, khóa, hoặc mật khẩu.
Không tự thử lại lỗi 400/404 không thể khắc phục bằng chờ. Không tăng hạn mức,
không gọi thêm nguồn hoặc mở rộng bộ kiểm. Đây là chẩn đoán, chưa phải sửa nguyên nhân
thất bại U04. Bản sửa lệch định dạng nêu trên vẫn cần kiểm trên sản phẩm.
Chưa đóng A/E/F hoặc gộp main.

## Kiểm chứng bản chẩn đoán và sửa định dạng

59 phép kiểm đạt cho bản chẩn đoán ban đầu. Sau sửa định dạng, 85 phép kiểm
đạt trong test_web_reasoning.py, test_public_freshness.py,
test_web_source_failures.py và test_protonx_hardgates.py (17,32 giây).
Lần gọi đầu bộ kiểm mở rộng không chạy được vì tên test_protonx_tools.py không tồn tại;
đã chọn đúng test_protonx_hardgates.py rồi chạy đầy đủ, không tính lần sai là đạt.
Ruff và git diff --check đạt. Các ca mới kiểm mã 400/404/429/503, tính có thể
thử lại và không lộ nội dung riêng. Không phép nào gọi Gemini thật.

Nguồn đối soát: biên nhận lưu trong Supabase, nhật ký ứng dụng Render đúng lượt,
SDK Google cài trong backend/.venv. Thao tác đã thực hiện bằng Supabase và Render;
không tuyên bố đã xem trực tiếp giao diện thanh bên.
