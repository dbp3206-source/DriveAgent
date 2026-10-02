# Veridra — 90 tiêu chí chi tiết nghiệm thu toàn sản phẩm

Bản chốt ngày 01/10/2026. Dùng cùng [18 điều kiện nghiệm thu](ACCEPTANCE-CHECKLIST.md) và [định hướng sản phẩm](PRODUCT-FOUNDATION.md). Đây là bản chi tiết hiện hành, giữ đủ 90 mã để không mất yêu cầu khi gom nhóm; 18 điều kiện là cấp quản lý, không thay thế các tiêu chí này. Không phải 90 chức năng mới hoặc 90 lỗi đã chứng minh.

Mỗi mục cần kết quả, môi trường/bản mã, bước tái hiện, kỳ vọng/thực tế và liên kết bằng chứng. Chưa chạy không được đánh dấu đạt. Mục áp dụng vẫn bắt buộc trừ phần loại bỏ công khai; các ghi chú lịch sử trong checklist tổng không chứng nhận bản phát hành mới.

Bộ nhớ ngắn/dài hạn: áp dụng [MEMORY-QUALITY-PLAN.md](MEMORY-QUALITY-PLAN.md) tại D03/D10/F05/F06/H01/H07 và các chuỗi G/K liên quan. Không thay thế tải trang, nguồn, quyền, giao diện hay phát hành. Tình huống ngành trong D08 là kiểm khả năng tính dữ liệu, không đổi định vị thành giải pháp chuyên ngành. Ngưỡng tốc độ/điểm và thứ tự làm dùng bản checklist tổng hiện hành.

### A. Chốt phiên bản và chuẩn bị — làm trước tiên

- [ ] **A01 — Một bản nguồn duy nhất.** Chốt mã ứng viên, ghi nhánh, mã Git, phiên bản cấu hình/dữ liệu và mã ảnh Docker. Liệt kê thay đổi hiện còn thiếu; không mở rộng thêm chức năng ngoài danh sách khi đang nghiệm thu.
- [ ] **A02 — Đối chiếu yêu cầu cuối khóa.** Mỗi yêu cầu ProtonX có màn hình/đường thực thi, ca dương, ca từ chối và bằng chứng. Ghi Render là phương án thay thế VPS đã thống nhất, OCR là phần bị loại.
- [ ] **A03 — Bảo toàn thay đổi.** Kiểm tra lại thay đổi được giữ trong stash `local-design-qa-preserved-20261001` và tệp bỏ qua; không xóa hoặc gộp nhầm. Thư mục mã sạch không thay thế rà dữ liệu riêng.
- [ ] **A04 — Bộ mẫu hợp lệ.** Lập danh mục đủ sáu PDF và mẫu email/lịch/bảng/quy trình; có nguồn, ngày lấy, checksum, quyền sử dụng và đáp án đối soát. Dữ liệu giả lập phải được ghi nhãn.
- [ ] **A05 — Khóa cách chấm.** Chốt trọng số, ngưỡng, ngân sách miễn phí, số mẫu và ca chưa dùng khi sửa lỗi trước khi chạy đo; không chỉnh ngưỡng sau khi thấy điểm thấp.

### B. Tải trang, tài nguyên và tình trạng dịch vụ — ưu tiên cao nhất

