# Bản ứng viên ed3fa6a — 15/10/2026

**Trạng thái cập nhật 15/10: Live đúng ảnh, phần đặt tên/phục hồi đã kiểm trên URL; chưa ký nghiệm thu Production.** Đây là bản thuộc gói07/T07 của kế hoạch 13/10, không thêm tính năng hoặc đổi bộ nghiệm thu. Nhánh hiện hành là `staging/internal-assistant-20261013`.

## Kết quả triển khai và kiểm URL mới nhất

- Đã cập nhật đúng nguồn ảnh của dịch vụ hiện có qua thanh bên Render, trong **My Workspace**. Lần chạy [dep-db8cmkjncjis73fe9m2g](https://dashboard.render.com/web/srv-dav5v560tbcc73dpjlc0/deploys/dep-db8cmkjncjis73fe9m2g) hiển thị **Deploy succeeded | Live**, thời gian1m50s. Mốc bắt đầu giao diện19:47:14, nhật ký Live19:49:09 ngày15/10/2026 GMT+7; tiêu đề/source đúng digest7727c538…cacb0bd.
- Không tạo dịch vụ, đổi Environment, quyền hoặc gói. Lần bấm Connect đầu hết thời gian chờ điều khiển trước dispatch; đọc lại vẫn còn hộp cập nhật rồi mới bấm lại. Sau khi có mã deploy chỉ theo dõi đúng lần chạy đó, không phát lệnh triển khai thứ hai.
- Kiểm bằng cuộc trò chuyện phép tính giả lập đã có4.0: xuất mở hộp tên mới; xóa hết tên thì nút chuẩn bị bị khóa; nhập tên Việt và Hủy thì hộp đóng, root không còn aria-hidden. Chuẩn bị đúng tên **Kiểm đặt tên - dữ liệu giả lập 15-10-2026** hiện bản khóa và nút xác nhận riêng.
- Tải lại rồi mở xuất: phục hồi đúng tên/bản xem trước, không mở hộp tên mới. Nhật ký100sự kiện đã tải trước và sau phục hồi chỉ có một `docs_prepare` mới ngày15/10,0.63s,mã rút gọnfa78c383; không có `docs_execute` ngày đó trong tập đã tải. Không bấm xác nhận tạo, không gửi câu hỏi mới/đọc nguồn riêng.0Gemini/0chỉ mục/0Doc Google mới.
- DOM màn thanh bên cuối:566×676,scrollWidth556; console error cuối `[]`. Không lấy kích thước này thay kiểm390tại máy hoặc kết quả vận hành tổng thể. Bằng chứng nằm trong [QA đặt tên tài liệu](../design-work/document-export-20261014/qa/qa-report.md), gồm ảnh Render, hộp tên, bản xem trước và bản phục hồi.

Các quan sát công khai buổi chiều ở mục3 dưới đây giữ lịch sử trước triển khai, không còn là trạng thái bản đang chạy sau mốc Live trên. Hướng dẫn mục4 đã thực hiện, **không triển khai lại cùng ảnh chỉ vì đọc tài liệu này**.

Đợt bổ sung cùng ngày đã chạy T02 và hai câu hỏi tiếp T04 còn thiếu; đúng kết luận chính và không lẫn hồ sơ, giữ riêng các thiếu sót về mức đầy đủ. Linh vật báo xong ở trang Bộ nhớ và mở lại đúng hội thoại; T08 tìm được đúng ghi chú v2, sau xác nhận riêng đã xóa đúng mục và tìm mới trả0, ba ghi chú khác giữ nguyên. Chưa kiểm câu trả lời bộ nhớ trong hội thoại mới. Dùng5sinh câu trả lời+2tạo chỉ mục, hết phần bổ sung; cả đợt25/26. [Kết quả gộp](verification/internal-assistant/RESULTS-20261015.md). Chưa đổi mã hoặc ảnh ứng dụng.

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
| T02/T04/T08, phần còn lại T07 | Kiểm phần thiếu của nguồn có hiệu lực, đổi số/đổi hồ sơ, nhớ/quên và bản duyệt. Ngày15/10 đã duyệt thêm tối đa5 sinh câu trả lời+2 tạo chỉ mục, trần đợt26; trước bổ sung dùng18. Không tạo thêm Doc, không tính lại ngân sách theo ngày |
| Gói11–13/T09–T10 | Tài khoản thứ hai/thu hồi phiên thật; gián đoạn/quay lui/điều kiện mở trang sau ngủ. Chủ sở hữu ngày15/10 yêu cầu bỏ qua khôi phục DB+tệp vì không nhớ mật khẩu: loại khỏi đợt, ghi chưa kiểm chứng, không tính đạt và không tiếp tục yêu cầu đổi mật khẩu. Tạo project hoặc kiểm đơn vị không thay bằng chứng thực |
| Gói14 | Chủ sở hữu xác nhận dữ liệu/nhà cung cấp, người vận hành, lưu/xóa và quyền tích hợp; hiện chỉ giả lập/công khai, chưa mở dữ liệu doanh nghiệp nhạy cảm |
| Gói08/16 | Góp ý [bản nháp giải thích](AGENT-EXPLANATION-DRAFT-20261015.md) trước sửa UI; sau các điều kiện mới gộp main/thẻ/CI/ảnh/URL và ký biên bản. Bản đặt tên đã Live và kiểm URL, không còn chờ kết nối Render để triển khai |

Kiểm vận hành bổ sung ngày15/10:16/16ca hàng đợi/tình trạng dịch vụ tại máy đạt, gồm tiến trình thử bị dừng rồi tiến trình mới tiếp tục. Chưa diễn tập quay lui cloud: thao tác Connect đổi sang ảnhac46a7a bị lớp xét duyệt quyền từ chối vì thiếu xác nhận riêng. Đã hủy hộp nguồn chưa lưu; bản chạy vẫn7727c538. Không gọi thêm Gemini hoặc thay dữ liệu/Environment. [Giới hạn và phép chuyển cần xác nhận](verification/internal-assistant/RESULTS-20261015.md#t10-xử-lý-gián-đoạn-và-giới-hạn-quay-lui).

Gói10/15 đo lợi ích và dùng lặp lại để quyết định đầu tư, báo riêng; không lấy thiếu bằng chứng thị trường làm lý do sửa kỹ thuật không có điểm dừng. Đây là phân nhóm các việc đã có trong16gói, không tạo checklist hoặc phạm vi mới.
