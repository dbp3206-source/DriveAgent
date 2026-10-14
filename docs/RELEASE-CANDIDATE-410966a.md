# Bản ứng viên 410966a — bằng chứng triển khai

Ngày 13/10/2026. Trạng thái: **đã qua CI và Live để kiểm nghiệm, chưa nghiệm thu Production**. Không thay main trước khi đủ điều kiện phát hành đã khóa.

## Mã và môi trường khớp

- Commit: `410966a45887a56f4b002e17c6411acca4276170`.
- Nhánh: `staging/internal-assistant-20261013`; đã đẩy thành công, checkout sạch ngay sau đẩy. Tài liệu/bằng chứng vận hành phát sinh sau đó được giữ để đóng hồ sơ cuối.
- [CI #136](https://github.com/dbp3206-source/DriveAgent/actions/runs/38346595038): Success, tổng 5 phút 34 giây. PostgreSQL 34 giây; verify 4 phút 55 giây.
- [Kiểm PostgreSQL thực](https://github.com/dbp3206-source/DriveAgent/actions/runs/38346595038/job/115129353179) và [kiểm/dựng ảnh](https://github.com/dbp3206-source/DriveAgent/actions/runs/38346595038/job/115129500550) đều thành công. Chưa tải được XML từ giao diện do đường tải hết giờ; không tự ghi số ca/độ phủ CI chưa đọc được từ nhật ký.
- Ảnh công khai đã đọc bằng Registry HEAD, HTTP 200: `ghcr.io/dbp3206-source/veridra@sha256:1b427bd6536f2695b65e955afaa3d01276d9afbd7b8eade0dc34c8baba0f03ff`. Đây là mã băm ảnh, không phải mã băm tệp đính kèm GitHub Actions.
- [Render deploy](https://dashboard.render.com/web/srv-dav5v560tbcc73dpjlc0/deploys/dep-db6rbqek1f9s73b8upb0): nguồn `1b427bd`, trigger Image updated, Deploy succeeded/Live. Khởi động ứng dụng hoàn tất 11:40:51; Live 11:41:01 GMT+7. Không đổi gói Free hoặc đọc/chỉnh biến bí mật.
- [URL sản phẩm](https://veridra-closed-beta.onrender.com/). Đã tải lại và xác nhận cookie trước nâng cấp phải đăng nhập lại; không suy ra chất lượng đầu ra từ việc trang mở được.

## DB và môi trường khôi phục

Chỉ truy vấn số liệu cấu trúc, không xuất nội dung riêng:

| Quan sát | Trước triển khai | Sau triển khai |
|---|---|---|
| Schema nguồn | 5 | 6 |
| Cột `users.auth_version` | Chưa có | Có |
| Số tài khoản | 1 | 1 |
| Tệp Storage | 5 | 5 |

Số lượng giữ nguyên không tự chứng minh mọi nội dung/mã băm đã khớp; phần khôi phục vẫn chưa đạt.

Đích thử `scsxkanbmtexylgbrsla` thuộc tổ chức Veridra, plan `free`, đã hoạt động lại từ trạng thái INACTIVE qua COMING_UP tới ACTIVE_HEALTHY. Đối chiếu đích: 0 bảng ứng dụng, 0 kho, 0 tệp; khác nguồn `ltvzdrvjmljvrnhwxade`. Đây chỉ là bật lại đích cũ đã được phép, **chưa sao lưu/khôi phục dữ liệu**. Không tạo project/nâng gói hoặc ghi đè nguồn.

## Đợt kiểm được duyệt tiếp theo

Chủ sở hữu đồng ý tối đa **11 yêu cầu sinh câu trả lời** (gồm hai dự phòng) và **8 yêu cầu tạo chỉ mục**, tổng **19 yêu cầu Gemini thực**, chỉ bốn tệp giả lập A/B/C và web công khai; đúng một Doc giả lập sau xem trước/duyệt. Tính cả gọi thêm/thử lại; không đọc thêm nội dung riêng, gửi thư/sửa lịch, đặt lại bộ đếm hoặc nâng gói. Đến khi chốt bộ dữ liệu `.2` chưa dùng yêu cầu nào cho bộ mới.

Khóa chưa bật thanh toán đã được chủ sở hữu xác nhận. Điều kiện dữ liệu thật chưa đóng; xem `DATA-USE.md`. Không tự gọi dữ liệu doanh nghiệp thật để đủ tiêu chí.

Chủ sở hữu đã hoàn tất đăng nhập lại; giao diện Bắt đầu mới được quan sát trực tiếp trong thanh bên. Không nhập mật khẩu, khóa hoặc mã xác nhận, không mở rộng quyền để vượt bước này.

## Bằng chứng và việc còn phải giữ đúng

- Hồ sơ kiểm tại máy và ảnh: `design-work/production-20261013/qa/qa-report.md`; ảnh CI/Render mới: `ci-success-410966a.jpg`, `render-live-410966a.jpg` trong cùng thư mục screenshots.
- Nguồn Git và phiên bản CI/ảnh/URL đã đối chiếu; main/thẻ phát hành/biên bản vẫn chưa đóng.
- T01–T10 chưa có kết quả tích hợp đầy đủ của bản này; bộ nhớ xóa/truy xuất mới, một Doc, cách ly thật, khôi phục DB+tệp, đo vận hành và điều kiện dữ liệu còn cần bằng chứng tương ứng.
- Phần “Cách Agent hoạt động” vẫn chưa sửa, đúng yêu cầu làm cuối và nhận góp ý của người dùng.

Không nhầm CI xanh, migration thành công hoặc đích khôi phục hoạt động với nghiệm thu toàn bộ sản phẩm.
