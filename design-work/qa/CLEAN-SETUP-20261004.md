# Cài đặt từ mã sạch — 04/10/2026

## Phạm vi
Bản nguồn `cf93473` được xuất bằng git archive vào `tmp/clean-setup-python-fix`, không sao chép .env, cơ sở dữ liệu, khóa hoặc tài khoản thật. Sau phát hiện lỗi Windows PowerShell, script trong bản thử được sửa cùng bản chính và đối chiếu checksum bằng nhau. Thư mục này là mã sạch, không phải máy Windows mới hoặc môi trường cloud mới.

## Lỗi đã tái hiện và sửa
- Script cũ chấp nhận Python Windows 3.14 dù thư viện dự án không hỗ trợ. Bản sửa chỉ chọn 3.11/3.12, kiểm cả môi trường đã tồn tại và không tự xóa dữ liệu khi sai phiên bản.
- Cài đặt cũ giải phiên bản thư viện mới bằng pip; nay dùng uv 0.12.19 và uv.lock như CI, frontend giữ npm ci.
- Windows PowerShell đọc UTF-8 không có dấu nhận diện làm hỏng thông báo tiếng Việt, thậm chí lỗi phân tích chuỗi. Script đã có dấu nhận diện UTF-8; kiểm bằng chính Windows PowerShell đạt, đọc đúng “Setup hoàn tất”.

## Kết quả thực thi
- Cài đặt sạch đạt: Python 3.12.14, 161 gói từ bản khóa; npm ci thêm 474 gói, kiểm 475 gói và báo 0 lỗ hổng theo dữ liệu kiểm tại thời điểm chạy. Đây không phải bảo đảm phần mềm không có lỗ hổng.
- uv pip check trên môi trường mới: 163 gói tương thích (bao gồm tiện ích cài đặt).
- npm run build đạt; tạo `index-BYFPDCw1.js`, cùng mã tệp đang được phục vụ trên Render bản 30a2ec4.
- 40 ca Drive/API/xuất báo cáo/tác vụ Chat đạt; 11 ca cấu hình đạt. Không gọi Gemini hoặc Google trong bộ này.
- Khởi động FastAPI từ thư mục mới tại 127.0.0.1:8012 đạt; database mới rỗng, health ok, trang chính HTTP 200, chưa đăng nhập. Không cần Docker.
- Snapshot lúc rảnh: bộ nhớ làm việc 229,1 MiB, bộ nhớ riêng 305,1 MiB; không phải tải đỉnh hoặc phép thử 30 phút.
- Quét bí mật hiện hành đạt 526 tệp; quét lịch sử đạt 851 đối tượng có giới hạn. Không thay thế rà dữ liệu cá nhân hoặc các tệp lớn hơn giới hạn của bộ quét.

## Giới hạn còn giữ
Chưa hoàn thành đăng nhập Google/khóa riêng và ba quy trình nghiệp vụ từ máy mới, vì không sao chép danh tính người dùng vào bản thử. Chưa phục hồi PostgreSQL và Storage sang môi trường cloud riêng; chưa có bốn tài khoản thật. Vì vậy bằng chứng này đóng phần cài thư viện/đóng gói/khởi động từ mã sạch, không đóng toàn bộ E3 hoặc F3, không tạo điểm chất lượng nghiệp vụ.

Môi trường thử đã được dừng sau kiểm; không xóa các thư mục kiểm và không đụng cơ sở dữ liệu đang dùng. Script mới cùng hồ sơ được lưu staging; bản Render 30a2ec4 không đổi chỉ vì hướng dẫn đã được cập nhật.