- [ ] **B01 — Tái hiện chậm từ URL thật.** Đo mở `/`, `/#/home`, `/#/chat`, `/#/audit`, `/#/settings`, URL có `?connected=1`, tab mới và tải lại. Ghi thời điểm giao diện dùng được, không chỉ thời gian HTTP 200.
- [ ] **B02 — Tách nguyên nhân chờ.** Ghi riêng đánh thức Render, nạp Python, kết nối DB/kho tệp, đăng nhập, tải JS/CSS và gọi dữ liệu màn hình. Lưu dấu vết trình duyệt; không suy diễn từ một lần đo.
- [ ] **B03 — Thời hạn chờ và khôi phục.** Giả lập mạng treo/mất mạng, DB chậm và trả lỗi. Mọi thao tác có thời hạn phù hợp, hủy/đóng màn hình an toàn và nút thử lại; không màn hình trắng hoặc vòng chờ vô hạn; không tự gửi lại thao tác ghi.
- [ ] **B04 — Giảm chi phí khởi động.** Đo và tách nạp sớm MarkItDown, Qdrant, backend so sánh và thư viện không cần cho màn hình đầu. Không làm mất chức năng khi nạp muộn; kiểm tra cả lần dùng đầu tiên.
- [ ] **B05 — Sẵn sàng thật và phục hồi kho tệp.** Phân biệt máy chủ còn sống với chức năng đã sẵn sàng. Ngắt/phục hồi kho tệp sau khởi động phải được phản ánh đúng; kho bị hỏng chỉ khóa chức năng liên quan, không làm Chat mất dữ liệu.
- [ ] **B06 — Kho riêng tư trong mọi nhánh.** Kiểm tra kho tồn tại/công khai, chưa có kho, 403, 409 do tạo đồng thời và lỗi tạm. Không chấp nhận kho công khai; không vòng lặp tạo kho trên mọi lần khởi động bình thường.
- [ ] **B07 — Vừa tài nguyên miễn phí.** Đo RAM/CPU, số kết nối DB, dung lượng ảnh Docker và ổ tạm khi Chat + nhập PDF. Chạy liên tiếp ít nhất 30 phút và kiểm tra không tăng RAM không hồi phục, không bị hệ thống dừng do hết bộ nhớ. Không yêu cầu cài stack Docker nặng không cần thiết trên máy người dùng.
- [ ] **B08 — Đạt mục tiêu tốc độ đã duyệt.** Đo ít nhất 20 lượt đang hoạt động và 3 lượt khởi động sau ngủ; ghi trung vị, phân vị 95 và trường hợp chậm nhất. Không trộn thời gian ngủ vào thời gian xử lý Chat; không gọi xử lý chờ tốt là đã loại bỏ ngủ miễn phí.

### C. Đăng nhập, quyền và khóa Gemini riêng

- [ ] **C01 — Bốn người thật được mời.** Mỗi tài khoản đăng nhập, bị chặn nếu ngoài danh sách; chủ được cấu hình rõ, không lấy người đầu tiên làm chủ. Từng người tự xác thực, không yêu cầu gửi bí mật trong Chat.
- [ ] **C02 — Google đúng quyền.** Kiểm tra HTTPS callback, hủy cấp quyền, thiếu quyền, token hết hạn, kết nối lại, đăng xuất và chuyển tài khoản. Không hiện kết nối thành công nếu API cần dùng bị từ chối.
- [ ] **C03 — Khóa riêng từng người.** Lưu/đổi/xóa khóa, khởi động lại và kiểm tra không trả khóa về trình duyệt; không dùng key hoặc Google của chủ làm dự phòng cho người khác.
- [ ] **C04 — Chuyển khóa nhanh.** Thao tác chọn khóa không gọi model kiểm tra; kiểm tra kết nối là nút riêng. Chuyển liên tiếp trong mạng chậm, không bị phản hồi cũ ghi đè khóa mới.
- [ ] **C05 — Thanh hạn mức đúng khóa và mô hình.** Dữ liệu gắn với đúng người dùng, khóa và mô hình; khi đổi khóa bỏ số liệu hiển thị cũ. Phân biệt khóa đang chọn và khóa thực xử lý nếu có dự phòng.
- [ ] **C06 — Không giả số dư Google.** Thanh đo ghi ngân sách Veridra, số lượt model đã dùng và khoảng chờ; không cam kết còn chính xác 15/16 request. Không đặt lại bộ đếm khi đổi key cùng project. Quota project ngoài Veridra không quan sát đầy đủ được.
- [ ] **C07 — Phân biệt loại hạn mức.** Kiểm tra giới hạn theo phút/ngày/lượng nội dung xử lý, lỗi xác thực/quyền/hạn mức/máy chủ và quá thời gian chờ. Chỉ hiển thị mốc đặt lại hạn mức Google khi có cơ sở; hạn mức ngày dùng múi giờ Pacific có đổi giờ mùa hè, không cộng cố định 24 giờ từ lúc lỗi.
- [ ] **C08 — Cạn quota không mất việc.** Giữ prompt, nguồn và bản nháp; cảnh báo sớm theo ngân sách đã biết. Thử lại hữu hạn; chuyển khóa được người dùng cho phép, không đổi sang tuyến trả phí hoặc quay khóa để né giới hạn dự án.

