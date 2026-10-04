# Veridra — checklist hiện hành theo xương sống sản phẩm

Ngày chốt: 01/10/2026. Nguồn định hướng: [PRODUCT-FOUNDATION.md](PRODUCT-FOUNDATION.md). Quản lý bằng **18 điều kiện nghiệm thu trong 6 nhóm**, triển khai và đối soát bằng [90 tiêu chí chi tiết hiện hành](ACCEPTANCE-DETAILS.md). Hai cấp cùng bắt buộc: gom nhóm không có nghĩa cắt bỏ yêu cầu. Bản cũ trong thư mục QA chỉ là lịch sử; bộ nhớ là phần bổ sung, không thay phạm vi toàn sản phẩm.

**Ngưỡng hiện hành theo yêu cầu cập nhật của người dùng:** mục tiêu điểm tổng 8,7–9/10; mức 9,2 của kế hoạch trước chỉ là lịch sử. Điều kiện an toàn, hoàn thành chức năng chính, đủ nhóm đo, không lỗi nghiêm trọng và bằng chứng cùng phiên bản vẫn bắt buộc; không dùng điểm trung bình để bỏ qua điều kiện chưa đạt.

Mỗi ô chỉ đóng khi có bằng chứng cùng bản mã/ảnh Docker/cấu hình: môi trường, thời điểm, đầu vào, kỳ vọng/thực tế, mã yêu cầu và dữ liệu đối soát đã khử riêng tư. ĐẠT / KHÔNG ĐẠT / CHƯA KIỂM CHỨNG / LOẠI KHỎI PHẠM VI; không điểm giả. Phần đã có mã vẫn có thể chưa nghiệm thu.

**Bổ sung bộ nhớ ngày 01/10:** áp dụng [kế hoạch chất lượng bộ nhớ](MEMORY-QUALITY-PLAN.md), gồm 12 ca ngữ cảnh Chat và 6 ca dài hạn. Giữ nguyên 18 gate và 24 tác vụ chính: 6 tác vụ phối hợp trở thành hội thoại 3–5 lượt, không chỉ câu hỏi đơn. Chạy thêm ca xác định về lịch sử dài, ngày, gửi chồng và phục hồi theo rủi ro; không nhân toàn bộ bộ đo với mọi model.

Điều kiện bắt buộc bổ sung: A2/A3 chấm đúng yêu cầu xuyên lượt; B1–B3 tiếp nối đúng nguồn và lưu có chủ đích; C1 giữ/sửa ngữ cảnh kể cả vượt cửa sổ lịch sử hoặc đổi đường điều phối; C3 đổi khóa không mất phiên; D1 không chéo người hoặc dùng duyệt cũ cho nội dung mới; D2 sửa/quên và phục hồi có hiệu lực; D3 truy nguyên phiên bản ngữ cảnh không lộ nội dung riêng; E3 có demo hỏi tiếp; F1/F2 nghiệm thu nhiều lượt và nhiều người cùng bản. Tỷ lệ tiếp nối/truy hồi >=95%, cập nhật phạm vi/ràng buộc quan trọng và các ca an toàn bắt buộc 100%, 6/6 chuỗi phối hợp đạt. Bằng chứng bộ nhớ tính trong chất lượng nghiệp vụ/độ tin cậy, không tạo điểm tổng mới hoặc cộng trùng.

## Phạm vi đầy đủ đã khóa

