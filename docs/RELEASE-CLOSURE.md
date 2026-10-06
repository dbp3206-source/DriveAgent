# Đợt nghiệm thu cuối — chốt phạm vi 06/10/2026

Danh sách điều hành được người dùng yêu cầu tinh gọn. Đợt demo chỉ còn bốn nhóm
bắt buộc A, B, E và F. Nhóm C và D được chủ sở hữu loại khỏi đợt nghiệm thu này
ngày 06/10/2026 để tránh kéo dài tiến độ. Không thêm tính năng hoặc thiết kế lại.
Tiêu chí chưa có bằng chứng giữ chưa đạt.

| Nhóm | Việc còn lại | Điều kiện đóng |
|---|---|---|
| A | Độ dài báo cáo, bảo toàn dẫn nguồn, phạm vi số liệu PDF, bản xem trước Doc hết hạn | Ca lỗi đã tái hiện đạt trên URL thật; duyệt và đọc lại đúng, không trùng |
| B | Ba quy trình đầu ngày, trước hẹn, hoàn thiện/lưu; ghép kiểm nguồn, hỏi tiếp, quy trình đã lưu, nhớ/sửa/quên | Hoàn thành xuyên suốt, bảy vai trò và kiểm soát công cụ có dấu vết; hẹn giờ có lần chạy thật |
| C | **LOẠI KHỎI ĐỢT DEMO** — tốc độ mở/sau ngủ, đăng nhập, đổi khóa, lỗi mạng và kiểm lại toàn bộ giao diện | Không tính điểm và không dùng để chứng nhận; giữ giới hạn Render Free đã công bố |
| D | **LOẠI KHỎI ĐỢT DEMO** — khôi phục độc lập, quan sát mở rộng và bộ kiểm an toàn nâng cao | Không tính điểm và không dùng để chứng nhận; lỗi nghiêm trọng về quyền, mất dữ liệu hoặc ghi thiếu duyệt nếu phát hiện vẫn chặn phát hành |
| E | Hoàn thành 24 tác vụ đã khóa, ca bộ nhớ, đối chứng và lỗi giả lập hiện có | Tổng >=8,7/10; nguồn/nghiệp vụ/tin cậy >=9; đủ mẫu, không lỗi nghiêm trọng hoặc quy trình chính thất bại |
| F | Máy sạch, hướng dẫn, demo 10 phút, tài liệu đúng khả năng, CI, main, Render, quay lui | Cùng bản đã nghiệm thu; URL và hướng dẫn dùng được |

Thứ tự A, B, E rồi F; mục A còn lỗi được giữ chờ để tiếp tục B/E/F,
không lặp vô hạn và không đổi nhãn thành đạt. Mỗi mục đạt được
đóng; chỉ kiểm lại khi thay đổi ảnh hưởng trực tiếp. Sửa lỗi theo ca liên quan;
chạy toàn bộ kiểm máy ở bản chốt. Không gọi mô hình lặp để chọn câu trả lời đẹp.
Chỉnh thẩm mỹ nhỏ và tiện ích phụ được để bản sau, không chặn phát hành.

### Cách kiểm gộp đã chốt

- Gom các sửa chữa liên quan vào một bản; kiểm tự động đầy đủ một lần trước triển khai.
- Trên URL thật, kiểm một lần mỗi ca bị ảnh hưởng. Giữ kết quả không đạt để xử lý
  theo nguyên nhân; không gửi lại cùng câu hỏi để chọn một câu trả lời đẹp.
- Dùng một chuỗi nghiệp vụ để đồng thời kiểm chọn nguồn, tính toán, hỏi tiếp,
  nhớ điều đã sửa và lưu/đọc lại. Không chạy lại các thao tác đã có bằng chứng
  khi phần mã tương ứng không thay đổi.
- Chỉ đóng phát hành sau khi các lỗi còn chờ được giải quyết; tiến sang nhóm sau
  không có nghĩa là A đã đạt hoặc sản phẩm đã sẵn sàng phát hành.

Bốn người thật hiện thiếu ba người: giữ CHƯA KIỂM CHỨNG, không chứng nhận từ
tài khoản quản trị. Render miễn phí ngủ khi không hoạt động; không hứa luôn bật.
OCR/PDF ảnh, dịch vụ trả phí, ghi Calendar và hạ tầng nặng vẫn ngoài phạm vi.
PDF có văn bản vẫn trong phạm vi.

## Điểm bắt đầu có bằng chứng

- Staging `3b3afbc`: CI `37333982226` thành công; ảnh
  `sha256:13546369e918ebba41fb621aad27c77b8c2e2d9da279b301684e8f6ca8ccb0c7`
  đang chạy Live trên Render. Bản sửa phục hồi bản xem trước có 187 phép kiểm
  giao diện đạt; sửa bảo toàn dẫn nguồn có 104 phép kiểm đạt. Vẫn cần nghiệm thu
  hai ca này trên URL thật để đóng A.
- Cloud d319f1d là bằng chứng lịch sử: còn báo cáo ngắn, bản sửa định dạng bị từ
  chối và chưa tạo Doc. Không đổi nhãn kết quả cũ thành bằng chứng bản chốt.
- Hồ sơ lịch sử: design-work/qa/LIVE-ACCEPTANCE-20261005.md. Không đổi nhãn các
  phép đo cũ thành bằng chứng bản mới.

Kết thúc khi bốn nhóm A, B, E và F có đủ bằng chứng. C và D giữ nhãn `EXCLUDED`
trong báo cáo cuối, không được đổi thành `PASS`. Khi đó đóng phiên bản và dừng
chỉnh sửa; không mở thêm vòng hoàn thiện chung chung.

## Đối soát cuối ngày 06/10 — chưa đóng phát hành

- Render đã phục vụ `89f9c82`, ảnh `sha256:a970c8dbef2300d1a0167269655ce76e10870649ff76484554ff95d3d960e1c3`;
  CI `37449967840` đạt. Đây không phải xác nhận đủ A/B/E/F.
- B: đọc gộp tối đa năm thư và lịch 24 giờ hoàn tất trong 25,2 giây,
  một lần gọi mô hình; lưu và mở lại giữ dẫn nguồn. Lịch trống nên chưa
  chứng nhận chuẩn bị cho một cuộc hẹn thực tế có dữ liệu.
- Quy trình Minh Phát đọc hai tệp và tính toán hoàn tất 41,7 giây.
  Bước đổi sang An Bình bị chặn khi mô hình gọi công cụ không được cung cấp;
  giữ chưa đạt, không nới quyền để lấy kết quả đẹp.
- Nguồn web không truy cập được đã gọi công cụ thật nhưng chưa có câu trả
  lời hữu ích. Số học PDF đúng nhưng phạm vi dự báo ngân hàng vẫn diễn giải
  sai; A còn chờ. E chưa đủ bộ 24 tác vụ và chưa có điểm tổng hợp lệ.
- Sửa tiếp: lịch sử gọi công cụ được tách theo trợ lý và tập công cụ hiện tại;
  lịch sử hội thoại chính vẫn được nạp đúng người và đúng cuộc trò chuyện.
  Khi công cụ web không trả bằng chứng đủ, trả rõ chưa xác minh và ghi cảnh
  báo, không tính thành công nghiệp vụ. Lỗi quyền, nguồn không an toàn và
  hết hạn mức vẫn bị chặn. 204 phép kiểm liên quan đạt; chưa kiểm live bản sửa.
- `main` chưa gộp. Không công bố sẵn sàng phát hành khi các mục trên chưa đạt.
