# Bản ứng viên ed3fa6a — 15/10/2026

**Trạng thái: CI đạt, ảnh đã xuất bản; chưa triển khai bản sửa tên tài liệu và chưa ký nghiệm thu Production.** Đây là bản thuộc gói07/T07 của kế hoạch 13/10, không thêm tính năng hoặc đổi bộ nghiệm thu. Nhánh hiện hành là `staging/internal-assistant-20261013`.

## 1. Đúng bản cần triển khai

```text
Commit: ed3fa6a38b093d7aeda517df03c88cbd16880cd7
ghcr.io/dbp3206-source/veridra@sha256:7727c538cbcb97700f7d922fddb4aea56e0839d9edaf85754dafda771cacb0bd
```

- [CI #140](https://github.com/dbp3206-source/DriveAgent/actions/runs/38694316034): API GitHub xác nhận `completed/success`, đúng commit trên; cập nhật 15/10/2026 06:51:02 UTC. Hai job `postgres-state` (116287209476) và `verify` (116287414181) đều thành công. Không suy tổng số ca CI từ số tại máy.
- Bước xuất bản ảnh thành công. Bước **Deploy the exact verified image to Render** là **skipped**, không phải triển khai thành công.
- Registry công khai trả HTTP200 cho tag full commit, header Docker-Content-Digest đúng chuỗi trên. Chỉ đọc manifest, không tải ảnh lớn hoặc dùng khóa riêng.
- GitHub xác nhận staging ở commit trên; main còn `a026db6716cab24c5431833644c8976312902dc8` tại lần đối chiếu này. Các commit chỉ tài liệu sau đó không làm đổi mã ảnh ứng dụng cần triển khai.

## 2. Bản sửa có gì và đã kiểm đến đâu?

Người dùng chọn tên trước khi khóa bản xem trước Google Doc; tải lại phục hồi đúng tên/bản duyệt theo chủ sở hữu, không tạo yêu cầu mới để đổi tên. Giữ bước duyệt riêng, kiểm trạng thái và chống ghi trùng. Không đổi migration, quyền Google, gói dịch vụ hoặc mô hình.

34/34 backend liên quan, 219/219 frontend, lint/build và trình duyệt thật tại máy đã đạt; PostgreSQL thật qua CI trên cùng commit. Chỉ một bản xem trước local, chưa duyệt/ghi Google. [Hồ sơ đặt tên tài liệu](../design-work/document-export-20261014/qa/qa-report.md). Linh vật có [bằng chứng Render trước đó](MASCOT-NOTIFICATIONS.md) và kiểm lại local ngày15/10; không lấy nó thay nghiệm thu toàn bộ sản phẩm.

## 3. Đối chiếu URL thật ngày 15/10

Lần đọc `/api/health` đầu hết thời gian chờ35giây; đọc lại cùng URL nhận HTTP200: status=ok, database=true, object_storage=true, vector_store=postgres-pgvector, OAuth đã cấu hình. Không khởi động lại dịch vụ. Đây **không phải** phép đo chuẩn sau ngủ, không chứng minh nguyên nhân lần hết giờ và không kiểm kết nối Gemini/Google bằng tài khoản người dùng. Trường Gemini server chưa cấu hình không nói được khóa riêng người dùng có dùng được hay không.

HTML công khai đang tham chiếu `/assets/index-5fNVRRAp.js` và `ChatPage-UvdgUJLy.js`: có lời thông báo linh vật, nhưng chưa có đường `/api/documents/previews/` hoặc hộp “Tên tài liệu”. Đó là kiểm sự hiện diện mã công khai, không chứng minh digest runtime chính xác hay thao tác đã đăng nhập. Vì vậy không gọi bản sửa tên tài liệu là đã lên URL.

## 4. Một lần triển khai, không đổi cấu hình khác

Nếu kết nối Render đã được cài/xác nhận trong phiên, dùng đúng dịch vụ hiện có. Nếu cần thao tác thủ công:

1. Mở [Settings của Veridra](https://dashboard.render.com/web/srv-dav5v560tbcc73dpjlc0/settings), đúng **My Workspace**, dịch vụ `srv-dav5v560tbcc73dpjlc0`.
2. Phần nguồn ảnh: Edit/Update Source → Existing Image → dán nguyên chuỗi ảnh ở mục1 → Connect/lưu. Không tạo dịch vụ khác, không đổi Environment, quyền hoặc gói trả phí; không bấm thêm lượt triển khai nếu lượt do lưu nguồn đã chạy.
3. Khi Live, đối chiếu digest ở Render với ảnh đã khóa. Kiểm duy nhất phần bị tác động: đáp án giả lập đã có → xuất → sửa tên → Hủy; mở lại → chuẩn bị → tải lại → đúng tên/bản duyệt. **Không bấm duyệt tạo thêm Google Doc, không gọi Gemini** trong bước này.

Nếu có lỗi mới, giữ nguyên mã yêu cầu/trạng thái và chẩn đoán trước khi sửa. Bản quay lại dự kiến là `2dbaac5`/ảnh `ac46a7a22d37ee3c059d3dff560b6d39ec6a6ec2ebb5ec78b7e8be83df13a143`, đã có thu hồi phiên; chưa coi hướng dẫn này là bằng chứng đã diễn tập quay lui.

## 5. Điều kiện còn lại của kế hoạch, không tự đổi thành đạt

| Nhóm hiện có | Cần đúng bằng chứng gì để đóng |
|---|---|
| T02/T04/T08, phần còn lại T07 | Kiểm phần thiếu của nguồn có hiệu lực, đổi số/đổi hồ sơ, nhớ/quên và bản duyệt; ngân sách hiện duyệt19đã dùng18, chưa được dùng ngân sách bổ sung đang hỏi |
| Gói11–13/T09–T10 | Tài khoản thứ hai/thu hồi phiên thật; kết nối nguồn–đích an toàn rồi khôi phục DB+tệp, đối soát; gián đoạn/quay lui/điều kiện mở trang sau ngủ. Tạo project hoặc kiểm đơn vị không thay bằng chứng thực |
| Gói14 | Chủ sở hữu xác nhận dữ liệu/nhà cung cấp, người vận hành, lưu/xóa và quyền tích hợp; hiện chỉ giả lập/công khai, chưa mở dữ liệu doanh nghiệp nhạy cảm |
| Gói08/16 | Góp ý [bản nháp giải thích](AGENT-EXPLANATION-DRAFT-20261015.md) trước sửa UI; sau các điều kiện mới gộp main/thẻ/CI/ảnh/URL và ký biên bản |

Gói10/15 đo lợi ích và dùng lặp lại để quyết định đầu tư, báo riêng; không lấy thiếu bằng chứng thị trường làm lý do sửa kỹ thuật không có điểm dừng. Đây là phân nhóm các việc đã có trong16gói, không tạo checklist hoặc phạm vi mới.
