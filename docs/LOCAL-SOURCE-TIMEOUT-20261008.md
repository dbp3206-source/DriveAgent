# Đọc nguồn được chỉ định — nguyên nhân và sửa gọn

## Bằng chứng trên bản 1baf5e6

- Lượt `d3b1a9af-52b0-4172-9b2c-c51e2871eb8a`, 14:01 ngày 08/10/2026.
- Ngân sách ngày đã đặt lại lúc 14:00; không còn lỗi hết ngân sách ngày.
- Hai lượt tìm, hai lượt đọc và phép tính đều thành công. Nhật ký có năm
  lần gửi mô hình từ 07:01:23 đến 07:01:41 UTC; phản hồi cuối lúc 07:01:43.
- Bộ đếm ghi đúng năm giữ chỗ trong phút, chạm giới hạn 5 lượt/phút.
  Lượt tiếp theo chờ `reserve_with_wait(max_wait_seconds=60)` trong khi
  toàn yêu cầu cũng bị giới hạn 60 giây. Tác vụ dừng ở 60.578 giây.
- Không có mã Google 503/504 trong cửa sổ nhật ký này. Không gán lỗi mới
  này cho sự cố quá tải hôm qua. Thông báo hết thời gian hiện quy lỗi quá
  rộng cho Gemini, trong khi việc chờ lượt nội bộ cũng nằm trong phạm vi đó.

## Nguyên nhân trong mã và thay đổi

Tên tệp không nói rõ nơi lưu nên tuyến tự động suy đoán Drive. Người dùng
cấm Drive khiến tuyến bị loại; quyết định chọn luồng xử lý chưa áp dụng
lựa chọn nguồn hiệu lực nên chuyển sang vòng điều phối nhiều lượt.

Sửa hai điểm, không thêm quy trình mới:

1. Với yêu cầu chỉ đọc tệp có tên, cấm Drive nhưng không cấm nguồn trên
   máy, chọn nguồn trên máy. Không ghi đè nguồn người dùng đã chọn.
2. Quyết định dùng luồng đọc nguồn có sẵn dựa trên tuyến đã áp dụng lựa
   chọn và giới hạn nguồn. Quy trình đã lưu vẫn giữ tuyến được quản lý riêng.

Tái sử dụng: tìm/đọc đúng tệp → tổng hợp có dẫn nguồn → thực hiện phép tính
bằng công cụ → kiểm kết quả trước khi công bố. Không tăng hạn mức, xóa bộ
đếm, mở nguồn bị cấm hoặc biến số liệu giả lập thành hiệu quả đã đo.

## Trạng thái nghiệm thu

Kiểm tự động cục bộ: 266 phép kiểm đạt trong 42,95 giây (ADK, điều khiển
nguồn, luồng tổng hợp, định tuyến và ngân sách ở hai kho lưu). Ruff và
`git diff --check` đạt. Không gọi Gemini thật trong đợt kiểm này. Kiểm
bao gồm giữ lựa chọn nguồn đã lập chỉ mục và không coi câu cấm đọc là
yêu cầu chuyển sang nguồn trên máy.

Chưa có câu trả lời hoàn chỉnh của W01 để chấm; không đóng B/E hoặc main.
Bản sửa cần qua kiểm tự động và triển khai trước một phép kiểm gộp thật.
