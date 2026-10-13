# Veridra — nền tảng sản phẩm

Định hướng hiện hành: 13/10/2026. Thay thế định hướng tư vấn trước bán hàng, BA/HR và ngân hàng trước đây. Lịch sử kiểm thử vẫn giữ nguyên ngày, phiên bản và phạm vi; thay đổi định vị không biến ca chưa đạt thành đạt.

## 1. Sản phẩm dành cho ai, làm được việc gì?

**Veridra là trợ lý AI cho công việc nội bộ: tìm hiểu thông tin, nắm tình hình, phân tích phương án, chuẩn bị cuộc họp và hoàn thiện nội dung từ các nguồn được phép.**

Người dùng thường xuyên xử lý tài liệu, thư và họp, phải tự tổng hợp để viết báo cáo, đề xuất hoặc phản hồi. Không giới hạn ngành hoặc chức danh; cũng không hứa hiểu mọi nghiệp vụ chuyên ngành. Bản đầu giới hạn tối đa bốn tài khoản được mời, dữ liệu riêng. Đây chưa phải không gian cộng tác và quản trị toàn doanh nghiệp.

Vấn đề cần giải quyết: thông tin rời rạc, mất công tìm và đối chiếu; tóm tắt chưa giúp chọn hướng làm; dữ kiện thay đổi khiến phải sửa nhiều nơi; kết quả khó tiếp nối hoặc dễ bị hiểu là đã thực hiện. Đây là giả thuyết cần đo với người dùng thật, không phải kết quả khảo sát thị trường đã xác nhận.

Đơn vị giá trị là **một công việc được hoàn thành và chấp nhận**, tính cả tìm nguồn, chờ, kiểm tra, sửa và hỗ trợ — không phải số tin nhắn, số vai trò hoặc độ dài câu trả lời.

## 2. Năm nhóm việc, cùng một trợ lý

| Nhóm việc | Đầu ra có ích |
|---|---|
| Hiểu tài liệu | Trả lời trực tiếp, chỉ nguồn, phân biệt bản có hiệu lực với bản nháp, chỉ ra phần khác hoặc thiếu |
| Nắm tình hình | Điều đã chốt, còn mở, cần xác nhận; người và hạn chỉ ghi khi nguồn có |
| Phân tích và đề xuất | Hướng khả thi, đánh đổi, ưu tiên có lý do và một hoặc hai bước tiếp |
| Chuẩn bị cuộc họp | Mục tiêu, câu hỏi, điểm cần quyết định; cập nhật từ ghi chú người dùng cung cấp |
| Soạn và hoàn thiện | Bản nháp đúng mục đích, sửa được; trạng thái lưu hoặc tạo bên ngoài phải đúng thực tế |

Năm nhóm là lối bắt đầu công việc, không phải năm hệ thống hoặc năm vòng gọi mô hình. Câu hỏi đơn giản cần câu trả lời ngắn đủ; không ép thêm ba phương án. Khi tham vấn, trợ lý cần giúp chọn hướng, không chỉ liệt kê thông tin. Nếu chỉ một hướng khả thi thì giải thích rõ, không tạo lựa chọn yếu cho đủ số.

## 3. Ba hành trình để kiểm chứng

| Hành trình | Chuỗi công việc | Giới hạn |
|---|---|---|
| A — Chọn nhà cung cấp | Ba báo giá → đối chiếu → đổi ngân sách → sửa đề xuất → soạn → duyệt lưu | Dữ liệu giả lập; không tự mua hoặc ký hợp đồng |
| B — Họp dự án | Thư/lịch/tài liệu được chọn → nắm tình hình → chuẩn bị → nhận ghi chú sau họp → soạn tổng kết | Không tự nghe họp, gửi thư hoặc sửa lịch |
| C — Áp dụng hướng dẫn | Bản có hiệu lực + bản nháp → hỏi cách làm → giải quyết mâu thuẫn → danh sách bước → nhớ/dùng lại/quên | Không coi bản mới nhất tự động là bản có hiệu lực |

Bộ chuẩn hiện hành: [dữ liệu giả lập và mười ca](verification/internal-assistant/README.md). Bộ chuẩn cũ vẫn là bằng chứng lịch sử, không tự động đại diện cho hướng mới.

## 4. Cách trợ lý xử lý

