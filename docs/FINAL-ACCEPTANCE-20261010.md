# Nghiệm thu cuối theo phạm vi đã chốt

## Quyết định và phạm vi

Sau đợt kiểm duyệt ngày 10/10/2026, người dùng yêu cầu thực hiện phần còn
lại và nghiệm thu. Phạm vi cuối gồm đúng hai lỗi bên dưới và một lượt kiểm
gộp sau triển khai. Đây là bản dùng thật có giới hạn cho quản trị/nhóm nhỏ
đã được kiểm và bài demo dự án. Quyết định này tiếp nối
[bàn giao trước đó](DEMO-HANDOFF-20261010.md).

## Hai lỗi phải đóng

| Mục | Nguyên nhân | Cách sửa và bằng chứng trong máy |
|---|---|---|
| Liên kết nguồn chính thức | Khi chuyển HTML thành chữ, bộ đọc bỏ địa chỉ trong thẻ liên kết. Bước tìm website được nguồn chính thức dẫn tới không còn địa chỉ để đọc tiếp. | Giữ địa chỉ HTTPS cạnh nhãn và ngữ cảnh; giải đường dẫn tương đối theo trang nguồn. Kiểm qua tuyến thu thập thật với máy chủ thử: đọc trang cơ quan → lấy liên kết → đọc trang tổ chức; vẫn giữ giới hạn hai trang, xác minh địa chỉ và không chuyển khóa tìm kiếm sang website. |
| Tỷ lệ thành công của Nhật ký | Ô tổng hợp chỉ đếm lượt có thời gian đo; biểu đồ đếm mọi lượt đã kết thúc. Cùng dữ liệu hiện 82/96 = 85% và 84/98 = 86%. | Dùng chung cách tính trên mọi lượt đã kết thúc; lượt đang chạy không tính thành lỗi. Tốc độ chỉ dùng thời gian đo hợp lệ, thiếu dữ liệu không coi là 0. Tái hiện bộ 100 sự kiện: cả hai nơi phải là 84/98 = 86%. |

Kiểm trong máy: 129 phép kiểm máy chủ liên quan đạt trong 29,01 giây;
190 phép kiểm giao diện đạt. Đây là kiểm hành vi mã, không phải điểm
chất lượng câu trả lời của Gemini.

## Điều kiện bàn giao

1. Kiểm mã, dựng giao diện và toàn bộ kiểm GitHub của bản sửa thành công.
2. Render chạy đúng ảnh bất biến được kiểm; địa chỉ sản phẩm và kiểm sức khỏe phản hồi tốt.
3. Mở Nhật ký, đối soát tỷ lệ giữa ô tổng hợp và biểu đồ; kiểm các màn hình nguồn/kết quả đã lưu/trò chuyện và ảnh đã yêu cầu. Ghi biên nhận bản, số đo và ảnh chụp thực tế.
4. Ghi quyết định nghiệm thu có giới hạn, cập nhật main và khóa đợt sửa.

Trạng thái: đang kiểm và chuẩn bị triển khai; chưa xác nhận lượt nghiệm
thu trên bản mới. Biên nhận cuối sẽ được ghi tại đây sau khi có kết quả.

## Cách dùng bằng chứng A/B/E/F

- A: hai lỗi cuối được kiểm đúng phần bị ảnh hưởng; giữ biên nhận câu trả lời và nguồn đã đối soát trước đó.
- B: giữ biên nhận hỏi tiếp/đổi dữ kiện, tính toán, quy trình đã lưu, bộ nhớ và kết quả xuất; mở lại dữ liệu hiện có trên bản mới để kiểm tính liên tục. Không tạo lại ghi chú đã xóa hoặc tài liệu Google.
- E: giữ kết quả và giới hạn thật. Không cấp điểm tổng 8,7/10 từ số phép kiểm mã, không đổi ca thiếu bằng chứng thành đạt. Dùng quyết định nghiệm thu có giới hạn đã được người dùng chấp nhận.
- F: bản ứng dụng đã kiểm trên main, đúng ảnh Render, URL dùng được, biên nhận và hướng dẫn demo được bàn giao.

Các giới hạn đã chấp nhận ở biên bản trước vẫn áp dụng: một quản trị thật;
PDF hoãn; C/D loại khỏi đợt demo; lịch thật trống; chưa có tổng điểm của bộ
24 tác vụ, chuỗi đầy đủ bảy vai trò và kiểm hình thức Word. Không suy từ
sửa mất liên kết rằng ASIAD đã tìm được nguồn. Đây không phải chứng nhận
vận hành nhiều người dùng ở quy mô lớn.

Sau khi bốn điều kiện bàn giao đạt, đợt sửa kết thúc. Các yêu cầu mới được
xử lý như một đợt riêng khi người dùng yêu cầu.
