# Tìm kiếm web miễn phí — cấu hình và kiểm trước triển khai

Người dùng đồng ý bổ sung Tavily ngày 08/10/2026 để khắc phục việc Gemini
từ chối khả năng tìm kiếm và nguồn dự phòng chỉ có tiêu đề. Không thay đổi
phạm vi A/B/E/F, không bật trả phí hoặc nới hạn mức Gemini.

## Một lần cấu hình

1. Tạo khóa tại https://app.tavily.com với gói miễn phí. Không thêm thẻ,
   không bật trả theo lượt. Không gửi khóa trong Chat.
2. Để kiểm nội bộ trước triển khai, tự lưu khóa vào `.env` đã được Git bỏ qua,
   dưới tên `DRIVE_AGENT_TAVILY_API_KEY`. Giữ các biến hiện có, không chụp
   hoặc đăng nội dung tệp. Khóa nằm ở máy chủ, không có biến frontend.
3. Sau khi kiểm nguồn và câu trả lời đạt, nhập cùng biến trong Render →
   dịch vụ Veridra → Environment. Triển khai đúng mã ảnh của bản đã kiểm,
   không dùng ảnh 81665f7 cũ hoặc coi đổi biến là đã cập nhật mã.

## Luồng và giới hạn

- Có khóa: đúng một yêu cầu tìm kiếm `basic`, không tự chọn `advanced`,
  không gọi dịch vụ trích xuất riêng hoặc câu trả lời tự sinh của Tavily.
  Tối đa sáu kết quả. Dùng văn bản trang do Tavily trích xuất; nếu thiếu,
  thử đọc trang trực tiếp một lần. Không dùng đoạn giới thiệu tìm kiếm làm
  bằng chứng đã đọc trang. Nội dung lưu và nội dung dùng suy luận giống nhau.
- Sau đó tổng hợp một lần bằng Gemini hiện có, kiểm trích đoạn và nguồn.
  Bỏ lần gọi Gemini Search vốn đang bị từ chối. Bộ điều phối vẫn có thể cần
  một lượt riêng để ghép báo cáo tư vấn; không tuyên bố toàn Chat chỉ một lượt.
- Tìm kiếm/đọc nguồn có giới hạn tổng 25 giây. Nội dung trả tối đa 2 MB;
  mỗi đoạn trang tối đa 9.000 ký tự. Chặn URL nội bộ và đường chuyển hướng
  nội bộ. Khóa chỉ gửi tới API Tavily, không chuyển tới các website nguồn.
- Truy vấn doanh nghiệp không chứa nội dung thư, lịch, thông tin liên hệ hay
  ngân sách riêng. Dữ liệu trang chỉ là nguồn tham khảo, không phải chỉ dẫn.
- Ngày do nhà cung cấp ước tính không được coi là ngày sự kiện. Kết luận về
  lịch phải có khoảng ngày trong nguồn phù hợp, không suy ra từ ngày truy cập.
- Hết hạn mức/lỗi khóa: trả lỗi rõ, không thử lại, không chuyển sang trả phí.
  Việc tài khoản thực sự không bật trả theo lượt cần người sở hữu kiểm trên
  Tavily; mã không thể xác nhận chế độ thanh toán chỉ từ khóa.

## Bằng chứng hiện có và bước còn lại

Kiểm trong máy: 119 phép kiểm cấu hình, nguồn, suy luận, bảo mật và định
tuyến đạt trong 5,77 giây. Bao gồm khóa được che, không đi theo yêu cầu đọc
trang, URL/chuyển hướng nội bộ, dữ liệu quá lớn, lỗi mạng và các mã lỗi
301/401/429/432/433/503. Không gọi Tavily/Gemini thật trong bộ này.

Đợt kiểm gộp cuối thêm thông tin cập nhật, điều kiện cuối khóa và quét bí mật:
186 đạt trong 14,87 giây. Kiểm quy tắc mã máy chủ/script và khoảng trắng đạt;
quét 565 tệp Git thấy được không phát hiện bí mật. Các bộ có phần trùng nhau,
không cộng số lượng và không dùng chúng làm điểm chất lượng câu trả lời.

Chưa có khóa Tavily để kiểm nguồn thật; chưa đóng A/E/F hoặc chấm điểm.
Tiếp theo chỉ kiểm nguồn/câu trả lời của các ca còn thiếu trong bộ đã khóa,
ưu tiên company-02 và U01; không chạy lại phần bộ nhớ đã có biên nhận hợp lệ.
Nếu nội dung thật không đạt thì giữ trạng thái chưa đạt, không coi CI hoặc
kiểm giả lập là nghiệm thu nghiệp vụ.

Tài liệu API đã đối chiếu ngày 08/10/2026:
https://docs.tavily.com/documentation/api-reference/endpoint/search và
https://docs.tavily.com/documentation/api-credits.
