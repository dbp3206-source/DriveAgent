# Veridra — nền tảng sản phẩm đã chốt

Phiên bản định hướng: 01/10/2026. Đây là bản chuẩn về đối tượng, nghiệp vụ, phương pháp và giá trị; không phải chứng nhận mọi hành vi đã được triển khai hoặc nghiệm thu. Danh sách triển khai hiện hành: [ACCEPTANCE-CHECKLIST.md](ACCEPTANCE-CHECKLIST.md).

## 1. Một định vị duy nhất

**Veridra — Trợ lý chuẩn bị tư vấn khách hàng doanh nghiệp.**

Veridra giúp chuyên viên tư vấn giải pháp AI/phần mềm biến yêu cầu qua email, hồ sơ tài liệu và thông tin doanh nghiệp thành báo cáo trước cuộc hẹn, câu hỏi cần làm rõ và phản hồi được duyệt.

- Người dùng chính: chuyên viên tư vấn giải pháp AI/phần mềm trước bán hàng.
- Nghiệp vụ: tiếp nhận yêu cầu, chuẩn bị và tiếp nối cuộc hẹn tư vấn.
- Bối cảnh: nhóm cung cấp dịch vụ phần mềm sử dụng Gmail, Drive và Calendar.
- Quy mô thử nghiệm: tối đa bốn người được mời; mỗi người có tài khoản, dữ liệu và khóa Gemini riêng. Không xây cộng tác nhóm chỉ vì có bốn tài khoản.
- Người hưởng lợi trực tiếp: người chuẩn bị cuộc hẹn. Người quyết định mua và mức sẵn sàng trả tiền chưa được xác minh; không bịa mô hình doanh thu hoặc quy mô thị trường.
- Lời hứa giá trị cần chứng minh: giảm công chuẩn bị và sửa lại, làm rõ điều còn thiếu, giữ bằng chứng và quyền duyệt hành động.

Không phải hệ thống quản lý bán hàng, quản trị dự án, quản lý cuộc sống hoặc giải pháp chuyên ngành. Khách hàng thuộc nhiều ngành không đồng nghĩa Veridra giải quyết nghiệp vụ chuyên ngành của họ.

## 2. Vấn đề trước, công nghệ sau

Khi nhận yêu cầu tìm hiểu giải pháp, người tư vấn phải tự tìm, ghép và kiểm tra thông tin từ thư, hồ sơ, Internet và lịch. Đầu ra thường là báo cáo chuẩn bị, câu hỏi trao đổi và phản hồi. Giả thuyết vấn đề:

| Mã | Trở ngại | Câu hỏi phải giải quyết | Giá trị cần kiểm chứng |
|---|---|---|---|
| P1 | Yêu cầu chưa rõ, thư/attachment phân tán | Khách hàng muốn gì; điều nào đã nói rõ, điều nào chưa biết? | Giảm bỏ sót và hiểu sai |
| P2 | Thiếu bối cảnh hoặc dùng thông tin cũ | Nguồn nào liên quan và còn phù hợp với cuộc hẹn? | Giảm công tìm và kiểm tra |
| P3 | Tóm tắt nhiều nhưng chưa phục vụ trao đổi | Cần hỏi hoặc xác nhận điều gì để làm việc tiếp? | Báo cáo sử dụng được, không chỉ đủ chữ |
| P4 | Phản hồi/lưu kết quả thủ công, dễ làm lại | Cần làm hành động nào, ai duyệt, đã thực hiện chưa? | Giảm sao chép, sai nơi và hành động trùng |

Các vấn đề này có căn cứ từ yêu cầu ProtonX và tình huống sản phẩm đã gặp; chưa được coi là khảo sát thị trường. Không tuyên bố chưa ai giải quyết hoặc Veridra tốt hơn đối thủ khi chưa so sánh.

Đơn vị giá trị là **một cuộc hẹn được chuẩn bị và một bước tiếp theo được xử lý đúng**, không phải một tin nhắn, một model call hay một agent.

## 3. Phương pháp luận: hai lớp, không dùng tên khung làm trang trí

### Lớp thiết kế sản phẩm

Xác định công việc khách hàng cần hoàn thành và bản đồ giá trị để chọn đúng vấn đề. Kiểm thử giả thuyết bằng cùng dữ liệu, yêu cầu và điều kiện hoàn thành. Ưu tiên phần chặn công việc hoặc gây rủi ro trước; chỉ dùng điểm RICE khi có dữ liệu về tác động/công sức, không điền số giả.