| Phần việc | Số tiêu chí chi tiết | Việc hoàn thiện và bằng chứng bắt buộc |
|---|---:|---|
| Chuẩn bị, đối chiếu cuối khóa | 5 — A01–A05 | Một bản nguồn; ma trận yêu cầu; bảo toàn thay đổi; mẫu hợp lệ; cách chấm khóa trước khi đo |
| Tải trang và tài nguyên | 8 — B01–B08 | Tìm nguyên nhân URL chậm theo từng giai đoạn; sửa chờ vô hạn/khởi động; đo tốc độ, RAM, CPU và kho riêng tư |
| Đăng nhập và khóa riêng | 8 — C01–C08 | Bốn người thật, quyền Google và kết nối lại; khóa riêng mã hóa; chuyển nhanh; bộ đếm đúng phạm vi và giữ việc khi hết hạn mức |
| Trò chuyện | 10 — D01–D10 | Câu đơn giản/phức tạp; hỏi tiếp; nguồn mới; tính toán/dẫn chứng; tiến độ thật; phục hồi lỗi và ngữ cảnh nhiều lượt |
| Gmail, Drive, lịch, tài liệu | 10 — E01–E10 | Đọc đủ/tìm đúng; tạo đúng nơi có duyệt; lịch đọc/chuẩn bị trước hẹn; PDF có văn bản; nhập và tìm kiếm bền |
| Kết quả, Skills, bộ nhớ | 8 — F01–F08 | Lưu/sửa/phiên bản/xuất; quy trình nhiều bước; nhớ/quên đúng; phối hợp và quyền riêng tư |
| Bảy agent và yêu cầu cuối khóa | 7 — G01–G07 | Vai trò thật; sáu bước kiểm soát công cụ; sáu doanh nghiệp; buổi sáng/trước hẹn; báo cáo và liên lạc giữa agent |
| An toàn và dữ liệu bền | 10 — H01–H10 | Cách ly người; chống chỉ dẫn độc hại; duyệt đúng; bí mật; tiếp tục tác vụ; đối soát thao tác chưa rõ; sao lưu/khôi phục/xóa |
| Quan sát và số đo | 6 — I01–I06 | Truy nguyên lỗi/chậm; số đo thật; Grafana riêng và dấu vết; quan sát hỏng không phá Chat; so sánh trước/sau |
| Giao diện và câu chuyện | 7 — J01–J07 | Một nền caro, chuyển động tham khảo GetLayers; sáng/tối; điện thoại/bàn phím; tiếng Việt; cài đặt rõ; hành trình giải thích đúng định vị |
| Đánh giá, tài liệu và phát hành | 11 — K01–K11 | Bộ tự động; 24 tác vụ thật và mẫu mới; bốn người; điểm đủ nhóm; hướng dẫn từ máy sạch; demo; kiến trúc; GitHub/main/Render đúng bản và quay lui |
| **Tổng** | **90** | Không bỏ nhóm để chỉ tập trung bộ nhớ hoặc Chat |

Bảy nhóm người dùng nhắc lại có 61 tiêu chí; 29 tiêu chí còn lại là chuẩn bị, quan sát, giao diện và phát hành. Giữ đủ cả 90, không coi 61 là toàn bộ sản phẩm.

## Cách triển khai, không chỉ kiểm thử

Mỗi điều kiện làm theo cùng một chu trình: **đối chiếu mã và tái hiện → xác định phần thiếu/nguyên nhân → sửa đúng phần cần thiết → kiểm tra tự động → chạy thao tác thật → ghi bằng chứng → đóng điều kiện**. Phần đã hoạt động không xây lại; phần không có tác động nghiệp vụ, không bắt buộc cuối khóa/an toàn/phát hành thì không thêm.

1. **Chốt nghiệp vụ và mẫu:** định vị trợ lý chuẩn bị tư vấn khách hàng doanh nghiệp; ba quy trình W1–W3; đầu ra và phương pháp phân tích; chuẩn hóa bộ chấm. Đầu ra: hợp đồng nghiệp vụ, mẫu/đáp án và ma trận ProtonX.
2. **Ổn định đường vào:** ưu tiên tải URL, khởi động, giới hạn chờ, đăng nhập/quyền, chuyển khóa và thông báo hạn mức. Đầu ra: đường truy cập thật dùng được với số đo và giới hạn đã công bố; không chỉ `/api/health` trả thành công.
3. **Hoàn thiện chức năng chính:** Chat và từng nguồn, hỏi tiếp/ngữ cảnh; kết quả/Skills/bộ nhớ; thực hiện W1–W3 xuyên suốt, duyệt và đọc lại. Đầu ra: tác vụ nghiệp vụ hoàn thành, không ghép các kiểm tra thành phần rời thành một quy trình đạt.
4. **Chứng minh an toàn và phục hồi:** kiểm quyền, dữ liệu bền, lỗi giữa chừng, khôi phục môi trường mới và truy nguyên. Lỗi bảo mật nghiêm trọng xử lý ngay khi phát hiện, không đợi bước này.
5. **Hoàn thiện sử dụng và demo:** nội dung đúng đối tượng, giao diện thống nhất, nền động có giới hạn, tiếng Việt; README/kiến trúc/hướng dẫn mẫu và bài demo 10 phút. Không thiết kế lại vô hạn.
6. **Chốt nghiệm thu và phát hành:** chạy đủ bộ cùng bản, bốn người, đo chất lượng/thời gian/tài nguyên, rà bí mật; đóng các điều kiện; gộp main, kiểm CI và triển khai đúng ảnh, kiểm cuối/khả năng quay lui.

