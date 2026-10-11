# Bộ dữ liệu chuẩn để thử Veridra

Phiên bản `demo-20261011-public.1`. Toàn bộ GD01–GD05 là dữ liệu giả lập, không
phải khách hàng, giao dịch hoặc cuộc hẹn thật. Đây là bộ kiểm thủ công có đáp án,
không phải chương trình tự gửi câu hỏi hay tự thao tác Google.

## Thành phần

| Tệp | Mục đích | Đáp án trọng tâm |
|---|---|---|
| [GD01 Minh Phát](inputs/GD01-minh-phat.md) | Đọc hiệu chỉnh, tính toán, hỏi tiếp | 24 người, 96 giờ; 20% tiết kiệm 19,2 giờ; đổi 25% tiết kiệm 24 giờ |
| [GD02 An Bình](inputs/GD02-an-binh.csv) | Nhập bảng, đối soát số có dấu và số tuyệt đối | -5/+3/0; tổng có dấu +50.000 đồng; tổng lệch tuyệt đối 550.000 đồng |
| [GD03 Hoa Mai](inputs/GD03-hoa-mai.md) | Dùng quy trình với ngành khác | 60%/25%/15%; không suy doanh thu |
| [GD04 Lam Sơn](inputs/GD04-lam-son.md) | Lưu, sửa, tra và cất ghi chú đúng phạm vi | Bốn mục; không áp dụng sang khách hàng khác |
| [GD05 Thư giả lập](inputs/GD05-thu-gia-lap.md) | Chuẩn bị thư và duyệt | Đúng giờ/ngày; chỉ xem trước, không gửi |

- [10 ca đầy đủ: yêu cầu, đầu vào, thao tác, câu hỏi và kỳ vọng](testcases.json).
- [Đáp án độc lập và cách chấm](expected-answers.md).
- [Danh mục và SHA-256](manifest.json).
- [Kết quả chạy thật lịch sử](../DEMO-REPORT-20261011.md).

## Cách chạy gọn

1. Mở Veridra, đăng nhập tài khoản được phép và kiểm tra hạn mức. Không dùng khóa
   hoặc phiên đăng nhập của người khác.
2. Chạy TC01–TC02 để xem màn hình và bộ lọc. Chỉ tìm tệp của chính mình hoặc tệp
   được phép truy cập.
3. Nhập GD01 và GD02 ở Tài liệu local. TC03–TC04 nối tiếp trong cùng cuộc trò
   chuyện; luôn chỉ rõ tên nguồn. Đổi khách hàng phải bỏ dữ kiện khách cũ.
4. TC05 tạo ghi chú Lam Sơn; TC06 lưu và nạp quy trình. Không coi việc lưu thành
   công là bằng chứng mô hình đã dùng đúng ghi chú hoặc quy trình.
5. TC07 dùng GD05 và dừng ở bản xem trước. TC08 chỉ đọc thư/lịch thật nếu chủ tài
   khoản đồng ý gửi phần liên quan đến nhà cung cấp mô hình. Không có chấp thuận
   thì chỉ kiểm nút nạp câu hỏi và ghi phần đọc nguồn là chưa chạy.
6. TC09 kiểm nguồn web nếu còn hạn mức; thử lưu/xuất bằng kết quả giả lập. Tạo
   Google Doc là thao tác ghi riêng: cần quyền và duyệt; không tự gửi thư.
7. TC10 đối chiếu nhật ký với việc vừa làm. Ghi đúng đạt/đạt một phần/chưa đạt/
   chưa chạy, lỗi và thời gian quan sát; không chạy lại chỉ để đủ độ dài.

Không cần chạy liên tục cả bộ nếu hết hạn mức. Ghi điểm dừng, giữ đầu vào và kết
quả, không đặt lại bộ đếm để làm đẹp kết quả. Các số tiết kiệm trong GD01 là giả
thuyết để kiểm phép tính, không phải hiệu quả đã đo của sản phẩm.

## Mức chất lượng cần đạt

Ưu tiên đúng dữ kiện, phép tính, khách hàng và nguồn; bố cục tiếng Việt rõ ràng,
phân biệt điều đã biết với suy luận và điều chưa xác nhận. Độ dài chỉ ước lượng.
Chấm đúng yêu cầu và khả năng của mô hình đang dùng; không đòi văn phong giống
một mô hình mạnh hơn, nhưng không nới lỏng sai số học, bịa nguồn hoặc ghi trái quyền.

Bản công khai đã thay thao tác chọn thư thật cụ thể bằng nguồn của người chạy.
Kết quả ngày 11/10 là lịch sử của bộ gốc, không phải một lần chạy lại bộ công khai.
