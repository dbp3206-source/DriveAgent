# Năm bước chốt nghiệm thu

Ngày chốt: 07/10/2026. Phạm vi: A/B/E/F theo RELEASE-CLOSURE.md.
Không thêm tính năng, vòng thiết kế hay bộ đo mới. C/D loại khỏi đợt demo;
P06 hoãn; chỉ một quản trị thật. Không đổi các mục này thành đạt.

| Bước | Làm gì | Điều kiện đóng |
|---|---|---|
| 1 — Khóa bản | Đẩy một đợt sửa chung về bằng chứng web, chạy kiểm tự động và triển khai đúng ảnh; sau đó cố định bản nghiệm thu. | Kiểm GitHub đạt, dịch vụ chạy đúng bản; không dùng trạng thái triển khai của bản cũ. |
| 2 — Đóng A | Kiểm lại tuyến website bằng một ca hồ sơ doanh nghiệp sau sửa; đối soát từng nhận định với nguồn đã đọc, phạm vi doanh nghiệp và ngày tin. Hoàn tất các ca hồ sơ/thông tin cập nhật còn thiếu trong bộ đã khóa. | Có lần đọc web thật; dẫn nguồn hỗ trợ kết luận; không bịa lịch/ngân sách hoặc coi thiếu bằng chứng là đạt. |
| 3 — Đóng B | Hoàn tất phần còn thiếu của ba quy trình: đầu ngày, chuẩn bị tư vấn, xem trước/duyệt/đọc lại; kiểm hỏi tiếp đổi phạm vi, quy trình đã lưu, nhớ/quên và kết quả xuất. Dùng lại biên nhận hợp lệ, không tạo thêm tài liệu Google hoặc đọc thêm thư ngoài phép. | Chuỗi đủ bước, đầu vào mới không lẫn dữ kiện cũ; lưu/mở lại đúng; ghi rõ lịch trống và dấu vết vai trò thực sự có. |
| 4 — Đóng E | Đối soát kết quả 24 tác vụ đã khóa, P06 giữ hoãn; không chạy thêm mẫu ngoài bộ. Chỉ tính số đo từ bằng chứng thật, công bố mẫu số/ngoại lệ và kết quả chưa đạt. Chốt hướng dẫn và bài demo 10 phút bằng các kết quả này. | Đủ bằng chứng cho các tác vụ áp dụng; điểm theo ngưỡng đã khóa, không có điểm giả hoặc lỗi chức năng chính bị bỏ qua. Không dùng kết quả lịch sử khác bản như phép kiểm mới. |
| 5 — Đóng F | Khi 1–4 đạt: gộp staging vào main, kiểm CI main, triển khai đúng ảnh; kiểm ngắn đăng nhập, nguồn, kết quả đã lưu và URL. Công bố bản/mã ảnh, báo cáo nghiệm thu, giới hạn và cách quay lui. | Main và Render cùng bản đã nghiệm thu; URL dùng được; bàn giao đủ. Dừng chỉnh sửa sau bước này. |

## Trạng thái lúc khóa

- Bước 1: bản đang chạy đã đạt kiểm triển khai; bản sửa bằng chứng web mới
  vẫn ở local, chưa đẩy và chưa triển khai. Không dùng bằng chứng của bản đang
  chạy để chứng nhận bản sửa. Lệnh đẩy trước bị bộ duyệt chặn vì hạn mức;
  không đi đường khác để vượt chặn. Kiểm local: 179 phép kiểm đạt trong
  67,90 giây, gồm nguồn, điều phối, tìm web và yêu cầu cuối khóa; kiểm mã đạt.
  CI 37563231626 thành công; ef04f01 chạy đúng ảnh trên Render,
  đợt dep-db2r5dks728c73abmc6g Live lúc 02:49:04 UTC ngày 07/10.
  Ảnh: sha256:0f26be48e572d73e98a237ab5675952774bfe7f0abd309be1554f2d1d07a1f59.
- Bước 2: ca Bosch trên ef04f01 hoàn tất 28,5 giây, đọc web thành công,
  phân biệt ngày/phạm vi/trạng thái và đủ ba câu hỏi làm rõ. Đóng riêng lỗi
  bỏ câu hỏi; còn thuật ngữ tiếng Anh. Ca Vinamilk suy diễn việc ra mắt từ
  tiêu đề sản phẩm và nhận tiêu đề rác. Đã sửa chung ở local: loại tiêu đề
  rác, chỉ trình bày tiêu đề/ngày đăng đối với nguồn chưa đọc toàn văn ở cả
  hai tuyến điều phối. Chưa kiểm thật sau sửa, chưa đủ các ca còn lại,
  chưa đóng A. Sửa này không chứng minh mọi nhận định không dẫn nguồn đều đúng.
- Bước 3: W04 đạt đủ ba lượt tính/sửa/nhớ trên ef04f01; đã đối soát mở bản
  lưu và tìm ghi chú đã xóa. Hẹn giờ và xuất có biên nhận lịch sử; chưa đóng toàn B.
- Bước 4 chưa đủ bộ kết quả/điểm hợp lệ. Không công bố điểm tổng hiện tại.
- Bước 5 chưa gộp main; phải chờ các bước trên.

## Phần còn lại, không mở rộng

1. Đưa đợt sửa đang có lên bản nghiệm thu sau khi lệnh đẩy được phép chạy.
2. Đóng A bằng các ca còn thiếu trong bộ đã khóa; gộp kiểm web, nội dung và
   tiếng Việt. Không chạy lại ca đã đạt nếu mã sửa không ảnh hưởng.
3. Đóng B bằng các đoạn quy trình còn thiếu; đối soát lại biên nhận lưu,
   xuất và hẹn giờ, chỉ chạy đoạn chưa có bằng chứng phù hợp.
4. Chốt E: tính đúng kết quả bộ 24 tác vụ theo ngưỡng đã khóa, công bố mục
   hoãn/không áp dụng; hoàn tất hướng dẫn và bài demo 10 phút.
5. Chốt F: chỉ khi 1–4 đạt mới gộp main, kiểm tự động và triển khai đúng bản;
   kiểm ngắn URL rồi bàn giao. Không sửa tiếp ngoài lỗi chặn các bước này.

Danh sách này không bảo đảm sẽ đạt ngưỡng khi chưa đo. Nếu hạn mức không
đủ, phải ghi chưa kiểm, không thay bằng điểm giả. Nghiệm thu giới hạn cho
một quản trị và phạm vi demo; không chứng nhận vận hành bốn người hoặc
khôi phục/an toàn/tốc độ đầy đủ khi C/D đã được loại khỏi đợt này.

## Quy tắc dừng vòng sửa

Chỉ sửa lỗi làm thất bại một bước trên, sau khi xác định nguyên nhân.
Gộp sửa và kiểm trong một đợt; không kiểm lại phần không bị ảnh hưởng chỉ để
tăng số phép thử. Một lỗi bắt buộc chưa giải quyết thì báo đúng mục bị chặn,
không phát sinh danh sách hoàn thiện mới hoặc tự cấp nhãn sẵn sàng phát hành.
Thiếu hạn mức/quyền/dữ liệu không phải lý do bịa kết quả. Không yêu cầu thêm khóa.