Mỗi bước cập nhật trạng thái thật và phần cần người dùng xác thực. Không đóng điều kiện chỉ vì đã viết mã; cũng không giữ phần đã đạt mở vô hạn bằng cách thêm yêu cầu mới.

## A — Nghiệp vụ và cách chấm (làm trước)

- [ ] **A1. Chuẩn hóa bộ đo công ty.** Tách kiểm tra nguồn/nghiên cứu khỏi W1–W3 đầy đủ. Bỏ 12 nguồn và 42 giây như điều kiện bắt buộc từ số ví dụ; vẫn đo số nguồn/thời gian. Kiểm nhận định với nội dung nguồn, không chỉ marker; nguồn mâu thuẫn phải được nêu và xử lý, không tự FAIL vì phát hiện mâu thuẫn. Không dùng `unauthorized_side_effects=0` hằng số hoặc chữ `pending` làm bằng chứng an toàn. Thiếu dữ liệu phải hạ kết luận, không sửa expected để PASS. Hiện: cần sửa bộ đo trước khi chứng nhận nghiệp vụ.
- [ ] **A2. Đầu ra nghiệp vụ có hợp đồng rõ.** Bản yêu cầu/báo cáo trước hẹn/bản phản hồi bám mục tiêu; tách dữ kiện-suy luận-giả định-chưa biết; câu hỏi hiện trạng/vấn đề/ảnh hưởng/kết quả mong muốn liên quan và không bịa ngân sách/ROI. Đọc nguồn, tính toán và hỏi lại chỉ khi cần; phương pháp thể hiện ở đầu ra thật, không chỉ copy giới thiệu. Hiện: có thành phần; cần đối soát toàn bộ.
- [ ] **A3. Khóa mẫu và cách chấm.** Manifest đủ 6 doanh nghiệp ProtonX, 6 PDF cung cấp và mẫu thư/lịch/attachment/bảng/skills/memory; URL/checksum/quyền/oracle. Khóa 24 lượt live theo plan: 6 doanh nghiệp, 6 tác vụ tài liệu có text, 6 phối hợp, 6 nguồn cập nhật; thêm ca âm và mẫu mới ngoài bộ sửa lỗi. File scan là ca từ chối không OCR, không tính vào đọc thành công. Chấm 30% nguồn, 25% nghiệp vụ, 20% tin cậy, 15% khả dụng, 10% vận hành; mục tiêu tổng 8,7–9/10 và nhóm quan trọng >=9. Lưu số mẫu, lỗi và giới hạn; không lấy điểm mẫu offline làm điểm live.

## B — Ba quy trình và nguồn (không mở rộng domain)

