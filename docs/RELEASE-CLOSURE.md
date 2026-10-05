# Đợt nghiệm thu cuối — 05/10/2026

Danh sách điều hành được người dùng yêu cầu tinh gọn. Sáu nhóm dưới đây gom
checklist hiện hành, không bỏ các yêu cầu bắt buộc trong ACCEPTANCE-CHECKLIST.md.
Không thêm tính năng hoặc thiết kế lại. Tiêu chí chưa có bằng chứng giữ chưa đạt.

| Nhóm | Việc còn lại | Điều kiện đóng |
|---|---|---|
| A | Độ dài báo cáo, bảo toàn dẫn nguồn, phạm vi số liệu PDF, bản xem trước Doc hết hạn | Ca lỗi đã tái hiện đạt trên URL thật; duyệt và đọc lại đúng, không trùng |
| B | Ba quy trình đầu ngày, trước hẹn, hoàn thiện/lưu; ghép kiểm nguồn, hỏi tiếp, quy trình đã lưu, nhớ/sửa/quên | Hoàn thành xuyên suốt, bảy vai trò và kiểm soát công cụ có dấu vết; hẹn giờ có lần chạy thật |
| C | Tốc độ mở khi đang chạy/sau ngủ, đăng nhập, đổi khóa, hết hạn mức, lỗi mạng; giao diện và ảnh/bộ lọc đã yêu cầu | Số đo theo ngưỡng đã khóa; không chờ vô hạn hoặc mất việc; thao tác chính dùng được |
| D | Quyền, chỉ dẫn độc hại, duyệt; tiếp tục sau triển khai; khôi phục DB và tệp sang đích riêng; quan sát đã cam kết | Không lộ/ghi trái quyền/trùng; đối soát bản khôi phục và truy nguyên thật |
| E | Hoàn thành 24 tác vụ đã khóa, ca bộ nhớ, đối chứng và lỗi giả lập hiện có | Tổng >=8,7/10; nguồn/nghiệp vụ/tin cậy >=9; đủ mẫu, không lỗi nghiêm trọng hoặc quy trình chính thất bại |
| F | Máy sạch, hướng dẫn, demo 10 phút, tài liệu đúng khả năng, CI, main, Render, quay lui | Cùng bản đã nghiệm thu; URL và hướng dẫn dùng được |

Thứ tự A, sau đó B/C/D song song theo khả năng, E và F cuối. Mỗi mục đạt được
đóng; chỉ kiểm lại khi thay đổi ảnh hưởng trực tiếp. Sửa lỗi theo ca liên quan;
chạy toàn bộ kiểm máy ở bản chốt. Không gọi mô hình lặp để chọn câu trả lời đẹp.
Chỉnh thẩm mỹ nhỏ và tiện ích phụ được để bản sau, không chặn phát hành.

Bốn người thật hiện thiếu ba người: giữ CHƯA KIỂM CHỨNG, không chứng nhận từ
tài khoản quản trị. Render miễn phí ngủ khi không hoạt động; không hứa luôn bật.
OCR/PDF ảnh, dịch vụ trả phí, ghi Calendar và hạ tầng nặng vẫn ngoài phạm vi.
PDF có văn bản vẫn trong phạm vi.

## Điểm bắt đầu có bằng chứng

- Staging 4a4577d: CI 37323704603 thành công; bản sửa phục hồi bản xem trước có
  187 phép kiểm giao diện đạt, kiểm mã/dựng ứng dụng đạt. Chưa nghiệm thu cloud
  của thay đổi này trong hồ sơ hiện tại.
- Cloud d319f1d: còn báo cáo ngắn, bản sửa định dạng bị từ chối; chưa có Doc tạo
  thành công trong đợt kiểm hiện tại. Không dùng trạng thái máy chủ khỏe để đóng A/B.
- Project khôi phục riêng đã tạo; chưa có bằng chứng dữ liệu đã khôi phục.
- Hồ sơ lịch sử: design-work/qa/LIVE-ACCEPTANCE-20261005.md. Không đổi nhãn các
  phép đo cũ thành bằng chứng bản mới.

Kết thúc khi sáu nhóm và điều kiện áp dụng có đủ bằng chứng. Khi đó đóng phiên
bản và dừng chỉnh sửa; không mở thêm vòng hoàn thiện chung chung.
