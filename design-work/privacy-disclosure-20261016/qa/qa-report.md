# Kiểm tra thông báo dữ liệu Veridra — 16/10/2026

## Kết quả

**Mã và giao diện cục bộ: đạt. Phát hành ra URL: chưa làm trong lượt kiểm này.** Đây là nghiệm thu riêng cho thông báo dữ liệu, không phải xác nhận toàn bộ Veridra đã sẵn sàng sản xuất. Không dùng Gemini, không đọc Gmail/Drive thật và không gửi nội dung thật tới dịch vụ ngoài.

Phần bổ sung đưa thông tin đến đúng lúc: trước khi cấp quyền Google, trong khung trò chuyện và tại trang tài liệu đã nhập. Trang `/privacy.html` giải thích dữ liệu được xử lý ở đâu, nguy cơ của hạn mức Gemini miễn phí, mốc 30 ngày có xác nhận, giới hạn xóa và kênh liên hệ. Liên kết mở được cả từ chân trang trong ứng dụng.

## Phạm vi và căn cứ

- Giao diện theo Fluent UI và màu sắc hiện có; không thay đổi cách gọi Gemini, OAuth, lưu trữ hoặc dọn dữ liệu.
- Nguồn sự thật trong sản phẩm: `docs/DATA-USE.md`, `docs/DATA-RETENTION-20261015.md`, mã hiện hành và trang `frontend/public/privacy.html`.
- Điều khoản Google Gemini API: https://ai.google.dev/gemini-api/terms
- Chính sách dữ liệu Google API: https://developers.google.com/terms/api-services-user-data-policy
- Google nêu điều kiện khác nhau giữa hạn mức trả phí và miễn phí; thông báo vì thế không khẳng định mọi khóa đều được xử lý như nhau. Veridra hiện không xác minh trạng thái thanh toán của khóa. Đây là thông báo sử dụng cho bản thử nghiệm kín, không phải tư vấn pháp lý hay chứng nhận tuân thủ.

## Kiểm tra đã chạy

| Kiểm tra | Kết quả | Bằng chứng/giới hạn |
|---|---|---|
| Frontend unit | **224 đạt, 0 lỗi, 0 bỏ qua** | `npm run test:unit`; gồm kiểm nội dung trang công khai và vị trí cảnh báo trước chat/ủy quyền Google. |
| Lint | **Đạt** | `npm run lint`, mã thoát 0, không cảnh báo/lỗi. |
| Bản dựng | **Đạt** | `npm run build`, `tsc -b` và Vite hoàn tất; `frontend/public/privacy.html` được đưa vào `dist/privacy.html`. |
| Kiểm trình duyệt tự động | **Đạt** | `node scripts/privacy-ui-smoke.mjs`; Chrome/Playwright, API giả lập cục bộ, trò chuyện tối 1440×1000, sáng 390×844, màn thiết lập chưa đăng nhập và trang tài liệu đã nhập; kiểm liên kết, tràn ngang, vùng chồng mascot và lỗi JavaScript. `browserErrors: []`. |
| Trang công khai trên bản dựng | **Đạt cục bộ** | HTTP `200`, tiêu đề đúng; chụp toàn trang ở 1440×1200 và 390×844. |
| Kiểm mã định dạng | **Đạt** | `git diff --check`, không phát hiện lỗi khoảng trắng. |
| Dịch vụ thật / dữ liệu thật | **Không gọi** | Không đăng nhập Google, không gọi Gemini/Tavily, không đọc Gmail/Drive/lịch, không xóa/ghi dữ liệu thật. |
| CI / main / Render | **Chưa xác minh** | Bản sửa chưa được đẩy lên `main` hoặc triển khai; URL công khai vẫn cần xác nhận sau phát hành. |

## Kiểm tra hiển thị