- [ ] **B1. W1 tiếp nhận đầu ngày.** Email sender/date/count/thread/body/attachment và phân trang đúng; hỏi tiếp đổi phạm vi không dùng bộ lọc cũ. Job sáng bền tạo bản yêu cầu/điều thiếu/việc cần chuẩn bị, biết hồ sơ đã có và lịch. Bảy vai trò và sáu bước Tool Harness có dấu vết thật, cả nhánh từ chối. Kiểm mẫu ProtonX, không tự gửi thư.
- [ ] **B2. W2 chuẩn bị trước hẹn.** Đọc Calendar đúng timezone/sự kiện, trigger trước hẹn thật; app ngủ/job restart không mất hoặc trùng. Drive đúng tệp/thư mục/phiên bản; TXT/MD/CSV/IPYNB và PDF text theo giới hạn; trích đúng trang, không cắt âm thầm/index rỗng. Kết hợp web/Company Info: ngày xuất bản-sự kiện-truy cập, nguồn liên quan, lỗi thiếu nguồn nói đúng. Giữ ranh giới “không đọc Gmail/Drive” khi người dùng chỉ định. OCR loại bỏ; không thêm tạo/sửa lịch vào gate.
- [ ] **B3. W3 phản hồi/lưu/tiếp nối.** Gmail đúng recipient/CC/BCC/thread/attachment; Docs/Sheets đúng nội dung/parent và vùng sửa; preview→duyệt→execute→readback. Skills nhiều bước có đầu vào mới/revision; Memory chỉ ghi theo yêu cầu rõ, sửa/quên có hiệu lực và không lưu secret. Kết quả sửa/xuất MD/PDF/DOCX đọc được tiếng Việt/bảng/link và giữ nguồn. MCP/A2A được quảng bá phải là đường SDK thực; phân biệt phần minh họa. Không tự biết kết quả cuộc họp.

## C — Độ tin cậy và trải nghiệm chờ

- [ ] **C1. Chat và xử lý lỗi.** Câu đơn giản, phân tích dài, phép tính và nguồn hỗn hợp chạy thật. Có ngân sách vòng gọi/deadline/hủy; lỗi 401/403/429/503/timeout phân biệt; giữ câu hỏi và nguồn. Đổi trang/reload/gửi đôi không mất hoặc tạo trùng. Sự kiện pending thật, không suy nghĩ nội bộ/tiến độ giả. Hiện: hồi quy nhỏ đạt; live cùng bản chưa đủ.
- [ ] **C2. Tải cloud và tài nguyên.** Đo URL thật warm/cold, auth/status/API/static/import/DB/storage riêng. Thời hạn chờ phía giao diện, retry có giới hạn, không spinner vô hạn; lazyload thư viện không cần đầu trang. Tình trạng kho tệp cập nhật sau lỗi/phục hồi, kho public/409 không được chấp nhận; readiness khác liveness. Đo RAM/CPU/kết nối/ảnh Docker trong tải Chat+PDF, không chạy stack nặng không cần. Mục tiêu đã đề xuất: warm p95<=5s (>=20 lượt), cold<=120s (>=3 lượt), Chat đơn giản p95<=20s (>=10), có nguồn p95<=60s; công bố lỗi/cỡ mẫu và giới hạn ngủ miễn phí, không cam kết luôn bật.
- [ ] **C3. Khóa và hạn mức.** Lưu mã hóa theo người, chuyển key không gọi model kiểm tra; p95<=2s trên >=10 lượt, không phản hồi cũ ghi đè. Snapshot theo người/khóa/model; phân biệt khóa chọn và thực phục vụ. Ledger không reset do đổi key cùng project; không quảng bá 15/16 là quota Google thật. Cooldown/reset có căn cứ, múi giờ đúng; hết hạn mức giữ yêu cầu. Không paid fallback hoặc sử dụng credential của người khác.

## D — An toàn, dữ liệu bền và quan sát

