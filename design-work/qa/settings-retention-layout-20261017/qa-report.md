# Kiểm hồi quy bố cục phần lưu giữ — 17/10/2026

## Kết luận

Đã tìm được nguyên nhân của lỗi thấy trực tiếp trên trang Cài đặt bản đang chạy: lưới có 12 cột, phần trạng thái hệ thống chiếm 8 cột, nhưng thẻ “Thời hạn lưu giữ” không được chỉ định vị trí. Trình duyệt tự đặt thẻ vào 4 cột còn trống. Tiêu đề bên trong lại cần tối thiểu 180 + 260 px, nên nội dung tràn khỏi thẻ và làm xuất hiện thanh cuộn ngang.

Đã sửa đúng bố cục: thẻ lưu giữ chiếm toàn hàng, nằm dưới trạng thái hệ thống. Không đổi nội dung, thao tác, màu sắc hay thiết kế các phần khác.

## Kiểm tra

- Trình duyệt thật trên URL trước sửa: ảnh và cây truy cập cho thấy thẻ bị ép hẹp và nội dung tràn. Không đọc hoặc thay đổi dữ liệu tài khoản.
- Kiểm hồi quy bằng Chrome với CSS thật của sản phẩm và nội dung giả lập: 1280×900 và 390×844, cả sáng/tối. Cả 4 trường hợp đều đặt thẻ toàn hàng sau trạng thái hệ thống, không tràn ngang.
- Frontend: 224 bài đạt; ESLint đạt; bản dựng production đạt.
- Backend lưu giữ cô lập: 221 bài đạt, 1 bài bỏ qua; không dùng dữ liệu cloud, Gemini hoặc Google.
- Ảnh giao diện tổng hợp giả lập: `desktop-light.png`, `desktop-dark.png`, `mobile-light.png`, `mobile-dark.png`. Báo cáo số đo của kiểm hồi quy: `report.json`.

## Giới hạn

Sửa đổi chưa qua CI cho mã mới và chưa phát hành. Phải kiểm lại trang Cài đặt trên Render sau khi đúng ảnh mới được triển khai; hiện chưa tính lỗi này là đã sửa trên sản phẩm đang chạy. Kiểm khôi phục DB/tệp vẫn được chủ sở hữu cho miễn, nên chưa được ghi là đạt.

## Công cụ và tài sản

- Dùng hệ thống CSS hiện có của Veridra; không thêm thư viện hoặc ảnh bên ngoài.
- Dùng Playwright với Chrome cài sẵn cho ca tổng hợp. Lượt đầu dùng cấu hình Chromium riêng nhưng trình duyệt đó không được cài; chuyển sang Chrome theo lệnh kiểm thử đã có trong repo.
- Screenshot chỉ chứa nhãn giả lập; không chứa email, khóa, thư, tài liệu hoặc dữ liệu tài khoản.
