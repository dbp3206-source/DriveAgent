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
- Câu hỏi web độc lập: tổng hợp một lần bằng Gemini hiện có, kiểm trích
  đoạn và nguồn. Báo cáo tư vấn: công cụ chỉ thu văn bản gốc, bộ điều phối
  tổng hợp báo cáo cuối; bỏ lượt tổng hợp trung gian. Cờ chọn đường này do
  máy chủ đặt, không phải tham số người dùng. Lượt sửa cấu trúc nếu thật sự
  cần vẫn có giới hạn; không tuyên bố mọi câu hỏi luôn chỉ một lượt.
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

Cập nhật sau 13:55 UTC ngày 08/10: U01 đã trả lời nội bộ đúng khoảng ngày
và kết luận, trích đoạn được kiểm trên đúng nguồn trả về. Company-02 trả
báo cáo sau một lượt mô hình, nhưng còn thiếu quy mô và giới hạn tin mới;
đã làm rõ hướng dẫn báo cáo, chưa kiểm thật sau sửa. Ngân sách bảo vệ tại
máy đã 16/16, không gọi thêm hoặc đặt lại. Không phải lỗi 503 đang tiếp
diễn. Chưa triển khai Tavily lên Render hoặc cấp đạt A/E/F; xem trạng thái
hiện hành ở đầu INTERNAL-ANSWER-REVIEW-20261008.md. Các số đo dưới đây là
lịch sử theo đợt, không mô tả ngân sách còn lại hiện tại.

Kiểm trong máy: 119 phép kiểm cấu hình, nguồn, suy luận, bảo mật và định
tuyến đạt trong 5,77 giây. Bao gồm khóa được che, không đi theo yêu cầu đọc
trang, URL/chuyển hướng nội bộ, dữ liệu quá lớn, lỗi mạng và các mã lỗi
301/401/429/432/433/503. Không gọi Tavily/Gemini thật trong bộ này.

Đợt kiểm gộp cuối thêm thông tin cập nhật, điều kiện cuối khóa và quét bí mật:
186 đạt trong 14,87 giây. Kiểm quy tắc mã máy chủ/script và khoảng trắng đạt;
quét 565 tệp Git thấy được không phát hiện bí mật. Các bộ có phần trùng nhau,
không cộng số lượng và không dùng chúng làm điểm chất lượng câu trả lời.

Bản mã ứng dụng `53c96eeada85e322ed45055030dc60db0d294f9f` đã qua kiểm
tự động GitHub `37762947341`; hai công việc PostgreSQL và verify đều hoàn
tất thành công. Chưa triển khai bản này hoặc cấp đạt nghiệp vụ từ CI.

Đã đồng bộ bộ kiểm nguồn `qa_protonx_source_probe.py` với nhà cung cấp đang
cấu hình. Tên ca sai bị chặn trước gửi yêu cầu; trang của bên thứ ba không
được gán là website chính thức. Ca U01 lấy nguyên câu hỏi trong bộ đã khóa.
Ba phép kiểm của bộ đo đạt trong 2,49 giây, không gọi mạng/mô hình. Khi có
khóa, dùng đúng một lần `scripts/qa_protonx_source_probe.py company-02 U01`
để thu nguồn công khai trước khi dành lượt Gemini cho chất lượng câu trả lời.
Biên nhận văn bản nguồn và thời gian nằm riêng trong thư mục QA bị Git bỏ
qua. Nhãn `collected` chỉ nghĩa đã thu dữ liệu, không nghĩa nghiệm thu đạt.

Đã nhận cấu hình khóa tại máy và kiểm nguồn thật ngày 08/10, không đọc hoặc
công bố khóa. U01 tìm được văn bản từ Hội đồng Olympic châu Á và Chính phủ
Nhật Bản chứa khoảng ngày sự kiện. Đây là thu nguồn, chưa phải nghiệm thu
câu trả lời. Chọn trang chính thức người dùng đã đưa trước tài liệu phụ;
truy vấn giữ yêu cầu nguồn chính thức/khoảng ngày, bỏ cụm hỏi đóng không
cần cho tìm kiếm. Không gắn cứng tên sự kiện, ngày hoặc URL vào sản phẩm.

Báo cáo company-02 chạy bộ điều phối và công cụ thật trong phiên thử riêng:
đọc sáu nguồn, đúng một lượt Gemini, không đọc dữ liệu riêng hoặc ghi Google.
Google trả 503 UNAVAILABLE, thông báo mô hình đang quá tải; toàn lượt 10,656
giây, chưa có báo cáo để chấm. Không chạy lại, không đặt lại hạn mức. Bộ đếm
tại máy tăng đúng 10 → 11/16; còn năm lượt, không phải hết ngân sách.
Biên nhận tại design-work/qa/acceptance-20261008/tavily-pipeline-cuxr0fl_/result.json;
mã 503 được quan sát trực tiếp trong đầu ra thực thi, không suy từ biên nhận
chỉ ghi chưa nghiệm thu. Đường web đã thu nguồn, nhưng chất lượng cuối cần
kiểm khi mô hình hoạt động trở lại. A/E/F vẫn chưa đóng.

Tiếp theo chỉ kiểm câu trả lời của các ca còn thiếu trong bộ đã khóa;
không chạy lại phần bộ nhớ đã có biên nhận hợp lệ.
Nếu nội dung thật không đạt thì giữ trạng thái chưa đạt, không coi CI hoặc
kiểm giả lập là nghiệm thu nghiệp vụ.

Tài liệu API đã đối chiếu ngày 08/10/2026:
https://docs.tavily.com/documentation/api-reference/endpoint/search và
https://docs.tavily.com/documentation/api-credits.
