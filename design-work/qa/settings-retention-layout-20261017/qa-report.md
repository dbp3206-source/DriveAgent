# Kiểm hồi quy bố cục phần lưu giữ — 17/10/2026

## Kết luận

Đã tìm được nguyên nhân của lỗi thấy trực tiếp trên trang Cài đặt bản đang chạy: lưới có 12 cột, phần trạng thái hệ thống chiếm 8 cột, nhưng thẻ “Thời hạn lưu giữ” không được chỉ định vị trí. Trình duyệt tự đặt thẻ vào 4 cột còn trống. Tiêu đề bên trong lại cần tối thiểu 180 + 260 px, nên nội dung tràn khỏi thẻ và làm xuất hiện thanh cuộn ngang.

Đã sửa đúng bố cục: thẻ lưu giữ chiếm toàn hàng, nằm dưới trạng thái hệ thống. Không đổi nội dung, thao tác, màu sắc hay thiết kế các phần khác.

Ứng viên `d76f2e6` đã lên `main`; GitHub Actions [CI #154](https://github.com/dbp3206-source/DriveAgent/actions/runs/39022598365) thành công trong 6m13s. Ảnh đã kiểm chứng có mã `ghcr.io/dbp3206-source/veridra@sha256:8b2c74ed27062a2e88888db3d8fdc16972e26633760b88bbe0f5d68b28a26978`. Render deploy [dep-db9kcvrncjis739ls3ng](https://dashboard.render.com/web/srv-dav5v560tbcc73dpjlc0/deploys/dep-db9kcvrncjis739ls3ng) báo **Live** với đúng digest đó.

## Kiểm tra

- Trình duyệt thật trên URL trước sửa: ảnh và cây truy cập cho thấy thẻ bị ép hẹp và nội dung tràn. Không đọc hoặc thay đổi dữ liệu tài khoản.
- Sau triển khai, `/api/health` trả `status: ok`, cơ sở dữ liệu và kho tệp đều hoạt động; thời điểm khởi động khớp với deploy mới. Trang Cài đặt đang chạy được mở lại, thẻ lưu giữ hiển thị toàn chiều ngang dưới phần hệ thống và không tràn khung.
- Kiểm hồi quy bằng Chrome với CSS thật của sản phẩm và nội dung giả lập: 1280×900 và 390×844, cả sáng/tối. Cả 4 trường hợp đều đặt thẻ toàn hàng sau trạng thái hệ thống, không tràn ngang.
- Frontend: 224 bài đạt; ESLint đạt; bản dựng production đạt.
- Backend lưu giữ cô lập: 221 bài đạt, 1 bài bỏ qua; không dùng dữ liệu cloud, Gemini hoặc Google.
- Ảnh giao diện tổng hợp giả lập: `desktop-light.png`, `desktop-dark.png`, `mobile-light.png`, `mobile-dark.png`. Báo cáo số đo của kiểm hồi quy: `report.json`. Ảnh live chỉ được quan sát trong phiên trình duyệt; không lưu lại vì ảnh toàn trang Cài đặt có thông tin tài khoản/khóa.

## Chấm điểm cho phạm vi sửa này

| Tiêu chí | Điểm | Căn cứ |
|---|---:|---|
| Đúng nội dung và yêu cầu | 20/20 | Chỉ sửa vị trí thẻ; không đổi hành vi lưu giữ |
| Hợp giao diện hiện có | 18/20 | Giữ nguyên hệ thống màu và thành phần; không mở rộng thiết kế |
| Bố cục và cấu trúc | 13/15 | Thẻ đúng thứ tự, chiếm đủ hàng; đây là sửa hẹp, không phải thiết kế lại |
| Chữ và khả năng đọc | 15/15 | Giữ nguyên kiểu chữ, kiểm bằng 4 kích thước/sáng-tối |
| Khoảng cách và phân cấp | 15/15 | Thứ tự hệ thống → lưu giữ → phần tiếp theo được giữ rõ |
| Hoàn thiện kỹ thuật và xác minh | 14/15 | CI, deploy và URL đều xác minh; ảnh live không lưu riêng để tránh lộ thông tin tài khoản |
| **Tổng** | **95/100** | Chỉ đánh giá thay đổi bố cục này, không phải điểm nghiệm thu toàn sản phẩm |

## Giới hạn

Kiểm khôi phục DB/tệp vẫn được chủ sở hữu cho miễn, nên chưa được ghi là đạt. Đây là nghiệm thu lỗi bố cục đã khoanh vùng, không đồng nghĩa toàn bộ sản phẩm đã đạt Production.

## Công cụ và tài sản

- Dùng hệ thống CSS hiện có của Veridra; không thêm thư viện hoặc ảnh bên ngoài.
- Dùng Playwright với Chrome cài sẵn cho ca tổng hợp. Lượt đầu dùng cấu hình Chromium riêng nhưng trình duyệt đó không được cài; chuyển sang Chrome theo lệnh kiểm thử đã có trong repo.
- Dùng kỹ năng `render-monitor` (đọc từ `C:\Users\Bao Phuc\.codex\plugins\cache\openai-curated-remote\app-6a624c56bfe081918f7544f7d58f6faf\1.0.1\skills\render-monitor\SKILL.md`) cùng Render MCP để xác nhận dịch vụ, deploy và health; dùng CUA để kiểm tra trực quan URL sau deploy.
- Screenshot chỉ chứa nhãn giả lập; không chứa email, khóa, thư, tài liệu hoặc dữ liệu tài khoản.
