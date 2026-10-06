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

### Chẩn đoán nguyên nhân trước khi sửa tiếp

- Mã lỗi web thật được đọc từ Nhật ký: `web_source_transport_error`;
  không suy ra hết hạn mức hoặc công cụ chưa được gọi.
- Quy trình đổi đầu vào nạp thành công rồi bị chặn với `unavailable_tool`.
  Nhật ký cũ không giữ tên công cụ bị chặn nên chưa đủ bằng chứng xác định
  nguyên nhân dẫn đến lệnh sai. Không thêm ngoại lệ theo khách hàng kiểm thử.
- Bổ sung chẩn đoán chỉ gồm tên công cụ khớp danh mục máy chủ và danh sách
  công cụ được cấp; tên tự dựng thành `unknown`, không lưu đối số riêng.
  Không nới quyền, không gọi lại, không đổi lỗi thành thành công.
  72 phép kiểm ADK/hội thoại đạt; kiểm mã và khoảng trắng đạt.
  Vẫn cần đọc bằng chứng của lần chạy trên bản triển khai trước khi đóng lỗi.

- Tái hiện độc lập bằng hàm ngữ cảnh: yêu cầu chỉ dùng lượt hiện tại vẫn nạp
  hai lượt cũ và số liệu cũ. Nguyên nhân nằm ở việc giới hạn độ dài lịch sử
  nhưng không giới hạn lịch sử theo phạm vi bằng chứng người dùng yêu cầu.
  Sửa cơ chế chung: mỗi yêu cầu có phiên công cụ riêng; hội thoại chuẩn vẫn
  giữ ngữ cảnh ngắn hạn. Khi có chỉ dẫn rõ chỉ dùng đầu vào hiện tại, loại
  dữ kiện và dẫn nguồn trước mốc đó khỏi ngữ cảnh thực thi, kể cả hỏi tiếp.
  Không xóa lịch sử hiển thị hoặc bộ nhớ dài hạn. Câu phủ định/trích dẫn
  không tự trở thành lệnh bỏ ngữ cảnh. 169 phép kiểm liên quan đạt; kiểm
  riêng các ranh giới ngữ cảnh đạt. Chưa chứng nhận ca live đã hết lỗi.

### Bằng chứng mới và nguyên nhân phạm vi PDF — 06/10/2026

- Bản `37fb6d3` chạy đúng ảnh `sha256:40b4ab7341844a82482bfa553a3749b67d31f28399966f325f2a868fde979b27`,
  CI `37457008642` đạt, Render `dep-db2dqqrncjis73ebrm0g` Live.
- Đổi An Bình trong chính hội thoại Minh Phát: lượt
  `6f88a691-2ceb-4dbb-ad6a-2d29fc6e584e`, 25,8 giây, giữ 8 người và ba câu
  hỏi làm rõ, có `skill_run`; không mang số liệu, dẫn nguồn hoặc phép tính cũ
  vào câu trả lời, không gọi công cụ nguồn bị cấm. Đạt ca đổi đầu vào đã tái hiện.
- Web không truy cập được: `a0916d11-571a-46e5-9dda-70684e529234`, 11,2 giây,
  có `web_research` lỗi và trả rõ chưa xác minh, không bịa lịch hoặc dẫn nguồn.
  Đạt cách xử lý thiếu bằng chứng, không phải đã tìm được thông tin.
- Bản kết quả giả lập Mộc An `5cbbce8b-70de-4fe6-8078-2ea3a474ce5d` mở lại
  trên bản này vẫn v2, bốn câu hỏi, 62 từ/260 ký tự. Không gọi lại mô hình hoặc
  ghi lại kết quả để tạo bằng chứng mới.
- Đối chiếu trực tiếp chữ nguồn ngân hàng trang 1: tiêu đề và phần giải thích
  dùng phạm vi không đồng nhất. Nhãn phạm vi hẹp ở vị trí 539, chi tiết ở 1689;
  đoạn trích 500 ký tự mất cả hai, trong khi phần văn bản đầy đủ vẫn có.
  Đây là lỗi bảo toàn bằng chứng có thể tái hiện, không phải căn cứ khẳng định
  mọi câu dùng nhãn rộng đều do mô hình tự bịa.
- Sửa chung giữ phần thân trang tới 3.000 ký tự trong trích dẫn trang cụ thể,
  giữ chữ cỡ lớn khi có trong giới hạn 4.000 ký tự; không lấy trang kế tiếp.
  Yêu cầu đối chiếu tiêu đề với phần giải thích, công bố phạm vi không thống
  nhất thay vì âm thầm chọn một nhãn. Không đổi oracle hoặc gắn ngoại lệ theo tệp.
  181 phép kiểm liên quan đạt; sau bổ sung kiểm qua công cụ đọc thật với nguồn
  giả lập, 19 phép kiểm nguồn/trích dẫn đạt. Chưa coi P06 đã đạt live sau sửa này.
- A/B/E/F chưa đóng: còn phạm vi PDF trên URL sau sửa, các chuỗi nghiệp vụ đủ
  bước, hẹn giờ chạy thật, bộ 24 tác vụ đủ bằng chứng và bàn giao cùng bản.
  Giữ main chưa gộp; không dùng CI xanh làm chứng nhận chất lượng trả lời.
