# Content Outline

## Khung ứng dụng

- Thanh điều hướng bên trái: Trò chuyện, Google Drive, Bộ nhớ, Nhật ký, Phân quyền, Cài đặt.
- Header ngữ cảnh: tiêu đề trang, mô tả ngắn, kết nối hiện tại, theme và hồ sơ.
- Nội dung responsive: sidebar chuyển thành drawer trên màn hình nhỏ.

## Trò chuyện

- Empty state giải thích ba việc agent làm được bằng nội dung thật.
- Danh sách tin nhắn có citation mở được về đúng tệp.
- Composer có gợi ý truy vấn và trạng thái đang xử lý.
- Execution trace thu gọn: lập kế hoạch, gọi tool, truy xuất, hoàn tất hoặc phục hồi lỗi.

## Google Drive

- Thanh tìm kiếm theo tên hoặc nội dung; API hỗ trợ thêm filter MIME type.
- Danh sách có tên, loại, chủ sở hữu, thời gian sửa, trạng thái index.
- Action chính: đọc, lập chỉ mục và mở tệp gốc trên Drive.
- Preview nội dung văn bản, cảnh báo khi định dạng không hỗ trợ.

## Bộ nhớ

- Tìm kiếm semantic/keyword.
- Sáu loại FACT, PREFERENCE, CONTEXT, EPISODIC, PROCEDURAL, SUMMARY ở API và form tạo.
- Thêm, tìm, lưu trữ và xóa bộ nhớ của chính người dùng; API hỗ trợ cập nhật.
- Hiển thị loại, tag và thời gian cập nhật.

## Nhật ký

- Bảng audit theo request ID, user, role, tool, trạng thái và latency.
- Chi tiết arguments/result đã được che dữ liệu nhạy cảm.
- Bộ lọc trạng thái; API giữ đủ trường để mở rộng theo thời gian/tool.

## Phân quyền

- Ma trận vai trò và quyền tool.
- Danh sách người dùng dành cho super admin.
- Trạng thái phạm vi OAuth tách riêng khỏi vai trò ứng dụng.

## Cài đặt và onboarding

- Kiểm tra Gemini API key, OAuth client, SQLite, vector store.
- Hướng dẫn từng bước tạo OAuth client trên Google Cloud.
- Nút kết nối ở onboarding, đăng xuất phiên và health diagnostics.