- [ ] **D1. Quyền và hành động.** Invite<=4 và owner chỉ định; OAuth HTTPS/thiếu quyền/hết phiên/reconnect; cookie/CSRF/RBAC. Truy cập chéo cả Chat/file/vector/key/job/stream/Memory/Skills/export/log bị chặn. Injection qua mọi nguồn, URL nội bộ, upload/path/size, exfiltration và gửi thiếu duyệt bị chặn. Approval gắn payload/user/version; sửa nội dung cần duyệt lại. Rà secret/PII trong Git/log/trace/artifact; không log query mã OAuth. Ca âm phải có bằng chứng không ghi/gửi, không chỉ câu chữ trả lời.
- [ ] **D2. Dữ liệu và phục hồi.** Cloud state của quota/circuit/skills/approval/queue/checkpoint/tệp/kết quả đều bền; local vẫn dùng được. Migration có phiên bản; claim/lease/resume/idempotency thật sau restart/redeploy. Hành động unknown phải readback trước retry. Sao lưu DB+Storage, restore môi trường mới với checksum/quyền/vector; cleanup/delete/retention/caps được kiểm tra. Không restart cùng volume rồi coi là restore.
- [ ] **D3. Quan sát đủ truy nguyên.** Request/task ID nối logs/metrics/traces; agents/tool thành công-thất bại/token/latency và cost có căn cứ. Giá chưa biết không ghi 0. Một request cloud thật đối soát được bằng Langfuse/OpenTelemetry/Grafana riêng và có quyền; metadata retention 30 ngày, không xuất prompt/mail/key. Exporter hỏng không làm Chat hỏng. Chỉ hiện số đo có mẫu thật; không khối nghiệm thu nội bộ hoặc điểm giả trên giao diện.

## E — Concept và sử dụng dễ hiểu

- [ ] **E1. Một câu chuyện sản phẩm.** Home/README/hướng dẫn/“Cách hoạt động” dùng định vị và ba lối vào trong PRODUCT-FOUNDATION. Các tình huống ngân hàng/học tập/kho chỉ minh họa khả năng, không tuyên bố giải pháp ngành. Giữ bảy agent/mẫu doanh nghiệp, không thêm CRM/task manager. Ngôn ngữ user gọn bằng tiếng Việt, không buộc chọn giao thức/agent trước khi dùng.
- [ ] **E2. UI thống nhất, không thiết kế lại vô hạn.** Giữ logo/type/màu component tối; một canvas caro sáng/tối, wrapper không ghép nền trơn. GetLayers chỉ tham khảo điểm sáng nhẹ Home, có tắt/reduced-motion và quyền tài nguyên; không che click/đẩy layout. Light/dark, 320/375/414/768/desktop, focus/bàn phím/console/network/empty/loading/error/disabled trên mọi màn hình liên quan. Bảng số đo có thiết kế phù hợp nhưng chỉ dữ liệu thật.
- [ ] **E3. Hướng dẫn và demo làm theo được.** Mẫu giả lập/nguồn thật tách rõ, không đưa tài liệu riêng vào repo. Tutorial từng màn hình và W1–W3: chuẩn bị→thao tác→prompt→kỳ vọng→đối soát→phục hồi. Kịch bản 10 phút ProtonX, demo chính/phương án provider lỗi. Chạy theo từ môi trường sạch; OAuth/BYOK/cold-start/khả năng không hỗ trợ được giải thích đúng.

## F — Nghiệm thu và phát hành đúng bản

- [ ] **F1. Bằng chứng live và giá trị.** Hoàn thành 24 lượt đã khóa, mẫu ngoài bộ sửa lỗi, fault injection và đối soát nhận định bằng nguồn/oracle. W1–W3 phải thực thi xuyên suốt, không ghép component PASS thành chuỗi PASS. Ít nhất 2 công việc so sánh cặp với cách hiện tại, gồm sửa tay và hạn chế mẫu nhỏ; không tự hứa mức tiết kiệm/doanh thu. Không P0/P1; gate thiếu/chưa kiểm chứng chặn phát hành dù đạt mục tiêu điểm tổng 8,7–9/10.
- [ ] **F2. Bốn người thật và cùng phiên bản.** Từng người tự OAuth/BYOK; >=5 vòng thao tác xen kẽ trên HTTPS, không chéo dữ liệu/crash/mất việc. Đóng băng Git/config/migration/model/dataset/digest cho hồ sơ cuối. Thay đổi sau chốt phải chạy lại phần ảnh hưởng. Dữ liệu có từ build cũ giữ lịch sử, không đổi nhãn thành build mới.
- [ ] **F3. GitHub→Docker→Render.** Dependency khóa, kiểm mã/test/regression/build/smoke từ sạch; giải thích skip. Rà diff và secret/history/license; preserve stash/tệp của user. CI đóng gói đúng digest, nghiệm thu rồi gộp main; CI main/release/Render cùng ảnh. Đối soát URL/login/Chat/nguồn/duyệt/persistence và rollback. Không tự đổi repo URL/visibility hoặc quảng bá free-tier luôn sẵn sàng.

