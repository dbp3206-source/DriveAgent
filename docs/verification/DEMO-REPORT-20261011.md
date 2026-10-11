# Báo cáo kiểm sản phẩm ngày 11/10/2026

## Phạm vi và cách đọc

Chạy thật trên [Veridra](https://veridra-closed-beta.onrender.com/) trong trình
duyệt thanh bên, bằng một tài khoản quản trị. Mô hình được ghi nhận là Gemini
3.5 Flash Lite theo giao diện/dấu vết; không đối chiếu chất lượng với một mô hình
mạnh hơn. Ưu tiên chính xác, nguồn, bố cục và đúng yêu cầu, không chấm cứng số từ.

Đây là bản tổng hợp công khai từ biên bản có sẵn, không phải đợt chạy lại. Không
sửa mã, đổi khóa, đặt lại hạn mức hoặc đổi gói dịch vụ để lập báo cáo. Bản Word
41 trang, 26 ảnh minh chứng và 38 ảnh gốc giữ nội bộ vì có thông tin tài khoản,
thư và tệp riêng. Bản công khai không kèm ảnh hoặc đường dẫn đến dữ liệu đó.

## Kết quả theo ca

| Ca | Phần được kiểm | Kết quả thực tế | Đánh giá |
|---|---|---|---|
| TC01 | Trang chủ, Cài đặt, Phân quyền, mô tả hoạt động | Mở được; ảnh mới tải được; trạng thái quyền hiện có rõ | Đạt trong phiên quản trị; không chứng minh đăng nhập mới/nhiều người |
| TC02 | Drive gần đây, thư mục/tệp, gắn sao, tìm kiếm | Các bộ lọc dùng được; tìm toàn văn lỗi 403 do kết hợp sắp xếp không được hỗ trợ | Đạt một phần |
| TC03 | Nhập Markdown/CSV, đọc hiệu chỉnh, tính toán | GD01 đúng 24 người, 96 giờ, tiết kiệm 19,2 giờ; CSV nhập được nhưng câu hỏi đối soát lỗi | Đạt một phần; chưa xác định chắc nguyên nhân lỗi CSV |
| TC04 | Hỏi tiếp, tải lại lịch sử, đổi khách hàng | 25% đúng 24 giờ tiết kiệm, còn 72 giờ; An Bình 8 người không bị trộn số Minh Phát | Đạt chuỗi đã kiểm |
| TC05 | Tạo/sửa/tra/cất bộ nhớ | Tra trực tiếp đúng; ghi chú đã cất không được dùng; tự chọn bộ nhớ có lượt không gọi tra | Đạt một phần |
| TC06 | Tạo/sửa/nạp/chạy quy trình | Bản mới lưu v1/v2 và nạp đúng tham số; có xung đột lần lưu tiếp; Hoa Mai chạy đúng với quy trình đã có | Đạt một phần; chưa chạy mô hình với chính quy trình mới |
| TC07 | Gmail, các chế độ xem, ảnh, soạn thư | Đọc nội dung và xem trước bản soạn được; ảnh ngoài vỡ | Đạt một phần; không gửi, không xác nhận lưu nháp/tệp đính kèm |
| TC08 | Đầu ngày, trước cuộc hẹn, đọc thư/lịch | Nút nạp đúng; câu trả lời nói thiếu công cụ; không có vết đọc thư/lịch dù giao diện Gmail đọc được | Chưa đạt; không suy ra thư hoặc lịch trống |
| TC09 | Tìm web, lưu/sửa/xuất kết quả, Google Doc có duyệt | Web bị giới hạn theo phút của ứng dụng; lưu/xuất được; tạo đúng một Doc giả lập sau duyệt và đọc lại đúng | Đạt một phần; không lấy kết quả Doc thay cho chất lượng web |
| TC10 | Xem/xuất/đối chiếu nhật ký | Truy nguyên được các thao tác và lỗi; xuất JSON được | Đạt phạm vi đã quan sát |

Tổng: **3 đạt, 6 đạt một phần, 1 chưa đạt**. Có 10 câu hỏi gửi mô hình, 8 phản
hồi văn bản, 2 yêu cầu lỗi. Số phản hồi không phải số câu trả lời đúng.

Chi tiết lời giải, nhận xét và giới hạn từng ca nằm trong
[kết quả có cấu trúc](evidence/demo-results-20261011.json). Đầu vào và đáp án nằm
trong [bộ dữ liệu chuẩn](golden/README.md).

## Những kết luận có và không có bằng chứng

- Có bằng chứng cho các bước đọc GD01, hỏi tiếp, đổi khách, quản lý ghi chú trực
  tiếp, lọc Drive, đọc nội dung Gmail, lưu/xuất kết quả, duyệt/tạo/đọc lại Google
  Doc giả lập và truy nguyên nhật ký.
- Chưa có đủ bằng chứng cho toàn bộ chuỗi tự chọn bộ nhớ, quy trình mới, thư/lịch
  đầu ngày, chất lượng câu trả lời web ở lượt bị chặn, tệp đính kèm và đối soát CSV.
- Không kiểm đủ nhiều người dùng thật, khôi phục dữ liệu, tốc độ sau ngủ hoặc mọi
  vai trò trợ lý. Các kiểm nội bộ riêng không lấp được khoảng trống này.
- Không quy mọi lỗi cho Google hoặc Gemini. Lỗi Drive có thông điệp cụ thể; lỗi
  web ghi nhận chốt hạn mức theo phút của ứng dụng; lỗi CSV chưa đủ căn cứ.
- Không dùng số thành công trong nhật ký làm điểm đúng của câu trả lời. Không
  công bố điểm chất lượng tổng hợp hoặc hiệu quả kinh doanh chưa được đo.

## Kết luận bàn giao

Sản phẩm có bản demo đang triển khai và nhiều quy trình đã chạy thật. Bộ kiểm này
không xác nhận toàn bộ sản phẩm sẵn sàng vận hành. Các vấn đề được ghi nhận để
người dùng quyết định phạm vi sử dụng; tài liệu không tự mở thêm vòng sửa mã.
