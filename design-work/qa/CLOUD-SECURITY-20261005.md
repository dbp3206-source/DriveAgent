# Kiểm quyền dữ liệu cloud ngày 05/10/2026

## Phạm vi và phát hiện

Kiểm trực tiếp bằng công cụ Supabase trên project đang phục vụ Veridra. Chỉ đọc cấu hình, quyền và số hàng; không đọc nội dung thư, hội thoại hoặc khóa. Năm bảng điều phối cũ trong schema `public` có dữ liệu, chưa bật bảo vệ từng hàng và cho vai trò `anon` / `authenticated` đọc: `adk_internal_metadata`, `app_states`, `user_states`, `sessions`, `events`. Đây là lỗi quyền truy cập nghiêm trọng, không được bỏ qua bằng điểm chất lượng.

Không có bằng chứng ở lượt này để kết luận dữ liệu chưa từng bị truy cập. Không xóa bảng, chuyển lịch sử hoặc đặt lại bộ đếm.

## Sửa trên hệ thống đang chạy

Đã áp dụng di trú Supabase `protect_legacy_adk_public_tables`: giới hạn chờ khóa 5 giây, bật bảo vệ từng hàng và thu hồi mọi quyền bảng của `PUBLIC`, `anon`, `authenticated` trên đúng năm bảng, có kiểm tra bảng/vai trò tồn tại. Giữ quyền chủ sở hữu `postgres`; không bật ép bảo vệ đối với chủ sở hữu.

Kiểm trực tiếp sau sửa: cả năm bảng bật bảo vệ; quyền đọc của hai vai trò API đều `false`. Số hàng trước/sau không đổi: metadata 1, trạng thái ứng dụng 1, trạng thái người dùng 1, phiên 26, sự kiện 212. Toàn bộ bảng trong `public` không còn bảng nào cho `anon` đọc. Schema `veridra_private` không cho hai vai trò API sử dụng; kho `veridra-private` không công khai, giới hạn tệp 25 MB.

Bộ kiểm bảo mật Supabase sau sửa không còn cảnh báo mức lỗi. Còn năm thông tin “bật bảo vệ nhưng không có chính sách”: đây là chủ ý chặn toàn bộ truy cập API, không thêm chính sách đọc để làm mất thông báo. [Giải thích của Supabase](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).

Sau sửa, GET công khai `/api/health` trả 200; kết nối cơ sở dữ liệu và kho tệp đều đúng. Kiểm này không thay thao tác Chat đã đăng nhập hoặc kiểm quyền của bốn người thật.

## Chống tái phát và giới hạn

Mã nguồn bổ sung di trú PostgreSQL số 5, chỉ tác động danh sách bảng ADK cũ khi có bảng dấu hiệu. Bốn kiểm tra đơn vị mới; bổ sung phép thử PostgreSQL riêng trong CI, có giao dịch hoàn tác toàn bộ dữ liệu thử và kiểm quyền, giữ dữ liệu, chạy lại an toàn.

Lượt local: 16 phép thử đạt, 12 phép thử PostgreSQL không chạy vì không có cơ sở dữ liệu thử riêng; kiểm mã các tệp thay đổi đạt. Không dùng các phép thử bị bỏ qua làm bằng chứng đạt. Cần kết quả PostgreSQL thật trong CI trước khi đóng kiểm mã.

Hướng dẫn khôi phục đã bổ sung sao lưu cả năm bảng lịch sử cũ; chưa thực hiện khôi phục độc lập. Chưa có `pg_cron` trên project thật, nên không chứng nhận tác vụ định kỳ khi Render ngủ. Công cụ Render chưa được nạp trong lượt hiện tại; cài plugin không đồng nghĩa đã đọc được bộ nhớ, thời gian đáp ứng hoặc nhật ký Render.

## Công cụ thực sự đã chạy

- Supabase: đọc project, bảng, truy vấn quyền/số hàng, kiểm cảnh báo bảo mật, áp dụng di trú và truy vấn xác nhận.
- Python/pytest và Ruff: kiểm mã, phép thử di trú/cấu hình/bảo vệ bảng.
- PowerShell: GET trạng thái HTTPS công khai sau sửa; lần đầu bị chặn kết nối trong môi trường hạn chế, chạy lại với quyền mạng được duyệt thành công.

Chỉ phần khóa quyền năm bảng có bằng chứng hoàn thành. D1/D2 và phát hành toàn sản phẩm vẫn chưa đạt đủ.