## Tình trạng hiện tại

### Việc còn lại để chốt — cập nhật 04/10/2026

Không mở thêm phạm vi; ưu tiên sáu khối dưới đây. Có mã và kiểm thử thành phần không đồng nghĩa đã nghiệm thu cả khối.

| Khối | Phần chưa đóng | Bước kết thúc cụ thể |
|---|---|---|
| Quy trình nghiệp vụ (A/B/F1) | Chưa đủ bằng chứng W1–W3 xuyên suốt và bộ mẫu đã khóa | Chạy ba quy trình với mẫu, đối soát nguồn/đầu ra/hành động; không ghép các ca thành phần thành một quy trình đạt |
| Hội thoại và nguồn (B2/C1/F1) | Hỏi tiếp Mộc An từng lạc sang web; tên báo cáo khi hỏi tiếp còn sai trên bản trước; bộ đo chưa đủ | Kiểm lại nguyên ca lỗi sau sửa, rồi hoàn thành các mẫu còn thiếu; không liên tục thêm mẫu mới |
| Đường vào và giao diện (C2/C3/E2) | Chưa đủ mẫu đo tốc độ; nút ngân sách bị ẩn trên điện thoại; chờ đánh thức máy miễn phí còn tồn tại | Sửa nút điện thoại, đo tải/chuyển khóa, kiểm trạng thái chờ và công bố giới hạn thực tế |
| An toàn và phục hồi (D1/D2/D3) | Khôi phục cloud độc lập và đối soát quan sát chưa có đủ bằng chứng | Kiểm bộ xác định trên dữ liệu thử; thử khôi phục DB+kho tệp sang môi trường riêng, không đè dữ liệu đang dùng |
| Hướng dẫn và demo (E1/E3) | Chưa chứng minh người dùng làm theo từ môi trường sạch thành công | Rà hướng dẫn với mã thật, chạy từ bản clone sạch, kiểm từng bước và kịch bản dự phòng |
| Bản phát hành (F2/F3) | Chưa đủ bốn tài khoản thật, chưa gộp main | Giữ kiểm một quản trị theo lựa chọn người dùng; bốn người vẫn chưa kiểm chứng. Chỉ gộp main khi điều kiện bắt buộc được giải quyết và cùng ảnh đã nghiệm thu |

Bản `41fee740f5231fd984920c6bea3b3db112ee9ac2` đã qua GitHub lần 56: kiểm mã/đóng gói 4 phút 19 giây, PostgreSQL 43 giây. Ảnh `sha256:adc86df42c0cc65c2fc158fd3e2a72c0ea27be31fd8c04f18b149d54d1285bd3` đã được đối chiếu trên Render, phục vụ lúc 17:01:54 ngày 04/10 giờ Việt Nam. Local: 1.021 ca máy chủ đạt, 11 ca PostgreSQL không chạy local; 168 ca giao diện đạt. Đây là kết quả kỹ thuật, chưa phải nghiệm thu toàn bộ sản phẩm hoặc điểm chất lượng nghiệp vụ. Nhật ký Render cho thấy khoảng 119 giây từ bắt đầu dịch vụ tới tiến trình máy chủ, thêm 18 giây khởi tạo ứng dụng; chưa giải quyết yêu cầu truy cập tức thì sau ngủ.

OCR/PDF ảnh, tuyến trả phí, tạo/sửa lịch, đăng ký đại trà và hạ tầng nặng vẫn loại khỏi phạm vi. PDF có văn bản không phụ thuộc OCR và vẫn được hỗ trợ theo giới hạn đã công bố. Các đoạn bên dưới là kết quả lịch sử, không phải bản cloud mới nhất.