Hiểu việc cần làm → chọn đúng nguồn → xử lý phù hợp → kiểm kết quả → trả lời hoặc trình duyệt → tiếp nối khi dữ kiện đổi.

- Làm phần đã đủ thông tin; chỉ hỏi điểm thiếu làm thay đổi kết quả hoặc quyền.
- Tách dữ kiện, nhận định, giả định và phần chưa biết. Không bịa nguồn, số liệu, người phụ trách hoặc việc đã làm.
- Chủ động đề xuất bước có ích trong phạm vi, không biến đề xuất thành lệnh thực hiện.
- Đầu vào mới thay phần cũ có liên quan; đổi hồ sơ phải tách phạm vi. Nguồn bị cấm vẫn bị cấm khi hỏi tiếp.
- Ghi nhớ dài hạn do người dùng chủ động chọn; không tự giữ mọi nội dung hội thoại.
- Ghi bên ngoài cần nội dung và đích cụ thể, xem trước, duyệt, thực hiện và đọc lại. Sửa bản đã duyệt thì cần duyệt lại. Kết quả chưa rõ phải đối soát, không phát lại mù.

Đặc tả thực thi: [hợp đồng trợ lý](ASSISTANT-CONTRACT.md). Trang giải thích “Cách trợ lý hoạt động” làm cuối, sau khi luồng chức năng ổn định; phải thông báo và nhận góp ý của chủ sản phẩm trước khi chốt.

## 5. Phạm vi và phần không hứa

Nguồn bản đầu: tệp nhập loại đã kiểm, PDF có chữ, Drive, Gmail/lịch được phép và web công khai khi cần. Không bắt mọi công việc dùng Google hoặc tìm web. Chỉ quảng bá định dạng xuất và thao tác đã được đọc lại thành công.

Hành động phát hành dự kiến: trả lời, soạn nháp, lưu kết quả trong Veridra; tạo Google Doc theo vai trò/quyền và duyệt đã kiểm. Mã có khả năng rộng hơn không đồng nghĩa đã được phép sử dụng. Gửi thư, sửa lịch, sửa tài liệu thật và chia sẻ ra ngoài không thuộc lời hứa bản đầu.

Hoãn: OCR, bảng lớn/đối soát chuyên sâu, ghi âm họp, quản lý dự án/giao việc tự động, cộng tác tổ chức, kết nối doanh nghiệp mới, nhiều nhà cung cấp mô hình, hạ tầng vi dịch vụ và mô hình chuyên ngành. Hẹn giờ/MCP/A2A/bảy vai trò giữ hồ sơ học phần và khu vực nâng cao; không mặc định gọi hết hoặc coi học phần đã hoàn tất chỉ vì có mã.

Giữ kiến trúc và các kết nối hiện có. Không thêm công nghệ chỉ để sơ đồ trông lớn hơn. Phần không giúp A/B/C và không bắt buộc cho an toàn/vận hành thì không thêm trong bản này.

## 6. Nghiệm thu kỹ thuật khác chứng minh đầu tư

Nghiệm thu kỹ thuật cần kết quả đúng, hoàn thành việc, đúng nguồn/quyền, phiên thu hồi bị từ chối, dữ liệu khôi phục đọc được, không chờ vô hạn hoặc ghi trùng, và bản trên GitHub/URL khớp bản đã kiểm. Kiểm ngoại tuyến không thay nghiệm thu nguồn thật. Trạng thái theo dõi: [sổ triển khai](PRODUCTION-EXECUTION-20261013.md).

Quyết định đầu tư cần thêm năm công việc so cặp và ba người dùng trong mười ngày làm việc. Tính cả ca thất bại, công kiểm/sửa/hỗ trợ, mức dùng lại và chi phí trên công việc được chấp nhận. Mục tiêu thăm dò: ít nhất bốn trong năm kết quả được chấp nhận, không sai trọng yếu, trung vị tổng thời gian giảm ít nhất 20%. Đây là ngưỡng thử chưa được chứng minh, không phải thành tích.

Trạng thái căn cứ gần nhất là UAT giới hạn, còn phát triển. Không gọi sản phẩm “Production toàn doanh nghiệp” khi mới tối đa bốn tài khoản hoặc thiếu bằng chứng vận hành. Không tự đặt điểm tổng hợp để che phần chưa kiểm. Kế hoạch giữ cố định mười ca và mười sáu gói; thay đổi phạm vi cần quyết định riêng.
