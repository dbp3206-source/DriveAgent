# Veridra — bàn giao bản demo đã chốt

Ngày 10/10/2026, người dùng đã trả lời “ok” cho câu hỏi chấp nhận bản demo
có giới hạn để đưa lên main. Quyết định này cho phép bàn giao, không phải
chứng nhận toàn bộ sản phẩm sẵn sàng vận hành. Dừng sửa phần web.

## Bản được bàn giao

- [Sản phẩm](https://veridra-closed-beta.onrender.com).
- [Mã nguồn main](https://github.com/dbp3206-source/DriveAgent/tree/main).
- Mã ứng dụng đã khóa: bfa018a78ae7eb46f91bd8904df2dccc2e9d2c51.
- [Kiểm GitHub của mã ứng dụng](https://github.com/dbp3206-source/DriveAgent/actions/runs/38059563702): đạt toàn bộ. Có 490 phép kiểm gộp trong máy; không dùng số này làm điểm chất lượng câu trả lời.
- Ảnh ứng dụng đã kiểm và chạy trên Render:
  `ghcr.io/dbp3206-source/veridra@sha256:5087f3edba1d6ca87f70a05a4983b8b4833d2acf9ec14cd5bcdd707a6d86f79e`.
- Biên nhận trước bàn giao: Render dep-db54p6nlot8c73dnkk80 thành công lúc
  21:34:52 ngày 10/10 giờ Việt Nam. HTTP health 200, cơ sở dữ liệu và kho tệp tốt.
- Lượt đẩy main chạy kiểm GitHub riêng. Ảnh main chỉ được dùng sau khi kiểm
  thành công; mã ảnh và biên nhận triển khai cuối được đối chiếu trong bàn giao,
  không suy từ tên nhánh hoặc tham số URL. Thay đổi bàn giao chỉ gồm tài liệu
  và quyết định nghiệm thu; mã ứng dụng không đổi so với bfa018a.

## Bằng chứng dùng cho demo

| Nội dung | Có thể trình bày | Không tuyên bố |
|---|---|---|
| Hồ sơ doanh nghiệp | Shopee đã chạy trên bản cuối, nguồn website thật, ba câu hỏi và trạng thái chưa ghi; có biên nhận Vinamilk và các doanh nghiệp khác giữ đúng bản cũ | Mọi câu trả lời luôn đúng; diễn giải nhu cầu là quy trình thực tế đã xác nhận |
| Nguồn mới | Đúng ngày máy chủ; giữ yêu cầu nguồn chính thức; thiếu nguồn thì báo chưa xác minh | Đã tìm được khoảng sự kiện ASIAD từ nguồn chính thức |
| Hỏi tiếp và tính toán | Giữ biên nhận W01/W02/W04, dữ kiện điều chỉnh, phép tính, điều chưa biết | Các con số giả lập là mức tiết kiệm đã đo trong thực tế |
| Quy trình, bộ nhớ, kết quả | Quy trình đã lưu đổi đầu vào; sửa/cất/xóa bộ nhớ; kết quả Mộc An bản 2 và xuất tệp có bằng chứng lịch sử | Mọi bước vừa chạy lại trên ảnh cuối; hình thức Word đã được kiểm; ghi chú thử đã xóa còn tồn tại |
| Google và hẹn giờ | Biên nhận đọc đã cho phép, tài liệu thử đã duyệt/đọc lại và bản tin thử chạy một lần | Đã kiểm trước hẹn có lịch thật, cả bảy vai trò hoặc đang bật lịch chạy mỗi ngày |

## Giới hạn được giữ công khai

ASIAD chưa đủ nguồn chính thức. W03 chưa đủ chuỗi trước/sau sửa trên cùng
bản; W06 chưa kiểm hình thức Word. Lịch thật trống; chưa đủ dấu vết cả bảy
vai trò. Chưa có tổng điểm hợp lệ theo bộ 24 tác vụ và ngưỡng 8,7/10.
PDF đã hoãn, C/D đã loại khỏi đợt demo; chỉ có một tài khoản quản trị thật.
Các kết quả này không bị đổi nhãn thành đạt. Render miễn phí có thể ngủ;
Gemini/Google phụ thuộc hạn mức và tình trạng dịch vụ ngoài.

## Cách trình bày và vận hành

1. Đăng nhập tài khoản đã được mời; không chiếu khóa, thư riêng hoặc cấu hình bí mật.
2. Dùng [kịch bản 10 phút](DEMO-10-PHUT.md) và hai tệp giả lập trong `docs/demo/`.
3. Ưu tiên mở kết quả đã có biên nhận. Nói rõ khi xem lại, không giả là vừa chạy.
4. Không tạo thêm tài liệu Google, gửi thư, tạo lại ghi chú đã xóa, tăng hạn mức hoặc đổi gói để trình diễn.
5. Nếu dịch vụ ngoài lỗi, dừng lượt đó và mở kết quả đã lưu; không thử lặp để chọn câu trả lời đẹp.

## Quay lui khi cần

Trước thay ảnh, giữ nguyên mã ảnh Render đang chạy. Nếu ảnh main không mở
được, trong Settings → Source của chính dịch vụ hiện có, chọn Existing Image
và dùng lại ảnh bất biến 5087f3ed ở trên; chờ Deploy succeeded | Live rồi mở
`/api/health`. Không đổi biến bí mật, quyền, gói dịch vụ hoặc dữ liệu.
Đây là hướng dẫn quay lui ứng dụng, không phải biên nhận khôi phục cơ sở dữ liệu.

## Điểm dừng

Sau khi main được cập nhật, kiểm GitHub trên main thành công, Render chạy
ảnh đã kiểm và mở lại được URL/nguồn/kết quả đã lưu: hoàn tất bàn giao bản
demo có giới hạn. Không phát sinh vòng sửa web, kiểm PDF hoặc gọi mô hình mới.
Kết quả bộ nghiệm thu đầy đủ vẫn giữ tại `backend/evals/release_acceptance.json`;
quyết định demo được ghi riêng, không tạo điểm giả.