- `screenshots/setup-data-notice-desktop.png`: cảnh báo xuất hiện trước bước cấp quyền.
- `screenshots/chat-desktop-dark.png`: nội dung còn đọc được khi mascot mở rộng; bản đầu phát hiện phần cảnh báo bị mascot che. Đã giới hạn chiều rộng cảnh báo và chạy lại bài kiểm chồng lấp.
- `screenshots/chat-mobile-light.png`: cảnh báo hiển thị trong khung trò chuyện trên màn nhỏ, không tràn ngang.
- `screenshots/local-sources-data-notice-desktop.png`: nhắc hạn mức miễn phí tại nơi tải tài liệu lên.
- `screenshots/privacy-desktop.png`, `screenshots/privacy-mobile.png`: trang thông tin công khai ở hai cỡ màn hình.

Ảnh là ảnh chụp từ Chrome chạy bản dựng cục bộ với dữ liệu giả lập; không phải ảnh bằng chứng của URL Render.

## Phát hiện và xử lý

1. Cảnh báo ban đầu bị mascot phủ một phần ở màn hình rộng. Đã dành vùng ngang cho cảnh báo khi mascot mở và thêm khẳng định hình học vào bài kiểm trình duyệt.
2. Lần chạy đầu của smoke test thất bại do kiểm thử đòi đúng cụm “không gửi”, còn giao diện dùng cách nói tự nhiên “đừng gửi”. Đã sửa biểu thức kiểm để xác nhận đúng nội dung thực tế; chạy lại đạt. Không thay đổi hành vi sản phẩm vì sai khác này.

## Điểm chất lượng phần thông báo: 87/100

| Tiêu chí | Điểm | Lý do |
|---|---:|---|
| Đúng nội dung và căn cứ | 19/20 | Phân biệt hạn mức miễn phí, không tuyên bố ẩn danh hoặc xóa tuyệt đối; còn chờ rà soát pháp lý. |
| Phù hợp người dùng và tình huống | 18/20 | Cảnh báo hiện trước ủy quyền, trước gửi chat và ngay trang tài liệu. |
| Bố cục thông tin | 14/15 | Trang chi tiết chia theo dữ liệu, nơi nhận, lưu/xóa, quyền và liên hệ. |
| Chữ và khả năng đọc | 13/15 | Tiếng Việt ngắn ở điểm thao tác; trang giải thích dài nhưng chia mục và xem được trên điện thoại. |
| Bố cục/nhận diện | 13/15 | Theo Fluent UI hiện có, có cảnh báo nổi bật, không dựng lại giao diện. |
| Hoàn thiện kỹ thuật | 10/15 | Unit, lint, build và Chrome cục bộ đạt; chưa có CI, xác minh URL Render hoặc rà soát pháp lý. |
| **Tổng** | **87/100** | Đạt ngưỡng nội bộ 80 cho lát cắt này; chưa phải cổng phát hành. |

## Còn lại trước khi coi phần này đã phát hành

1. Đưa thay đổi lên `main` và chờ CI đúng commit.
2. Triển khai ảnh mới lên Render, xác nhận `/privacy.html` mở công khai và kiểm lại liên kết/cảnh báo trên URL thật.
3. Chủ sản phẩm rà soát tên đơn vị vận hành, kênh yêu cầu xóa và nội dung pháp lý trước khi nhận dữ liệu cá nhân hoặc mở beta rộng. Hiện trang ghi quản trị viên/email đã cung cấp; chưa có đơn vị pháp lý được xác nhận.

## Giới hạn quan trọng

- Người dùng có thể trì hoãn hoặc không xác nhận dọn dữ liệu sau 30 ngày; khi đó dữ liệu Veridra còn lâu hơn. Đây không phải cơ chế tự xóa tuyệt đối theo hạn cứng.
- Tác vụ dọn Veridra không xóa bản gốc trên Google, bản người dùng tải về hoặc bản sao của nhà cung cấp khác.
- Không tuyên bố nội dung được ẩn danh. Không gửi thông tin cá nhân, nhạy cảm hoặc bí mật qua khóa Gemini dùng hạn mức miễn phí.
- Bài kiểm này chỉ chứng minh nội dung và bố cục của màn hình liên quan; không nghiệm thu quyền truy cập, độ bền dữ liệu, chất lượng câu trả lời, an ninh toàn hệ thống hay trạng thái production-ready của sản phẩm.
