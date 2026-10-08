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

CI 37742152484 thành công. Bản 81665f7 đã triển khai đúng ảnh
b80b2bd6fe8e1c7acf0943cf3f2e7bd1e8f0b9ad412cf5e75a8ae86b12bd9575;
Render dep-db3kafaj9qps7380tps0 Live ngày 08/10 lúc 14:26:49 giờ Việt Nam.
Kiểm công khai xác nhận máy chủ, cơ sở dữ liệu và kho tệp hoạt động.

Lượt thật 766df02c-e80b-4a34-8436-9af39ab3205a sau triển khai:

- Hai lần tìm và hai lần đọc đúng hai tài liệu trên máy, một phép tính;
  không có công cụ Gmail, Drive, lịch, web hoặc bộ nhớ trong nhật ký lượt này.
- Dấu vết ghi một lần gọi gemini-3.5-flash-lite. Tác vụ xử lý 14.328 giây;
  từ thời điểm lưu câu hỏi đến câu trả lời khoảng 16.46 giây.
- Dùng 24 người từ bản điều chỉnh, 5760 phút mỗi tháng, tiết kiệm giả định
  1152 phút ở mức 20%; có hai nguồn và ba câu hỏi làm rõ. Không gọi mức
  giảm này là hiệu quả đã đo. Không phát sinh đề xuất ghi Google.
- Câu trả lời được giữ ở trạng thái incomplete: dưới mức tối thiểu 200 từ;
  bước sửa định dạng cũng bị bộ kiểm phát hiện thay đổi dấu trích dẫn.
  Do đó đóng riêng lỗi vòng gọi gây hết thời gian; không cấp đạt toàn W01.

Không chạy lại lượt đầu chỉ để sửa độ dài trong đợt này.

Đoạn hỏi tiếp 82bea3d1-e3e7-43a8-b45b-d0185bab8758 đã completed: giữ đúng
24 người và 12 phút, đủ ba câu hỏi, hỏi ngân sách thay vì tự đưa ra số,
nhắc mức giảm 20% chỉ là giả định. Dấu vết không có công cụ đọc nguồn mới;
mô hình trả trong 3.468 giây. Không coi nhãn bảy vai trò ready là bảy vai
trò đã thực thi.

Bản lưu a8e73a8e-a363-4f4c-91fc-1af7b847c051, revision 1, không lưu trữ,
được tạo 14:32:14 giờ Việt Nam; nội dung giữ đúng câu trả lời và hai liên
kết nguồn. Người dùng xác nhận đã thao tác mở lại; đối soát SQL chỉ đọc
xác nhận dữ liệu bền, không thay cho bằng chứng hình ảnh tự động.

Đóng riêng đoạn hỏi tiếp và lưu của W01; toàn W01 vẫn một phần do độ dài
lượt đầu. A/E/F và main chưa đóng.

## Giới hạn điều khiển giao diện

Sau khi người dùng giao tự thao tác thanh bên, cua.getState thất bại trước
khi đọc trang với lỗi: windows sandbox failed: helper_unknown_error:
setup refresh had errors. Khởi tạo lại kernel rồi thử inventory lần nữa
vẫn cùng lỗi. Chrome DevTools inventory chỉ có about:blank, không có phiên
thanh bên đã đăng nhập. Không lấy cookie, bỏ đăng nhập, viết bản ghi Chat
qua SQL hoặc giả nhận đã chạy web thật. Các ca cần giao diện đang bị chặn
ở công cụ điều khiển; không yêu cầu người dùng nhập thêm câu hỏi thủ công.
