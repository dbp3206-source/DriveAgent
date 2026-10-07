# Năm bước chốt nghiệm thu

Ngày chốt: 07/10/2026. Phạm vi: A/B/E/F theo RELEASE-CLOSURE.md.
Không thêm tính năng, vòng thiết kế hay bộ đo mới. C/D loại khỏi đợt demo;
P06 hoãn; chỉ một quản trị thật. Không đổi các mục này thành đạt.

| Bước | Làm gì | Điều kiện đóng |
|---|---|---|
| 1 — Khóa bản | Dùng ef04f01 đã qua CI và triển khai đúng ảnh; giữ cố định bản nghiệm thu. | CI đạt, dịch vụ Live đúng ảnh; không dùng trạng thái Live của bản cũ. |
| 2 — Đóng A | Kiểm lại tuyến website bằng một ca hồ sơ doanh nghiệp sau sửa; đối soát từng nhận định với nguồn đã đọc, phạm vi doanh nghiệp và ngày tin. Hoàn tất các ca hồ sơ/thông tin cập nhật còn thiếu trong bộ đã khóa. | Có lần đọc web thật; dẫn nguồn hỗ trợ kết luận; không bịa lịch/ngân sách hoặc coi thiếu bằng chứng là đạt. |
| 3 — Đóng B | Hoàn tất phần còn thiếu của ba quy trình: đầu ngày, chuẩn bị tư vấn, xem trước/duyệt/đọc lại; kiểm hỏi tiếp đổi phạm vi, quy trình đã lưu, nhớ/quên và kết quả xuất. Dùng lại biên nhận hợp lệ, không tạo thêm tài liệu Google hoặc đọc thêm thư ngoài phép. | Chuỗi đủ bước, đầu vào mới không lẫn dữ kiện cũ; lưu/mở lại đúng; ghi rõ lịch trống và dấu vết vai trò thực sự có. |
| 4 — Đóng E | Đối soát kết quả 24 tác vụ đã khóa, P06 giữ hoãn; không chạy thêm mẫu ngoài bộ. Chỉ tính số đo từ bằng chứng thật, công bố mẫu số/ngoại lệ và kết quả chưa đạt. Chốt hướng dẫn và bài demo 10 phút bằng các kết quả này. | Đủ bằng chứng cho các tác vụ áp dụng; điểm theo ngưỡng đã khóa, không có điểm giả hoặc lỗi chức năng chính bị bỏ qua. Không dùng kết quả lịch sử khác bản như phép kiểm mới. |
| 5 — Đóng F | Khi 1–4 đạt: gộp staging vào main, kiểm CI main, triển khai đúng ảnh; kiểm ngắn đăng nhập, nguồn, kết quả đã lưu và URL. Công bố bản/mã ảnh, báo cáo nghiệm thu, giới hạn và cách quay lui. | Main và Render cùng bản đã nghiệm thu; URL dùng được; bàn giao đủ. Dừng chỉnh sửa sau bước này. |

## Trạng thái lúc khóa

- Bước 1 đạt: CI 37563231626 thành công; ef04f01 chạy đúng ảnh trên Render,
  đợt dep-db2r5dks728c73abmc6g Live lúc 02:49:04 UTC ngày 07/10.
  Ảnh: sha256:0f26be48e572d73e98a237ab5675952774bfe7f0abd309be1554f2d1d07a1f59.
- Bước 2: ca Bosch trên ef04f01 hoàn tất 28,5 giây, đọc web thành công,
  phân biệt ngày/phạm vi/trạng thái và đủ ba câu hỏi làm rõ. Đóng riêng lỗi
  bỏ câu hỏi; còn thuật ngữ tiếng Anh. Chưa đủ các ca còn lại, chưa đóng A.
- Bước 3: W04 đạt đủ ba lượt tính/sửa/nhớ trên ef04f01; đã đối soát mở bản
  lưu và tìm ghi chú đã xóa. Hẹn giờ và xuất có biên nhận lịch sử; chưa đóng toàn B.
- Bước 4 chưa đủ bộ kết quả/điểm hợp lệ. Không công bố điểm tổng hiện tại.
- Bước 5 chưa gộp main; phải chờ các bước trên.

## Quy tắc dừng vòng sửa

Chỉ sửa lỗi làm thất bại một bước trên, sau khi xác định nguyên nhân.
Gộp sửa và kiểm trong một đợt; không kiểm lại phần không bị ảnh hưởng chỉ để
tăng số phép thử. Một lỗi bắt buộc chưa giải quyết thì báo đúng mục bị chặn,
không phát sinh danh sách hoàn thiện mới hoặc tự cấp nhãn sẵn sàng phát hành.
Thiếu hạn mức/quyền/dữ liệu không phải lý do bịa kết quả. Không yêu cầu thêm khóa.
