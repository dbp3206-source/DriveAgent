# Drive — kiểm bộ lọc và thứ tự gần đây, 04/10/2026

## Phạm vi và nguồn
Yêu cầu người dùng: mở Drive theo hoạt động gần đây, lọc mục gắn sao/thư mục/tệp dưới thanh tìm kiếm. Giữ hệ thống Fluent, kiểu chữ và màu hiện có; không dựng lại trang. Mã thật tại `frontend/src/pages/DrivePage.tsx`, `frontend/src/styles.css`, `backend/app/api/drive.py`, `backend/app/tools/drive.py`.

Google định nghĩa `recency` là thời điểm mới nhất từ các trường ngày của tệp: [tài liệu files.list](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list). Màn hình dùng thứ tự này; công cụ tác vụ giữ mặc định `modifiedTime` để không đổi ngầm các luồng cũ. Bộ lọc thực hiện ở Google trước phân trang, không chỉ lọc danh sách đang thấy.

## Thực thi và bằng chứng
- Máy chủ: `backend/.venv/Scripts/python.exe -m pytest backend/tests -q`, chạy tại gốc dự án: 1.046 đạt, 14 bỏ qua, 189,68 giây. Bỏ qua gồm 11 ca cần PostgreSQL riêng, một ca quyền tệp Windows và hai ca tạo liên kết không khả dụng.
- Sau điều chỉnh thứ tự gần đây: bộ kiểm hai tệp liên quan đạt 20 ca; Ruff đạt. Bộ đầy đủ trước điều chỉnh nhỏ này không chứng nhận lại cùng bản; hệ thống GitHub phải chạy lại bản đã chốt.
- Giao diện: 171 ca đạt; kiểm mã và đóng gói đạt. Quét bí mật đạt trên 524 tệp Git thấy được ở thời điểm chạy.
- Trình duyệt thật: `node scripts/qa-drive-filters.mjs`, Chrome cài trên máy qua Playwright. Bốn chiều rộng 320/375/768/1440, giao diện sáng/tối, giảm chuyển động; kiểm kết hợp loại/sao và tìm kiếm. Không lỗi JavaScript hoặc tràn ngang trong các ca này.
- Ảnh và bản ghi: `design-work/qa/screenshots/drive-filters-20261004/`. API trong phép kiểm giao diện dùng dữ liệu giả lập, không phải kết quả Google thật và không phải số đo chất lượng nghiệp vụ.

## Lỗi kiểm tra đã xử lý
Lần chạy máy chủ từ thư mục backend không tìm thấy các tiện ích scripts; đổi về gốc dự án đúng như CI, không sửa sản phẩm vì lỗi cách chạy. Playwright thiếu trình duyệt đóng gói; dùng Chrome thật đã cài, không tải thêm. Lần chụp đầu trúng khung đang xuất hiện; thêm chờ độ đục hoàn tất. Nút Fluent mặc định quá rộng ở điện thoại; giới hạn chiều rộng tối thiểu và kiểm lại.

## Kết luận giới hạn
Đạt kiểm mã/truy vấn và hình thức cục bộ. Chưa đóng nghiệm thu Google thật hoặc bản Render cho chức năng mới. Điểm giao diện cục bộ 84/100: nội dung 18, phù hợp 18, cấu trúc 12, dễ đọc 13, bố cục 13, hoàn thiện 10. Đây là đánh giá thiết kế, không đưa vào số đo sản phẩm. Toàn bộ điều kiện phát hành vẫn cần bằng chứng riêng.

Ảnh hành trình là PNG người dùng cung cấp, đã đóng gói tại `frontend/public/harness/veridra-verified-workflow.png`; các con số trong ảnh được ghi là minh họa. Không phát sinh tài sản bên thứ ba hoặc kỹ năng tạo ảnh mới.