Cập nhật 04/10/2026: sản phẩm đã được triển khai trên [URL kiểm thử](https://veridra-closed-beta.onrender.com), dùng PostgreSQL và kho tệp riêng tư. Nhánh staging đã có các sửa lỗi và kiểm thử mới; chưa gộp main hoặc chứng nhận hoàn thành 18 điều kiện. Không đánh đồng các ô chưa đóng với việc chưa có mã hoặc chưa thực hiện gì.

Bản cloud đã đối chiếu gần nhất: `1020655`, ảnh `sha256:ea2046a44b54a33545f4f9386bab847885ae0aa068255d92a4d55a4801f5d22e`; GitHub lần 53 thành công, bước kiểm mã 4 phút 02 giây và PostgreSQL 37 giây, Render phục vụ từ 21:51:50 ngày 03/10 giờ Việt Nam. Bản này gồm sửa tải lịch sử, dẫn nguồn bộ nhớ, điều hướng web và giữ đoạn bằng chứng trang khi hỏi tiếp. Bộ máy chủ local trước đó có 1001 ca đạt, 11 phép thử PostgreSQL không chạy local; PostgreSQL được kiểm riêng trong GitHub. Đây là bằng chứng kỹ thuật, không phải điểm chất lượng câu trả lời hoặc chứng nhận cùng bản cuối.

Đã kiểm thật một số phần: đổi khóa đã lưu không khởi động lại và không đặt lại bộ đếm cũ; lưu ghi chú có phạm vi dự án, tìm lại trong phiên mới, cất và khôi phục; PDF có văn bản được xử lý đủ 15 trang và giữ sau triển khai. Trên `1020655`, một câu hỏi web đọc đúng nguồn chính thức hoàn thành 15,4 giây; câu hỏi bộ nhớ trả đúng ba mục/phạm vi, dẫn [1] và mở đúng màn hình bộ nhớ. PDF câu đầu 27,5 giây trả đúng tên đầy đủ, ngày phát hành/ngày dữ liệu, dẫn trang 1/3. Hỏi tiếp 17,7 giây tính đúng 5 ngày nhưng đổi sai tên báo cáo và tự quy việc kiểm tra lại thành đính chính dữ kiện của người dùng: vẫn KHÔNG ĐẠT. Đang sửa và kiểm lại, chưa chứng minh toàn bộ RAG, 12 ca ngữ cảnh, 6 ca bộ nhớ hoặc 6 chuỗi nghiệp vụ. Ngày 04/10 vẫn có chờ đánh thức Render kéo dài; chưa chứng nhận tốc độ khởi động đạt.

Các mục còn mở quan trọng: phục hồi tải lịch sử khi lỗi mạng; bộ thử nghiệp vụ và nguồn cập nhật đầy đủ; dẫn chứng/số liệu của các tài liệu còn lại; sửa/quên và hội thoại dài; luồng buổi sáng/trước hẹn; khôi phục dữ liệu trên môi trường mới; bốn người dùng thật; đối soát cuối cùng cùng một phiên bản. Chỉ có một tài khoản quản trị được người dùng cho phép kiểm hiện tại, nên mục bốn người giữ **CHƯA KIỂM CHỨNG**, không coi là đã loại bỏ.

Bằng chứng chi tiết và dữ liệu riêng của tester được giữ ngoài Git. Kết quả hồi quy ngày 01/10 và các bản trước chỉ là lịch sử; không đổi nhãn thành bằng chứng của bản cuối. OCR và tuyến trả phí không nằm trong phạm vi đã chốt. Không đưa email thật, tài liệu riêng hoặc khóa vào kho mã để chứng minh nghiệm thu.

## Điều kiện kết thúc và bàn giao

Chỉ kết thúc khi cả 18 điều kiện và các tiêu chí chi tiết áp dụng đã ĐẠT trên cùng bản phát hành; không lỗi nghiêm trọng hoặc lỗi chức năng chính chưa xử lý; đạt mục tiêu điểm tổng 8,7–9/10 và nguồn/nghiệp vụ/độ tin cậy từng nhóm >=9. Không thiếu nhóm đo, không lấy số liệu giả hoặc kết quả cũ để lấp khoảng trống.

Hồ sơ từng mục có: trạng thái; mã bản nguồn/cấu hình/model/dữ liệu/ảnh đóng gói; môi trường; đầu vào/bước làm; kỳ vọng/thực tế; mã yêu cầu; số đo và mẫu số; bằng chứng đối soát; lỗi/cách sửa/kiểm lại hoặc lý do loại bỏ được duyệt. Tiêu chí chưa chạy giữ CHƯA KIỂM CHỨNG và chặn phần phát hành liên quan.

Bàn giao đủ: concept/định vị/phương pháp; ma trận ProtonX; kiến trúc phản ánh mã thật; mẫu và đáp án được phép chia sẻ; kết quả đo/lỗi trước-sau; hướng dẫn clone/chạy local và HTTPS; tutorial từng chức năng/chuỗi phối hợp; bài demo 10 phút; hướng dẫn xác thực, sao lưu/khôi phục/quay lui; main GitHub và Render cùng bản đã nghiệm thu.

Loại đã chốt: OCR/PDF ảnh, dịch vụ trả phí, tạo/sửa Calendar, đăng ký đại trà và cụm hạ tầng nặng không cần thiết. PDF có văn bản giữ trong phạm vi khi nghiệm thu được. Không âm thầm loại thêm một chức năng đang được quảng bá chỉ để đạt điểm.

“Sẵn sàng phát hành” ở đây là **bản thử nghiệm theo lời mời, tối đa bốn người, đã nghiệm thu trong phạm vi công bố**. Không hứa miễn phí luôn bật, URL tức thì sau ngủ hoặc không bao giờ lỗi dịch vụ ngoài. Nếu yêu cầu luôn bật không đổi, phương án miễn phí hiện tại không đáp ứng và phải thay phương án hosting trước khi chứng nhận mức đó.

## Đối chiếu đầy đủ bản 90 mục

Mỗi mã cũ được gán một chủ quản để không bỏ sót; điều kiện bên trong vẫn dùng theo rủi ro liên quan, không chạy 90 dự án riêng.

| Gate mới | Mục cũ phụ trách |
|---|---|
| A1 | I05, I06 |
| A2 | D02, D07, G07 |
| A3 | A04, A05, K02, K03, K05 |
| B1 | E01, E02, G01, G02, G03 |
| B2 | D03, D04, D05, D06, D08, E04, E05, E07, E08, E09, E10, G04, G05 |
| B3 | E03, E06, F01, F02, F03, F04, F05, F06, F07, G06 |
| C1 | D01, D09, D10 |
| C2 | B01, B02, B03, B04, B05, B06, B07, B08 |
| C3 | C03, C04, C05, C06, C07, C08 |
| D1 | C02, F08, H01, H02, H03, H04, H05 |
| D2 | H06, H07, H08, H09, H10 |
| D3 | I01, I02, I03, I04 |
| E1 | A02, J06, J07, K08 |
| E2 | J01, J02, J03, J04, J05 |
| E3 | K06, K07 |
| F1 | điều kiện mới: chuẩn hóa bộ đo, so sánh giá trị và nghiệm thu W1–W3; không thay các lượt kiểm thử đã khóa |
| F2 | A01, C01, K04 |
| F3 | A03, K01, K09, K10, K11 |

Điều chỉnh công khai: E07 cũ bỏ tạo/sửa Calendar vì mã hiện read-only và ProtonX cần đọc/trigger; không phát triển ngoài yêu cầu. Bỏ “12 nguồn/42 giây” như gate cứng, vẫn ghi số đo để đối chiếu ví dụ ProtonX. Ngưỡng điểm dùng quyết định cập nhật đã ghi ở đầu tài liệu; không tự đổi theo kết quả đo, không bỏ thử bốn user/restore/an toàn/CI hoặc các mẫu bắt buộc.

Thứ tự: A trước → B/C song hành theo luồng → D trước khi release → E giới hạn theo concept → F chốt cùng bản. Lỗi bảo mật nghiêm trọng xử lý ngay, không chờ đến nhóm D.

Các bước cần người dùng: đăng nhập lại khi cần, cấp quyền/nhập key riêng, mời đủ tài khoản test và duyệt hành động thật. Không yêu cầu gửi bí mật trong Chat. Thiếu bước người dùng thì ghi rõ CHƯA KIỂM CHỨNG, không tự PASS.
