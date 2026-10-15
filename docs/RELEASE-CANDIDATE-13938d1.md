# Ứng viên 13938d1 — phần giải thích đã duyệt

Ngày 15/10/2026. Đã triển khai và kiểm trên URL thật. Chỉ thay phần trình bày và nhãn điều hướng, giữ ảnh người dùng và kỹ thuật nâng cao. Không đổi máy chủ, dữ liệu, quyền, hạn mức hoặc tích hợp.

## Mã và kiểm tự động

- Mã nguồn: `13938d158b6f1df13df01186a31b541d85ff13c1`, nhánh `staging/internal-assistant-20261013`.
- [CI #141](https://github.com/dbp3206-source/DriveAgent/actions/runs/38748183372): cả `postgres-state` và `verify` thành công. Đọc kết quả qua kết nối GitHub, không lấy việc đẩy mã thay kết quả kiểm.
- Phía máy chủ: 1.631 đạt, 14 bỏ qua, 92,91 giây, độ phủ 88,07%. Giao diện: 222 đạt, không lỗi hoặc bỏ qua. Các nhóm chồng lặp không cộng thành điểm sản phẩm. PostgreSQL có nhóm kiểm riêng đã thành công.
- Kiểm ngoại tuyến, toàn vẹn bộ chuẩn, quét bí mật, kiểm mã, dựng gói, khởi động và PDF tiếng Việt đều thành công. Bước triển khai tự động **bị bỏ qua**, không tính là đã triển khai.
- Ảnh phát hành từ đúng mã: `ghcr.io/dbp3206-source/veridra@sha256:0169c264a134bba62381d207785a3a7b4aaac611acdb1768b2e9208d377c1712`. Nhật ký phát hành ghi cùng mã băm cho mã nguồn 13938d1 và nhánh nghiệm thu.

## Nội dung và bằng chứng giao diện

Bốn bước: Hiểu việc → Chọn nguồn → Đưa kết quả → Duyệt và bàn giao. Chọn một trong ba ví dụ; phần kỹ thuật đóng và chưa dựng nội dung ban đầu; các liên kết lĩnh vực/bước cũ tự mở đúng phần. Giữ nguyên PNG 1672×941 cùng cảnh báo số minh họa. Đã kiểm ứng dụng thật cô lập tại máy ở 1440×1000, 820×900 và 390×844: bàn phím, ảnh và không tràn ngang. Không dùng thêm Gemini, tạo chỉ mục hoặc Google Doc. [Hồ sơ QA](../design-work/agent-explanation-20261015/qa/qa-report.md).

## Theo dõi Render

Đã gửi đúng một yêu cầu cập nhật nguồn ảnh qua thanh bên, không đổi biến môi trường, gói, quyền hoặc DB. Lần triển khai [`dep-db8dvrqj9qps73cj7d5g`](https://dashboard.render.com/web/srv-dav5v560tbcc73dpjlc0/deploys/dep-db8dvrqj9qps73cj7d5g) đã **Live**: tạo lúc 14:15:11.807 UTC, bắt đầu 14:15:16.936, hoàn tất 14:17:07.150 (21:17:07 GMT+7). Thời gian tạo tới hoàn tất là 115,343 giây, không phải thời gian gián đoạn người dùng. Kết nối Render xác nhận đúng mã băm; không bấm triển khai lại khi quan sát chậm.

Đã kiểm [URL sản phẩm](https://veridra-closed-beta.onrender.com/?verify=13938d1#/harness) bằng phiên quản trị trên thanh bên: bốn bước, một ví dụ mặc định, PNG tải đúng 1672px, chi tiết không dựng ban đầu; đổi ví dụ và mở/đóng bằng Enter hoạt động. Khung 566×676 không tràn ngang; nhật ký lỗi trình duyệt tại lần kiểm trả rỗng. Tải lại URL chuẩn vẫn đóng kỹ thuật. Kiểm sức khỏe trả dịch vụ, DB và kho tệp tốt; không thăm dò Google/Gemini. [Ảnh minh chứng](../design-work/agent-explanation-20261015/qa/screenshots/cloud-13938d1-sidebar.jpg). Đóng đúng phần giao diện đã duyệt, không tự đóng mọi điều kiện Production.

Bản về trước tương thích là 7727c538/ed3fa6a. Vòng quay lui riêng 7727c538 → ac46a7a → 7727c538 đã kiểm thật trước khi triển khai ứng viên này; không lấy vòng đó thay bằng chứng triển khai bản mới hoặc khôi phục DB.

## Không tự mở rộng nghiệm thu

Chưa gộp main, tạo thẻ hoặc ký biên bản khi còn thiếu bằng chứng trong sổ 16 gói. Khôi phục DB/tệp và T09 (gồm phần hai tài khoản/phiên cloud tương ứng) được loại khỏi đợt theo quyết định chủ sở hữu, không tính đạt; giữ nguyên mã bảo vệ. Quản trị viên phụ trách vận hành, email hỗ trợ/xóa `dbp3206@gmail.com`. Loại đầu vào và nhu cầu lưu 20–30 ngày đã xác nhận, nhưng cơ chế nhắc/xác nhận xóa chưa triển khai; [điều kiện dữ liệu](DATA-USE.md) và các phần ca chưa kiểm vẫn giữ trạng thái đúng. Đo lợi ích năm cặp và dùng lặp lại mười ngày phục vụ quyết định đầu tư, không phải lý do sửa mã ngoài phạm vi. Chưa gọi trạng thái này là Production đầy đủ.
