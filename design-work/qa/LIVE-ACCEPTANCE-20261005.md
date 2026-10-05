# Đối soát sử dụng thật ngày 05/10/2026

## Bản đã triển khai

GitHub CI `37270629909` thành công cho mã `e894fe8a8337cdeafbe0003d8fa735dee8f8de7d`. Đọc kho ảnh công khai xác nhận digest `sha256:eb28619b8db9ad2d6ff939d547d548de8d751e36996bcd8359577e3251c61bba`. Đã cập nhật nguồn đúng ảnh đó tại dịch vụ Render hiện có; triển khai `dep-db1k2mnavr4c73cadnr0` thành công, thời gian 1 phút 50 giây, bắt đầu 13:19:06 ngày 05/10 giờ Việt Nam. Trang được tải lại sau triển khai; tài khoản quản trị vẫn đăng nhập và dùng được Chat.

Các bằng chứng dưới đây thuộc bản này; không tự chuyển thành bằng chứng của bản sửa tiếp theo.

## Drive thật

Thanh bên sử dụng phiên OAuth của người dùng, không giả lập phản hồi Google. Danh sách mặc định có tệp và thư mục, nhãn “Gần đây trước”. Chọn chỉ thư mục trả 50 thư mục ở trang đầu; thêm gắn sao còn 12 thư mục, không lẫn tài liệu/bảng tính. Chọn chỉ tệp cùng gắn sao không có thư mục; bảng có 13 hàng gồm hàng tiêu đề. Bỏ gắn sao vẫn chỉ có tệp. Trả lại mặc định Tất cả và không gắn sao; sau triển khai, đọc lại danh sách thành công.

Ảnh giao diện được xem trực tiếp qua công cụ thanh bên: tìm kiếm/bộ lọc theo cùng giao diện tối. Chưa đối chiếu thời gian Google của từng mục để chứng nhận toàn bộ thứ tự gần đây; chưa đóng toàn bộ E04/E05. Công cụ đo DOM không phản hồi (`Page.getFrameTree` timeout), nên không chứng nhận đầy đủ kích thước, tràn ngang, lỗi mạng hoặc console bằng lượt này. Không ghi ảnh chứa tên tài liệu riêng vào Git.

## Hội thoại ba lượt bằng dữ liệu giả lập

Không gửi nội dung Gmail/Drive cho mô hình. Cấm đọc nguồn ngoài và bộ nhớ dài hạn; không tạo tài liệu Google. Khách hàng và số liệu trong ba câu hỏi đều giả lập.

| Ca | Kỳ vọng | Kết quả thực tế | Kết luận |
|---|---|---|---|
| Lượt 1 | Ba dòng: Minh Phát, 10 giờ 08/10/2026 giờ Việt Nam, tăng từ 100 lên 120 triệu với phép tính | Đúng khách hàng/hạn, 20 triệu và 20%; có công cụ calculate; thiếu phép tính trong câu trả lời. 25,9 giây | KHÔNG ĐẠT đầy đủ yêu cầu trình bày |
| Lượt 2 | Đổi riêng kỳ này thành 130 triệu, giữ khách hàng/hạn/ba dòng; ghi biểu thức phần trăm | Đúng cả ba dòng và `(130 - 100) / 100 * 100 = 30.0%`. 17,2 giây | ĐẠT ca hỏi tiếp này |
| Lượt 3 | Nhắc lại dữ kiện mới, không tính lại; tải lại trang khi đang chạy, không mất hoặc gửi trùng câu hỏi | Phục hồi đúng phiên đang xử lý; kết quả Minh Phát, đúng hạn, 130 triệu; mỗi lượt có một câu hỏi và một câu trả lời; không có công cụ trong dấu vết lượt cuối | ĐẠT ca tải lại này |

Lượt 3: mã yêu cầu `7a9f6a25-534c-43cb-b2f0-3bcbe7d239a7`, mô hình thực dùng `gemini-3.5-flash-lite`, 5.267 token đầu vào và 47 đầu ra, thời gian lời gọi mô hình 8.894 ms. Đây không phải thời gian toàn tác vụ. Ngân sách ứng dụng từ 13 còn 8 lượt sau ba câu hỏi; không đặt lại bộ đếm, không gọi đây là số dư Google. Dấu vết lượt đầu có calculate; lượt cuối không đọc hoặc ghi thêm nguồn.

Đây là một chuỗi kiểm ngữ cảnh/phục hồi bổ sung, không thay 24 tác vụ, 12 ca ngữ cảnh và 6 ca bộ nhớ dài hạn bắt buộc. Chưa có điểm tổng đủ nhóm.

## Phát hiện còn phải sửa và kiểm lại

- Sau ba lượt thật, bảng ADK cũ tăng từ 26 phiên/212 sự kiện lên 27 phiên/222 sự kiện, trong khi không có bảng ADK ở `veridra_private`. Cấu hình search_path trong URL đã không có tác dụng trên đường kết nối cloud này. Quyền đọc API các bảng cũ vẫn bị khóa. Đang bổ sung schema rõ trong câu SQL và đặt search_path theo từng giao dịch; không chuyển/xóa hàng cũ. Phải kiểm PostgreSQL thật và chạy lại sau triển khai để chứng nhận.
- Bộ xuất số đo trước sửa lấy giá mặc định 0 và có thể xuất chi phí 0 khi không biết giá. Đang sửa: giá không có là chưa định giá, chỉ xuất ước tính khi có cả hai giá và đủ dữ liệu token của mọi lượt được tính. Giá 0 chỉ hợp lệ khi được cấu hình rõ. Phép thử local không thay bằng chứng phiên bản cloud mới.
- Render Free hiển thị giới hạn 512 MB và 0,15 CPU, nhưng trang số đo yêu cầu gói trả phí để xem mức sử dụng. Đây là giới hạn cấu hình, không phải mức RAM/CPU đã đo. Không nâng gói để lấy bằng chứng.

## Công cụ và giới hạn

Đã dùng thao tác thật trong trình duyệt thanh bên để lọc Drive, cập nhật nguồn ảnh Render, xem kết quả triển khai và gửi/đọc Chat. Supabase chỉ đọc quyền, số hàng, danh sách bảng và phiên bản di trú, không xuất nội dung hội thoại. Kiểm mã local toàn bộ trước lượt này: 1.068 đạt, 15 không chạy; GitHub đã kiểm PostgreSQL thật của bản e894fe8.

Các mục còn chặn gồm bộ nghiệp vụ đủ mẫu, luồng đầu ngày/trước hẹn/duyệt và đọc lại, bộ nhớ đầy đủ, tốc độ khởi động/tài nguyên, khôi phục độc lập, bốn người thật và cùng phiên bản cuối. Không gộp nhánh chính hoặc tuyên bố sẵn sàng phát hành từ các kết quả thành phần ở trên.