Nguồn xác nhận hạn mức theo project, không theo key: [Google — hạn mức Gemini](https://ai.google.dev/gemini-api/docs/rate-limits). Một câu hỏi có thể gọi model nhiều lần nên không đồng nhất số câu hỏi với số lượt API.

### D. Trò chuyện, nguồn mới và chất lượng câu trả lời

- [ ] **D01 — Câu đơn giản.** Chào hỏi, phép tính, viết/tóm tắt không dùng nguồn ngoài phải hoàn thành thực tế; không gọi vòng agent hoặc truy cập Gmail/Drive không cần thiết.
- [ ] **D02 — Câu phức tạp và ràng buộc.** Kiểm tra tiếng Việt, độ dài, bảng, đơn vị, phép tính, giả định và kết luận theo yêu cầu. Bản nháp chưa đạt phải được sửa trong ngân sách hợp lý hoặc báo rõ, không tự nhận hoàn chỉnh.
- [ ] **D03 — Hỏi tiếp đổi phạm vi.** Đổi từ người gửi cụ thể sang năm email mới nhất; đổi ngày/thư mục/file/nguồn. Không tiếp tục dùng phạm vi cũ khiến trả thiếu hoặc nói chưa kết nối sai.
- [ ] **D04 — Chọn nguồn và phủ định.** Kiểm tra “không đọc Gmail/Drive”, chỉ local, nhiều nguồn và không nguồn. Quyền riêng tư và chỉ định rõ của người dùng ưu tiên hơn gợi ý định tuyến.
- [ ] **D05 — Thông tin cập nhật thật.** Kiểm tra lịch thể thao, giá/phiên bản/chức vụ/chính sách; có thời điểm server và múi giờ. Bắt buộc nguồn mới phù hợp, phân biệt ngày sự kiện/ngày xuất bản/ngày truy cập; không lấy trí nhớ model khẳng định hiện tại.
- [ ] **D06 — Web thiếu/lỗi nguồn.** 403/429/timeout, tin cũ, tin trái nhau và không có sự kiện: dùng nguồn chính thức khi đủ; nếu chưa đủ nói chưa xác minh. Không gửi nội dung riêng vào truy vấn web; xác minh tuyến grounding miễn phí thực sự khả dụng với project.
- [ ] **D07 — Dẫn nguồn theo nhận định.** Đối soát từng số liệu/kết luận quan trọng với đúng trang, thư, URL; liên kết còn dùng được. Số nguồn nhiều không thay độ đúng; không chỉ kiểm tra marker citation.
- [ ] **D08 — Phép tính có đối soát.** Tính tỷ lệ, chênh lệch, tổng, trung bình, tồn kho và đơn vị bằng công cụ; thử dữ liệu thiếu/không hợp lệ; phân biệt dự báo với dữ kiện. Đáp án số phải khớp bộ đáp án đối soát độc lập.
- [ ] **D09 — Sự kiện đang xử lý là thật.** Hiển thị agent nhận việc, công cụ/nguồn, tiến độ, thử lại và kết quả bước từ sự kiện thực. Không tạo luồng giả hoặc hiển thị chuỗi suy nghĩ nội bộ; tránh lộ nội dung riêng.
- [ ] **D10 — Lỗi dịch vụ và thao tác trò chuyện.** Thử hủy, gửi đôi, mất kết nối, chuyển trang, tải lại, quá thời gian chờ, lỗi máy chủ và hết hạn mức. Không treo vô hạn, mất câu hỏi hoặc tạo hai tác vụ ghi; xác định rõ đã hoàn thành/chưa hoàn thành.

### E. Gmail, Drive, Calendar và tài liệu tải lên

- [ ] **E01 — Gmail tìm đúng và đủ.** Sender theo tên/email, hôm nay/khoảng ngày theo giờ Việt Nam, số lượng, phân trang và hộp thư thực. Không có thư phải nói đúng, không suy diễn chưa kết nối.
- [ ] **E02 — Gmail đọc đủ cấu trúc.** Nội dung text/HTML, thread, attachment, MIME, CID và ảnh ngoài truy cập được; không dùng snippet thay body mà tự nhận tóm tắt toàn bộ. Thành phần không đọc được phải được chỉ rõ.
- [ ] **E03 — Gmail bản nháp/gửi.** Người nhận, CC/BCC, tiêu đề, nội dung, tệp đính kèm: xem trước → duyệt → gửi/lưu → đọc lại trạng thái. Hủy duyệt, thiếu quyền và thử lại không gửi trùng; không gửi thư thật ra ngoài kiểm thử khi chưa duyệt cụ thể.
- [ ] **E04 — Drive tìm đúng tệp.** Trùng tên, Unicode, đổi tên, nhiều thư mục, phân trang, quyền chia sẻ và tệp đã xóa. Không lấy file cùng tên của nguồn khác hoặc người khác.
- [ ] **E05 — Drive phân tích nhiều định dạng.** Docs, Sheets, PDF có text và định dạng hiện được quảng bá; chọn vùng/bảng, đọc đủ số liệu, đa nguồn và giới hạn tải. Dạng nào không chạy được thì loại khỏi giao diện/tài liệu hoặc sửa trước phát hành.
- [ ] **E06 — Drive tạo đúng nơi.** Tổng hợp/tính từ nhiều file → preview → duyệt → tạo Docs/Sheets đúng thư mục → đọc lại tiêu đề/nội dung/parent. Retry không tạo trùng; không ghi nhầm vào root rồi báo đúng thư mục.
- [ ] **E07 — Calendar đọc và chuẩn bị trước hẹn.** Đọc lịch theo múi giờ, sự kiện cả ngày, người tham dự, trùng giờ và thiếu quyền; quy trình trước họp dùng đúng sự kiện và không chạy trùng. Không gồm tạo/sửa lịch: ngoài phạm vi đã chốt.
- [ ] **E08 — Tệp nhỏ local.** TXT/MD/CSV/IPYNB nhập, xem, hỏi đáp, cập nhật/xóa; xử lý mã hóa, tiêu đề, cấu trúc notebook, file trùng/tên lỗi và giới hạn hiện công bố. Trên cloud không nói file được lưu trên máy người dùng.
- [ ] **E09 — PDF không OCR.** PDF có lớp text tối đa 25 MB, có số trang/citation, bảng/đa cột và file dài. File scan, mã hóa, lỗi hoặc trang ít/không text không được báo đã đọc hết; không âm thầm cắt văn bản. Kiểm tra cỡ file bằng bytes, không chỉ đuôi tên.
- [ ] **E10 — Nhập và tìm kiếm tài liệu bền.** Theo dõi tiến độ, hủy, thử lại, tiếp tục sau khởi động lại; không lập chỉ mục rỗng. Cập nhật/xóa phản ánh vào kết quả; tìm đúng đoạn xuyên tài liệu, chỉ dùng dữ liệu của đúng người và đúng phiên bản nguồn.

### F. Kết quả đã lưu, Skills và Bộ nhớ

- [ ] **F01 — Kết quả đã lưu có nghiệp vụ.** Lưu, tìm, mở, sửa, tạo phiên bản và xóa; giữ nguồn/citation, thời gian và liên kết tác vụ. Không mất chỉnh sửa khi reload hoặc đổi tài khoản.
- [ ] **F02 — Xuất thật và đọc lại.** Markdown/PDF/DOCX với tiếng Việt, bảng, số liệu, liên kết và phân trang. Mở từng định dạng trong môi trường đích; định dạng nào chưa xuất thực sự thì không trình bày như hỗ trợ.
- [ ] **F03 — Đánh giá kết quả trung thực.** Đánh giá tính đầy đủ/nguồn/hữu dụng có tiêu chí và dữ liệu đối soát; phân biệt nhận xét tự động với chứng thực sự thật. Phản hồi người dùng được lưu đúng bản kết quả.
- [ ] **F04 — Skills từ dễ đến khó.** Tạo/sửa/chạy/archive ít nhất 3 quy trình: một nguồn, nhiều nguồn và chuỗi phân tích → báo cáo. Kiểm tra đầu vào thiếu, revision và dữ liệu mới mỗi lần.
- [ ] **F05 — Phối hợp Skills trong Chat.** Hai skills trong một yêu cầu, mâu thuẫn chỉ định, thay nguồn và quyền thiếu; không dùng context cũ hoặc bỏ qua duyệt. Tiến độ nêu rõ bước thực đang chạy.
- [ ] **F06 — Bộ nhớ chủ động.** Nhập tay và yêu cầu “hãy nhớ…” qua Chat → mở phiên mới → tìm và dùng đúng; không tự lưu mọi nội dung nhạy cảm hoặc chỉ dẫn nhúng trong tài liệu.
- [ ] **F07 — Sửa và quên thật.** Sửa/archive/delete bộ nhớ, ngừng dùng dữ liệu cũ trong phiên mới; thao tác “quên” có kết quả kiểm chứng, không chỉ đổi giao diện.
- [ ] **F08 — Không nhiễm chéo.** Skills/Memory/kết quả/nguồn không lọt sang user khác; secret không được lưu làm kiến thức. Kiểm tra cả API trực tiếp chứ không chỉ ẩn nút trên giao diện.

### G. Bảy agent, quy trình cuối khóa và phối hợp

- [ ] **G01 — Bảy vai trò có thực thi.** Email, nghiên cứu web, thông tin doanh nghiệp, lịch, báo cáo, bộ nhớ và duyệt hành động đều có dấu vết thực. Tên agent trên màn hình không thay thế một bước chạy thật.
- [ ] **G02 — Sáu bước kiểm soát công cụ.** Đối soát từng bước ProtonX và nhánh từ chối: cấu trúc sai, chưa đăng nhập, thiếu quyền, cạn hạn mức, ghi nhật ký và thực thi. Từ chối phải xảy ra trước tác dụng phụ.
- [ ] **G03 — Buổi sáng đầy đủ.** Trigger bền → email → tìm công ty mới → web/thông tin doanh nghiệp → lịch → báo cáo → chờ duyệt → lưu/chuyển tiếp. Không làm lại mọi nghiên cứu khi có dữ liệu còn hợp lệ; không dùng thông tin cũ cho mục cần cập nhật.
- [ ] **G04 — Trước cuộc họp đầy đủ.** Job theo sự kiện lịch và timezone, đánh thức cloud bằng endpoint có xác thực; test app đang ngủ, sự kiện đổi/hủy và lịch trùng. Không dựa vào lịch chạy chỉ ở RAM.
- [ ] **G05 — Sáu doanh nghiệp ProtonX.** FPT Software, Vinamilk, Samsung Việt Nam, Shopee Việt Nam, Viettel Solutions, Bosch: mỗi ca có email/lịch mẫu, nguồn web thật, đầu ra và đáp án đối soát. “Quan tâm OCR” là nội dung nghiên cứu trong mẫu Shopee, không phải bật lại OCR cho sản phẩm.
- [ ] **G06 — Liên lạc giữa agent và công cụ.** Xác minh đường MCP/A2A được quảng bá là đường thật: đầu vào, phản hồi, lỗi, quyền và tương quan tác vụ. Tách minh họa khỏi thực thi; không lắp thêm dịch vụ chỉ để có sơ đồ đẹp.
- [ ] **G07 — Báo cáo cho cuộc họp.** Đủ giới thiệu/ngành/sản phẩm/tin mới/người liên hệ/điểm cần chú ý; nguồn đúng và không bịa contact. Số 98%, 42 giây, 12 nguồn của tài liệu là ví dụ, không điền thành kết quả Veridra.

### H. An toàn, hàng đợi và dữ liệu bền

- [ ] **H01 — Cách ly người dùng toàn bộ.** Thử truy cập chéo conversation, file, vector, key, operation, job, checkpoint, stream, export, Skills, Memory và nhật ký. Sửa ID/URL không vượt quyền.
- [ ] **H02 — Chống chỉ dẫn độc hại.** Thử trong Chat/email/PDF/web/memory yêu cầu lộ khóa, bỏ qua quyền hoặc tự gửi mail. Có bằng chứng độc lập, không chỉ chính evaluator tự chấm mẫu của mình.
- [ ] **H03 — Duyệt gắn đúng hành động.** Approval gắn với user, payload, phiên bản và thời hạn; sửa payload sau duyệt phải duyệt lại. Hủy hoặc thiếu duyệt không được ghi/gửi.
- [ ] **H04 — Cookie và đầu vào an toàn.** Cookie HTTPS, chống yêu cầu giả mạo, upload lớn/path traversal, URL nội bộ/metadata từ web/ảnh/attachment, lỗi HTML và rate limit. Không lấy trả lỗi 500 làm cơ chế chặn hợp lệ.
- [ ] **H05 — Bí mật không xuất hiện.** Kiểm tra tracked files, lịch sử Git, ảnh/tài liệu/artifact, responses, logs và traces. Dùng mã OAuth giả để kiểm thử log, không đọc/in bí mật thật. Không ghi query callback, key, token hoặc nội dung thư riêng vào log công khai.
- [ ] **H06 — State cloud không trên ổ tạm.** Quota, circuit, Skills, operation, queue, checkpoint, tài liệu và kết quả đều có adapter bền. Local vẫn chạy không cần Supabase; migration có phiên bản và không mất dữ liệu cũ.
- [ ] **H07 — Tác vụ dài sống qua gián đoạn.** Đóng tab, app restart/redeploy, lỗi worker giữa chừng và claim đồng thời. Lease/checkpoint/resume không mất việc hoặc chạy trùng; ưu tiên Chat, giới hạn xử lý nhập tài liệu.
- [ ] **H08 — Hành động trạng thái chưa rõ.** Mất phản hồi ngay sau gửi/tạo: đối soát hệ thống đích trước retry. Không phát lại mù; báo “chưa xác nhận” nếu không xác định được, không tự ghi thành công/thất bại.
- [ ] **H09 — Khôi phục độc lập.** Sao lưu DB và Storage; khôi phục sang môi trường mới bằng dữ liệu mẫu, đối soát count/checksum/quyền/vector/jobs. Restart cùng volume không được tính là restore test. Backup riêng tư, mã hóa, giữ tối đa 30 ngày theo plan.
- [ ] **H10 — Xóa và giới hạn dữ liệu.** Dung lượng theo user, retention, file tạm và account deletion; xóa cả object/vector/metadata liên quan. Công bố dữ liệu nào gửi Gemini, lưu ở đâu và cách chủ yêu cầu xóa.

### I. Quan sát vận hành và các số đo trong sản phẩm

- [ ] **I01 — Một mã truy vết xuyên suốt.** Cùng request/task ID nối API, agent, tool, hàng đợi, span và lỗi; tra được nguyên nhân cụ thể từ một request lỗi/chậm, không chỉ nhìn application log.
- [ ] **I02 — Đo dữ liệu thật.** Số yêu cầu/công cụ thành công-thất bại, agent đã chạy, lượng nội dung xử lý, thời gian từng bước và toàn lượt; định nghĩa mẫu số rõ. Chi phí chưa có giá phải nói chưa định giá, không ghi 0 giả.
- [ ] **I03 — Bộ quan sát có đối soát.** Grafana riêng cổng và có bảo vệ; Langfuse/OpenTelemetry nhận một request thật, nối trace đủ bước. Nếu chỉ chạy local, chứng minh đường metadata cloud về local không lộ nội dung riêng.
- [ ] **I04 — Quan sát không phá Chat.** Tắt exporter, chậm dịch vụ quan sát, lỗi gửi trace: Chat vẫn chạy, không rò RAM/queue và có thông báo vận hành thích hợp; metadata retention 30 ngày.
- [ ] **I05 — Nhật ký và bảng số đo dễ hiểu.** Chỉ hiện tiêu chí có số liệu thực, mẫu số, phạm vi, thời điểm. Không N/A, số giả, điểm tổng suy rộng hoặc khối nghiệm thu nội bộ trên giao diện; không làm mất các số đo đang có giá trị.
- [ ] **I06 — Bản thử so với bản chuẩn.** Dataset có phiên bản; lưu kết quả trước/sau cùng điều kiện và lý do khác biệt. Số đo lịch sử ghi rõ, không giả như của bản mới; lỗi chất lượng chặn release dù regression xanh.

### J. Toàn bộ giao diện và trải nghiệm

- [ ] **J01 — Một canvas caro.** Home/Chat/Drive/Gmail/Local/Kết quả/Skills/Memory/Cách hoạt động/Nhật ký/Phân quyền/Cài đặt dùng nền chung; wrapper không còn mảng nền trơn ghép vào. Card/input/modal vẫn có surface dễ đọc.
- [ ] **J02 — Chuyển động theo GetLayers.** Điểm sáng nhẹ trên lưới Home, không thêm một mảng nền, không chặn click hoặc gây dịch chuyển. Có tắt animation, giảm chuyển động và đo chi phí trên máy yếu; ghi quyền tài nguyên.
- [ ] **J03 — Sáng/tối đúng phạm vi.** Theme sáng đọc rõ sidebar/search/user message/output/code/tables/modals; không vô ý đổi palette component tối. Kiểm tra đủ trạng thái hover/focus/selected/disabled/error và hình/logo không nhấp nháy cũ.
- [ ] **J04 — Mọi màn hình đáp ứng kích thước.** 320/375/414/768 px và desktop; không tràn ngang, mất nút, che input, nhảy layout. Kiểm tra zoom và cuộn trong khung, không chỉ screenshot trang đầu.
- [ ] **J05 — Thao tác bàn phím và trạng thái.** Tab/focus rõ, modal đóng/mở và focus trở lại đúng; empty/loading/error/pending đều có hướng dẫn, nút thử lại không tạo trùng. Không lỗi console hoặc request bất thường bị bỏ qua.
- [ ] **J06 — Tiếng Việt và bố cục.** Giải thích gọn, không chêm thuật ngữ Anh trong nội dung cho user; tên riêng hãng được giữ. Cài đặt chia nhóm dễ hiểu; bảng đo có màu/viền/nhịp chuyển động phù hợp brand, không biến thành trang văn bản dán lên.
- [ ] **J07 — Cách Agent hoạt động.** Giữ và bổ sung hành trình bối cảnh → vấn đề → giải pháp → cơ chế → điểm khác biệt → giới hạn; minh họa từ sản phẩm thật, không bịa khách hàng/số liệu/so sánh đối thủ.

### K. Đo chất lượng, tài liệu và phát hành GitHub

- [ ] **K01 — Chạy đủ bộ tự động cuối cùng.** Kiểm tra mã, test backend/frontend, regression, build và smoke Docker từ sạch; giải thích từng ca skip. Rà migration, cấu hình env và dependency đã khóa; không coi test snapshot thay UI thật.
- [ ] **K02 — Ít nhất 24 lượt nghiệp vụ thật.** 6 doanh nghiệp + 6 luồng RAG + 6 phối hợp + 6 thông tin mới. Luồng RAG có thể dùng lại các PDF có text với câu hỏi khác; file scan là ca từ chối không OCR, không tính thành công đọc tài liệu. Mỗi nhóm có mẫu đối soát riêng.
- [ ] **K03 — Mẫu mới và lỗi chủ động.** Thêm mẫu chưa dùng khi sửa và chủ động tạo tình huống lỗi; kiểm tra dữ kiện/nguồn/hoàn thành, không chỉ đẹp hoặc đúng định dạng. Đáp án quan trọng đối chiếu thủ công bởi người kiểm thử với nguồn và bộ đáp án thực.
- [ ] **K04 — Bốn người đồng thời trên URL thật.** Ít nhất 5 vòng thao tác xen kẽ Chat/nguồn/khóa/kết quả/job; mỗi người dùng riêng nguồn và key. Kiểm tra tải, sự công bằng, không chéo dữ liệu và không crash. Tài khoản giả trong unit test không thay nghiệm thu này.
- [ ] **K05 — Điểm tổng có đủ nhóm.** Đúng nguồn 30%, hoàn thành nghiệp vụ 25%, tin cậy 20%, giao diện/khả dụng 15%, vận hành/tái lập 10%. Mục tiêu tổng 8,7–9/10 theo yêu cầu cập nhật, mỗi nhóm quan trọng ≥9; không lỗi nghiêm trọng. Thiếu nhóm bắt buộc thì chưa tính điểm toàn sản phẩm. Điểm tổng không thay các điều kiện an toàn và chức năng bắt buộc.
- [ ] **K06 — Hướng dẫn thực hiện lại được.** README hiện trạng/URL/giới hạn chính xác; hướng dẫn clone→cài→OAuth/key→nhập mẫu→Chat→workflow→test→Docker. Một môi trường sạch làm theo từng bước chạy được, không cần file bí mật trên máy chủ sản phẩm.
- [ ] **K07 — Bộ demo đầy đủ.** Mỗi màn hình/thao tác có chuẩn bị, prompt, kỳ vọng, đối soát và khôi phục lỗi; mẫu tải được đúng quyền. Bài giới thiệu 10 phút theo ProtonX và phương án khi provider lỗi; không hứa chạy thành công 100% bất chấp nguồn/quota.
- [ ] **K08 — Tài liệu kiến trúc nhất quán.** Một trang chỉ rõ local/cloud, thành phần thực hoạt động, adapter/persistence, queue, quyền, 7 agents, MCP/A2A và backend so sánh. Rà/xếp tài liệu cũ thành lịch sử thay vì để các hướng dẫn mâu thuẫn cùng là bản hiện hành.
- [ ] **K09 — Chuỗi build/phát hành tái lập.** GitHub kiểm tra sạch→đóng gói→ảnh Docker theo digest→Render dùng chính ảnh đó. Cấu hình thay đổi có kiểm tra tương ứng; không build một ảnh khác ngoài kiểm thử để demo.
- [ ] **K10 — Gộp vào main sau nghiệm thu.** Rà diff, bí mật, quyền tài nguyên và checklist; gộp nhánh thử nghiệm đúng bản đã đạt. Chạy lại kiểm tra GitHub trên main, phát hành bản gắn nhãn, cập nhật README/URL. Không gộp trước để tạo cảm giác hoàn thiện.
- [ ] **K11 — Kiểm tra lần cuối và quay lui.** Xác nhận Render đúng bản main đã chốt, đăng nhập/Chat/nguồn/duyệt/Storage hoạt động, dữ liệu còn sau deploy và cách rollback thực thi được. Ghi giới hạn còn lại cụ thể; không tuyên bố hết lỗi từ một lần smoke.
