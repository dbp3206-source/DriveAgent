# Kiểm lại linh vật đồng hành — 15/10/2026

## Kết luận và phạm vi
Yêu cầu thông báo kết quả Chat và tương tác hữu ích đã có trong mã hiện tại, không cần triển khai trùng. Lượt này kiểm lại trên mã `ed3fa6a38b093d7aeda517df03c88cbd16880cd7`; không sửa mã sản phẩm, không triển khai Render, không gọi Gemini hoặc tạo chỉ mục. Dùng hệ thống thiết kế Veridra hiện có, không dùng trình tạo ảnh hay thiết kế lại giao diện.

Nguồn: `frontend/src/components/MascotAssistant.tsx`, `frontend/src/hooks/useChatActivity.ts`, `frontend/src/chatActivity.mjs`, `frontend/src/App.tsx`, `frontend/src/pages/ChatPage.tsx` và helper QA cô lập `design-work/production-20261013/working/run_local_ui.py --mascot-check`. Không có kỹ năng tạo hình được sử dụng; kiểm trình duyệt bằng Chrome DevTools MCP thật, lưu nguyên byte ảnh bằng node_repl.

## Kết quả thực thi
- `npm test`: **219/219 đạt**, 0 bỏ qua, 11.011 giây; đây là tổng bộ kiểm frontend, không phải 219 ca riêng cho linh vật. `npm run lint`: exit 0. Không dựng lại vì không sửa mã sản phẩm trong lượt này.
- Trình duyệt thật, tài khoản demo cô lập tại `127.0.0.1:5175`, máy chủ QA tại `127.0.0.1:8003`. Profile không có khóa Gemini/OAuth, chặn kết nối ngoài. Helper trì hoãn tác vụ 12 giây để kiểm việc chuyển trang; đây là giả lập thời gian xử lý, không phải phép đo tốc độ hoặc chất lượng Gemini.
- Nhập `QA mascot: Tính 4.5 + 5.5 bằng bao nhiêu?`, gửi và chuyển Bắt đầu. Quan sát trạng thái đang xử lý, sau đó linh vật báo **Có câu trả lời mới**, thanh đầu trang và tên tab cùng cập nhật.
- Đóng bong bóng: thông báo ẩn nhưng dấu **1** còn nguyên, không tự đánh dấu đã đọc.
- Giả lập màn hình điện thoại thật qua DevTools `390x844x1,mobile,touch`. Việc giả lập tải lại trang: thông báo chưa đọc được khôi phục. DOM xác nhận innerWidth=390, innerHeight=844, scrollWidth=390; bong bóng left=68.40, right=378.40, top=558.50, bottom=758.40, nằm trong khung.
- Bấm **Xem câu trả lời**: mở đúng hội thoại với câu hỏi trên và đáp án **10.0**, dấu chưa đọc được xóa. Metadata thông báo chỉ có ownerId/taskId/sessionId/phase/unread; không chứa câu hỏi, câu trả lời hoặc khóa.
- Mở lại linh vật, bấm **Cần mình hỗ trợ?**: có hướng dẫn ngắn đúng ngữ cảnh Chat, nút Trò chuyện/Chọn tài liệu. Mở bộ chọn có sáu nhân vật; chọn **Cú**, nhãn và lựa chọn trên thiết bị cập nhật đúng. Không tự gửi câu hỏi hoặc thực hiện hành động Google.
- Console error sau luồng chính và mở bộ chọn: không có thông báo lỗi. Không dùng kết quả này để phủ nhận lỗi của tiến trình khởi động trùng cổng bên dưới.

## Bằng chứng
- `screenshots/desktop-completed.jpg`: ảnh gốc từ công cụ, DOM viewport 1536×682; không suy kích thước viewport từ số pixel ảnh chụp.
- `screenshots/mobile-completed.jpg`: viewport 390×844, ảnh gốc từ công cụ.
- Hai ảnh chỉ chứa dữ liệu giả lập. Không sửa, vẽ lại hoặc ghép ảnh. Mã băm trong run-manifest.json.
- Kiểm URL Render ngày 14/10 nằm trong báo cáo QA cha; **không được hiểu là kiểm cloud mới ngày 15/10**.

## Sự cố công cụ và cách xử lý
Kiểm cổng bằng Get-NetTCPConnection không trả danh sách trong môi trường này. Khởi động Vite/QA gặp cổng 5175/8003 đang dùng. Đối chiếu netstat và session QA đã biết: giữ Vite hiện có; dừng đúng backend QA sở hữu từ lượt trước qua session 35024, sau đó chạy helper với cờ mascot. Không dừng tiến trình người dùng, không đổi mã sản phẩm để khắc phục lỗi cổng. Backend thử trùng cổng tự thoát, không được tính là lần khởi động đạt.

## Giới hạn và chất lượng
Giữ đánh giá phạm vi tính năng **86/100** của báo cáo cha; không cộng điểm vì kiểm lại, không phải điểm Production toàn sản phẩm. Trạng thái lỗi/bản nháp, tắt linh vật và ranh giới tài khoản có bộ kiểm tự động và bằng chứng trước đó; không lặp lại đầy đủ trên cloud trong lượt này. Chưa giả lập tùy chọn giảm chuyển động hệ điều hành trong lượt này. Chỉ hoạt động khi ứng dụng còn mở hoặc mở lại để lấy trạng thái; không phải thông báo đẩy khi đã đóng trình duyệt. Hiện theo dõi một tác vụ đang chạy. Không thêm tài sản hoặc dependency; tiếp tục dùng sprites hiện có, Fluent icons và page-mascot.