Tài liệu tham khảo: [Strategyn — công việc cần hoàn thành](https://strategyn.com/jobs-to-be-done-template/), [Strategyzer — kiểm tra giả thuyết quan trọng](https://www.strategyzer.com/library/how-to-test-your-idea-start-with-the-most-critical-hypotheses), [Intercom — ưu tiên](https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers/).

### Lớp nghiệp vụ trong sản phẩm

**Hiện trạng → vấn đề → ảnh hưởng cần xác nhận → kết quả khách hàng mong muốn.** Tham khảo bốn nhóm câu hỏi của SPIN từ [Huthwaite](https://www.huthwaiteinternational.com/spin-methodology). Đây là cách chuẩn bị câu hỏi tư vấn, không phải triển khai toàn bộ phương pháp bán hàng, chứng nhận đào tạo hoặc sử dụng tài liệu/template thương mại của bên thứ ba.

- Hiện trạng: quy trình, công cụ và bối cảnh đã biết từ nguồn; không hỏi lại vô ích.
- Vấn đề: khó khăn khách hàng đã nêu; nếu chỉ có mong muốn chung thì đề xuất câu hỏi làm rõ.
- Ảnh hưởng: câu hỏi về hậu quả cần xác nhận; không tự gán chi phí, doanh thu hay mức cấp bách.
- Kết quả mong muốn: tiêu chí khách hàng dùng để đánh giá cải thiện; chưa biết thì hỏi, không tự hứa ROI.

Ví dụ khách hàng viết “muốn AI quản lý tài liệu”: chưa đủ kết luận cần chatbot. Câu hỏi phù hợp: khó tìm tài liệu nào; mất thời gian ở bước nào; sai sót ảnh hưởng gì; cải thiện cần đo bằng tiêu chí nào. Không ép mọi báo cáo phải có đủ bốn mục nếu không liên quan.

Phân tích bằng chứng là quy tắc xuyên suốt: **dữ kiện / suy luận / giả định / chưa biết**. Thông tin thiếu phải được biểu diễn như khoảng trống, không bịa nội dung cho đầy mẫu.

## 4. Xương sống xử lý thống nhất

| Bước | Câu hỏi nghiệp vụ | Đầu ra kiểm được | Thành phần hỗ trợ | Quy tắc dừng/chuyển |
|---|---|---|---|---|
| 1. Chốt phạm vi | Cuộc trao đổi nào, mục tiêu gì, nguồn nào được phép? | Yêu cầu, công ty, thread/tài liệu/lịch liên quan | Chat, Email Agent | Thiếu định danh làm sai nguồn: hỏi lại |
| 2. Phân rã | Cần biết gì để chuẩn bị được cuộc hẹn? | Câu hỏi đã trả lời và còn thiếu | Điều phối, quy trình dùng lại | Không thêm nghiên cứu không phục vụ mục tiêu |
| 3. Lấy bằng chứng | Nguồn nào trả lời từng câu hỏi? | Nội dung nguồn, vị trí, ngày và thời điểm lấy | Gmail, Drive/local, Web, Company Info, Calendar | Thiếu quyền/nguồn: báo rõ, không bịa |
| 4. Đối soát | Bằng chứng có đúng thời điểm, mâu thuẫn hoặc cần tính toán? | Dữ kiện xác nhận, phép tính, giả định và khoảng trống | Công cụ lọc/tính, kiểm tra đầu ra | Không coi trích dẫn tồn tại là kết luận đúng |
| 5. Tổng hợp | Người tư vấn cần mang gì vào cuộc hẹn? | Báo cáo, câu hỏi làm rõ, điểm cần chú ý | Report Agent | Đầu ra không bám mục đích: sửa trong ngân sách |
| 6. Chuẩn bị hành động | Cần phản hồi hoặc lưu gì, cho ai, ở đâu? | Bản xem trước với nội dung/nơi nhận cụ thể | Gmail, Docs/Sheets, Human Approval | Không đủ duyệt: chưa thực hiện |
| 7. Thực hiện và đọc lại | Hành động thực sự đã diễn ra đúng chưa? | Biên nhận và kết quả kiểm tra | Công cụ có kiểm soát, operation ledger | Chưa rõ trạng thái: đối soát, không phát lại mù |
| 8. Giữ và tiếp nối | Lần sau dùng lại gì; thông tin nào cần cập nhật? | Kết quả cùng nguồn/bối cảnh, ngữ cảnh được xác nhận | Artifacts, Company Info, Memory, Skills | Thông tin cũ không tự thành sự thật hiện tại |

Đây là quy tắc đầu ra/thực thi quan sát được, không phải yêu cầu hiển thị suy nghĩ nội bộ của model. Không bắt mỗi lượt đi qua tất cả agent; thao tác lọc ngày, phân trang và tính toán dùng bước xác định khi phù hợp.

Không tự dựng module quản lý khách hàng mới. “Hồ sơ cuộc hẹn” là quan hệ nghiệp vụ giữa yêu cầu, nguồn, lịch, báo cáo và hành động; tận dụng cấu trúc hiện có rồi mới sửa đúng phần thiếu.

## 5. Ba quy trình chính

### W1 — Tiếp nhận đầu ngày

Email mới → nhận diện yêu cầu cần chú ý → tìm hồ sơ công ty đã có → đối chiếu lịch → bản tổng hợp yêu cầu/thông tin thiếu/việc chuẩn bị. Phân biệt việc người dùng phải làm và job hệ thống xử lý. Không tự tạo lịch hoặc cam kết thời hạn.

### W2 — Chuẩn bị trước cuộc hẹn

Cuộc hẹn đã xác nhận + chuỗi email + tài liệu được chọn → bổ sung nguồn doanh nghiệp/tin phù hợp → báo cáo trước hẹn. Trigger tự động phải bền và đúng sự kiện; thao tác yêu cầu trực tiếp vẫn dùng được nếu trigger chưa sẵn sàng.

Báo cáo gồm: bối cảnh; yêu cầu đã xác nhận; doanh nghiệp/ngành/sản phẩm/quy mô khi có nguồn; người liên hệ từ nguồn có thẩm quyền; thông tin mới liên quan; phân tích; điều chưa rõ; câu hỏi cần hỏi; việc tiếp theo; nguồn và trạng thái hành động. Không bắt số lượng nguồn cố định. Mốc tin 30 ngày được dùng khi testcase/yêu cầu cần tin gần đây, không làm nguồn nền tảng cũ tự trở thành vô giá trị.

### W3 — Phản hồi và lưu kết quả

Báo cáo hoặc ghi chú được người dùng cung cấp → bản nháp phản hồi/tài liệu → duyệt → thực hiện → đọc lại → lưu kết quả để tiếp nối. Không tự ghi âm, dự họp hoặc biết kết quả cuộc họp. Người dùng phải cung cấp nội dung mới.

Calendar hiện được công bố là đọc lịch, không thay đổi lịch. Không thêm tạo/sửa lịch vào gate chỉ vì nghe phù hợp; yêu cầu chuẩn bị trước họp không bắt buộc chức năng này.

## 6. Đầu ra và ranh giới

Ba đầu ra chính: **bản xác định yêu cầu / báo cáo trước cuộc hẹn / bản nháp phản hồi hoặc tài liệu được duyệt**.

Giữ cốt lõi: Gmail, Drive/local, web, Calendar đọc, Company Info, báo cáo và duyệt. Giữ hỗ trợ: Skills, Memory, kết quả đã lưu, quyền, quota, nhật ký và quan sát. Bảy agent ProtonX và các kiểm soát kỹ thuật vẫn phải có bằng chứng thật.

Không mở rộng: định vị sinh viên/học tập; quản lý cuộc sống; danh sách việc học; CRM, scoring cơ hội, báo giá/hợp đồng; giải pháp chuyên ngành; agent hoặc dashboard chỉ để trình diễn. Khả năng đọc/tính dữ liệu ngành vẫn được giữ, nhưng không quảng bá thành nghiệp vụ chuyên ngành đã chứng nhận.

OCR loại bỏ. PDF có text tối đa theo giới hạn đã chốt giữ khi test đạt; PDF ảnh/lỗi/khóa phải trả trạng thái đúng. Cả sáu PDF người dùng cung cấp vẫn nằm trong manifest; không tính file scan từ chối đúng là ca đọc thành công.

Cloud miễn phí vẫn có ngủ/khởi động lại và lỗi dịch vụ ngoài. Không bảo đảm luôn bật, truy cập tức thì hay Gemini luôn thành công. Không dùng paid fallback hoặc khoá người khác. URL beta và đăng ký đại trà là hai phạm vi khác nhau.

## 7. Concept, ngôn ngữ và hành trình giới thiệu

Giữ tên Veridra, logo và hệ thiết kế. Hình ảnh chủ đạo: thông tin có nguồn được nối thành báo cáo và hành động kiểm soát được; không cần tạo lại brand hoặc vẽ thêm kiến trúc cho đẹp.

- Trang chủ: “Chuẩn bị cuộc hẹn với khách hàng.”
- Ba lối vào: “Đọc yêu cầu khách hàng” / “Chuẩn bị báo cáo trước cuộc hẹn” / “Soạn phản hồi và lưu kết quả”.
- Trạng thái dễ hiểu: “Đang đọc thư”, “Đang đối chiếu hồ sơ”, “Chưa xác nhận”, “Bản nháp”, “Chờ bạn duyệt”, “Đã kiểm tra kết quả”.
- Nguồn và chi tiết vận hành là lớp bổ sung; người dùng không cần chọn agent/giao thức để bắt đầu.
- Pending chỉ hiển thị sự kiện thực thi thật. Một canvas caro sáng/tối; chuyển động tham khảo GetLayers là hoàn thiện có giới hạn, không dự án thiết kế mới.

Demo 10 phút: tình huống email → trở ngại chuẩn bị → W2 chạy thật → kiểm bằng chứng và câu hỏi → W3 duyệt/đọc lại → kiến trúc bảy agent và kiểm soát → kết quả đo/giới hạn. W1 chứng minh bổ sung bằng job thật. Không ghép demo tách rời để tạo cảm giác một chuỗi đã chạy.

## 8. Cách chứng minh giá trị

Chỉ số chính: **thời gian đến báo cáo đủ điều kiện sử dụng, gồm kiểm tra và sửa**. Báo cáo thất bại phải tính vào tỷ lệ thất bại; không loại khỏi báo cáo chỉ để thời gian đẹp hơn.

Chỉ số bổ sung: đúng yêu cầu; đúng bằng chứng; độ đầy đủ theo mục tiêu; số lỗi nội dung quan trọng/công sửa; hành động đúng và không trùng; khả năng tiếp nối.

**Khả năng tiếp nối là chất lượng cốt lõi của Chat:** giữ đúng khách hàng/nguồn/ràng buộc trong cùng cuộc trò chuyện, thay đúng khi người dùng sửa và không lẫn với phiên khác. Bộ nhớ dài hạn chỉ lưu có chủ đích, có quản lý sửa/quên và quyền riêng tư; không đồng nghĩa lưu mọi lời thoại. Nghiệm thu theo [MEMORY-QUALITY-PLAN.md](MEMORY-QUALITY-PLAN.md), bằng hội thoại nhiều lượt gắn W1–W3 thay vì chỉ kiểm từng câu trả lời hoặc API lưu bộ nhớ.

So sánh với cách hiện tại của cùng người tư vấn trên dữ liệu tương đương. Ít nhất hai công việc đại diện chạy theo cặp, đổi thứ tự/case tương đương để giảm hiệu ứng đã biết đáp án; ghi khác biệt điều kiện. Mẫu nhỏ chỉ là bằng chứng thăm dò, không suy rộng thành tiết kiệm toàn thị trường hay tăng doanh thu.

Ngưỡng điểm >=9,2/10 giữ theo plan, nhóm quan trọng >=9, không P0/P1. Không có số liệu live đầy đủ thì chưa tính điểm toàn sản phẩm. Điểm offline không chứng nhận nghiệp vụ; chữ “pending” không chứng minh đã chặn gửi; số nguồn không chứng minh tính đúng.

Mỗi chức năng mới phải trả lời: giải quyết P1–P4 nào, phục vụ W1–W3 nào, đầu ra/metric nào thay đổi, bằng chứng tác động là gì. Nếu không, chỉ được làm khi bắt buộc ProtonX/an toàn/phát hành; còn lại hoãn.

## 9. Bằng chứng hiện tại và phần cần chuyển thành mã

Ngày 01/10/2026 đã chạy lại hồi quy: định tuyến 12/12, bộ chấm 12/12, hợp đồng mẫu 16/16, đối kháng 160/160; 35 test tập trung đạt. Không gọi Gemini/Google thật cho kết quả này.

Mã hiện có cung cấp các thành phần chính, nhưng Home vẫn nói học tập/ngân sách; bộ đo công ty còn chấm theo 12 nguồn và 42 giây, dựa marker và tự báo mâu thuẫn; runner không đi qua đầy đủ W1–W3. Các vấn đề này chặn việc nhận kết quả cũ làm chứng nhận định hướng mới.

Phương pháp và nội dung ở trên đã chốt trong tài liệu, **chưa tự trở thành hành vi chạy trong sản phẩm**. Các bước thực hiện tiếp theo được giới hạn bởi checklist hiện hành.
