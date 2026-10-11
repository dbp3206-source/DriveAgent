# Kiểm tra hồ sơ công khai ngày 11/10/2026

## Phạm vi

Chỉ tài liệu, dữ liệu giả lập và biên nhận đã loại dữ liệu riêng. Không sửa mã ứng
dụng, lược đồ dữ liệu, cấu hình triển khai, khóa, hạn mức hoặc giấy phép dự án.
Không gửi thêm câu hỏi tới mô hình hay gọi dịch vụ Google. Không công khai bản
Word, ảnh gốc, dữ liệu nhật ký thô hoặc URL tài liệu riêng.

## Các kiểm đã thực hiện

| Kiểm | Kết quả |
|---|---|
| Bộ hồi quy hiện có qua `scripts/evaluate_release_offline.py` | 200/200 đạt; biên nhận giữ riêng phạm vi không gọi mô hình |
| 10 tệp kiểm về bảo mật, kiểm soát hành động và hợp đồng nghiệp vụ qua pytest | 78/78 đạt, 0 lỗi, 0 bỏ qua; thời gian trong JUnit là 31,033 giây |
| JSON của hồ sơ mới | Đọc được; bộ demo có đúng 10 ca |
| Ma trận kiểm | 15 ánh xạ đến tệp/selector có thật, không đếm thành 15 kiểm độc lập mới |
| Mã băm bộ dữ liệu | 9 tệp khớp SHA-256 trong manifest |
| Đáp án số học | Đối chiếu độc lập GD01 bằng số thập phân chính xác và GD02 bằng số nguyên |
| Liên kết nội bộ Markdown ở các tài liệu thêm/sửa | Đích tồn tại trong kho |
| Kiểm riêng dữ liệu công khai | Không có email tài khoản quản trị, URL Google Doc riêng, định danh yêu cầu hoặc khóa trong hồ sơ mới |
| `scripts/scan_release_secrets.py` | Thành công cho tập tệp Git nhìn thấy và lịch sử theo phạm vi của công cụ |

Lần kiểm phép tính đầu dùng số thực nhị phân và báo sai khi so sánh chính xác
19,2. Đã đổi riêng phép kiểm bằng PowerShell sang số thập phân và đối chiếu lại
thành công; không thay đáp án chuẩn hoặc mã sản phẩm để khớp kết quả.

## Giới hạn kiểm tra

- Git có cảnh báo không đọc được một số thư mục kiểm thử tạm cũ. Không đưa chúng
  vào thay đổi; không tuyên bố đã quét mọi tệp trên ổ đĩa. Chỉ đưa các đường dẫn
  tài liệu được chỉ định vào bản cập nhật.
- Quét mẫu bí mật không chứng minh không còn mọi dạng thông tin riêng. Hồ sơ mới
  còn được rà theo trường: bỏ mã yêu cầu, URL Doc, tên ảnh và bản gốc riêng; chỉ
  giữ nội dung đánh giá cần thiết. Không sao chép ảnh tài khoản.
- Không chạy lại 10 ca web để làm hồ sơ; kết quả ngày 11/10 là bằng chứng lịch sử.
- Không lấy kiểm mã hoặc phép kiểm nội bộ thay cho nghiệm thu vận hành, nhiều
  tài khoản, khôi phục, chống mọi tấn công hoặc chất lượng mô hình chạy thật.
- Liên kết tới tài liệu cũ không có nghĩa đã kiểm lại mọi phát biểu lịch sử.

## Quyền và giấy phép

GD01–GD05 là dữ liệu giả lập được tạo cho bộ kiểm của dự án. Không chép tệp PDF
riêng, nội dung thư thật hoặc mã thư viện vào bộ này. Bộ nguồn ngoài kho của Gate 2
vẫn cần đúng tệp và quyền sử dụng. Kho chưa có giấy phép cấp dự án; không tự chọn
giấy phép thay chủ dự án trong đợt đóng gói hồ sơ.
