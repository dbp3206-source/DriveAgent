# Design Brief

## Audience and viewing context
Người dùng beta của Veridra, trước khi cấp quyền Google, nhập tài liệu hoặc gửi câu hỏi trong giao diện web trên máy tính/điện thoại.

## Core message
Veridra lưu dữ liệu trên máy chủ và gửi câu hỏi cùng phần nguồn cần thiết tới Google Gemini; người dùng cần hiểu điều kiện của hạn mức miễn phí trước khi dùng dữ liệu riêng.

## Desired reaction or action
Người dùng nhận biết nơi dữ liệu được xử lý, không gửi thông tin cá nhân/nhạy cảm/bí mật qua hạn mức Gemini miễn phí, và có thể mở thông tin chi tiết trước khi tiếp tục.

## Source authority
- `docs/DATA-USE.md` và `docs/DATA-RETENTION-20261015.md` (trạng thái triển khai và giới hạn đã xác nhận).
- Mã thực tế tại `frontend/src/components/SetupGate.tsx`, `frontend/src/pages/ChatPage.tsx`, `frontend/src/pages/LocalSourcesPage.tsx`.
- [Điều khoản Gemini API](https://ai.google.dev/gemini-api/terms) và [Chính sách dữ liệu Google API](https://developers.google.com/terms/api-services-user-data-policy), đã tra cứu 16/10/2026.

## Content hierarchy
1. Câu hỏi và phần nguồn cần thiết được gửi tới Gemini.
2. Hạn mức miễn phí có thể dùng dữ liệu để cải thiện dịch vụ và có thể có người đánh giá; không gửi thông tin cá nhân/nhạy cảm/bí mật.
3. Dữ liệu đến hạn sau 30 ngày chỉ bị dọn sau khi người dùng xem và xác nhận; nếu hoãn, dữ liệu có thể lưu lâu hơn.
4. Liên kết tới trang công khai, dễ đọc, có bên nhận dữ liệu và kênh hỗ trợ.

## Visual territory
Dùng Fluent UI và token hiện có; một cảnh báo ngắn, tĩnh, dễ quét, phù hợp sáng/tối và màn hình nhỏ. Trang thông tin dùng nền sáng trung tính, chiều rộng đọc vừa phải.

## Brand and system constraints
Không đổi luồng xử lý, quyền OAuth, nhà cung cấp, lưu giữ hay dữ liệu người dùng. Không thêm JavaScript/tracking vào trang thông tin. Dùng tiếng Việt ngắn, chỉ giữ tên riêng của nhà cung cấp.

## Anti-goals
Không tuyên bố dữ liệu đã ẩn danh, không hứa xóa tuyệt đối sau đúng 30 ngày, không gọi beta là chứng nhận tuân thủ, không tạo cảm giác mã hóa làm cho việc gửi dữ liệu miễn phí trở nên an toàn.

## Output contract
Trang HTML công khai tại `/privacy.html`; cảnh báo trong màn thiết lập, trò chuyện và nhập tài liệu; mã nguồn chỉnh sửa được; kiểm thử giao diện, lint, bản dựng và trình duyệt thật. Không gửi tài liệu thật hoặc gọi Gemini.

## Reference interpretation
Không có ảnh tham chiếu cần sao chép. Giữ đúng thiết kế Fluent UI hiện hữu và ưu tiên một cảnh báo nội dung gọn thay vì tạo màn hình marketing mới.
