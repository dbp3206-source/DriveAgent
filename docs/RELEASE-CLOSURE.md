# Đợt nghiệm thu cuối — chốt phạm vi 06/10/2026

## Đối soát mới nhất

**Ảnh gộp sẵn sàng triển khai — cloud chưa đổi:** commit
`2f0183a9e605da922065d55474d0549a6f4e23c4` có cả sửa ranh giới dữ kiện
và nhận diện nguồn công khai. 252 phép kiểm liên quan đạt trong 49,42 giây;
kiểm mã đạt. CI `37587663500` hoàn tất success, gồm PostgreSQL, backend,
giao diện, đóng gói ảnh và xuất PDF tiếng Việt. Mã ảnh đọc trực tiếp từ GHCR
theo thẻ commit, HTTP 200:
`ghcr.io/dbp3206-source/veridra@sha256:d33051adc30ea6ff64b766958ef50943f7b52d020bdafe0dc2b7ec45c68dd953`.
Bước triển khai Render skipped; cần đổi nguồn ảnh trong Settings.
Không đổi current_results hoặc ghi lỗi Vinamilk đã hết trên cloud trước khi
triển khai và đối soát thật. Không triển khai ảnh trung gian 0ae3dcb.

**Vinamilk trên 35183a5 — lỗi định tuyến đã xác định:** lượt
`c848fa59-415c-4f0e-97b1-1f805b20b71c` thất bại lần xử lý đầu, không có
câu trả lời. Supabase audit ghi ToolScopeError / unavailable_tool:
web_research bị gọi trong nhóm chỉ có calculate/local_source_read/local_source_search.
Điều khiển đầu vào đều auto. Nhật ký Render xác nhận cùng mã yêu cầu.
Nguyên nhân: nhu cầu có bối cảnh giả lập/tài liệu nên không thuộc bộ tìm tin
thuần công khai; đường đọc website doanh nghiệp chỉ nhận cụm “website/trang web
chính thức”, bỏ sót “tìm nguồn công khai thật từ URL”. Đã tái hiện ba biến thể
đều thất bại bằng kiểm mã trước sửa, không gọi Gemini. Mở rộng nhận diện rõ
nguồn công khai được chọn, dùng lại luồng thu thập theo tên miền và tổng hợp;
không gửi bối cảnh thư vào tìm web, không bỏ kiểm quyền. Giữ ca thật FAIL đến
khi kiểm bản sửa trên cloud; không coi lỗi này là hết hạn mức hay website chết.

**Sửa giới hạn suy diễn sau W02 — chưa chứng nhận câu trả lời thật:** dấu vết
ba lượt xác nhận đúng dữ kiện/ngày giờ, không gọi nguồn ngoài. Lượt đầu tự thêm
hiện trạng thiếu phân loại/công cụ; lượt hai giữ suy diễn đó trong khi chỉ đổi
ngày. Quy tắc chung trước đây yêu cầu tách giả định nhưng chưa chỉ rõ mục tiêu
không chứng minh nguyên nhân và câu trả lời trợ lý không phải nguồn xác nhận.
Bổ sung hai ranh giới này trong SYSTEM_PROMPT dùng chung cho các tuyến điều phối,
không thay đáp án hoặc lọc từ riêng An Bình. 65 phép kiểm ADK/LangGraph đạt;
kiểm mã và diff đạt. Phép kiểm mới chỉ chứng minh mọi vai trò nhận quy tắc,
không chứng minh mô hình luôn tuân thủ. Bản cloud vẫn là 35183a5; chưa triển khai
sửa này hoặc đổi W02 thành đạt toàn bộ.

**W02 trên 35183a5 — đã đối soát ba lượt người dùng chạy:** đọc riêng phiên
`d3bbbdd9-98b5-4dc2-a7ff-d588711c540b` qua Supabase, không chạy lại mô hình.
Mã lượt: `aee053c7-99e2-42bd-882d-e36cf235cb97`,
`e6f75b57-b183-45fa-9467-4164065e0894`,
`9a6fc289-ad50-4a02-805c-c566de9bfa08`. Lượt cuối giữ đúng An Bình,
14/10/2026 09:00, ngân sách chưa xác nhận, đủ ba câu hỏi; không trả giờ máy chủ.
Lượt hai có bốn đề mục xuống dòng riêng, 143 từ tách bằng khoảng trắng.
Đạt phần ghi nhớ/định dạng; chưa kiểm trực quan thanh bên. Hai lượt đầu khẳng
định quy trình thủ công, thiếu phân loại/công cụ tra cứu khi đầu vào chưa có
bằng chứng đó. Đây là hạn chế nội dung, không đổi toàn chuỗi thành đạt.
Các dấu vết lưu không có lượt gọi công cụ nguồn hay ghi Google.
Không cấp điểm E từ kết quả riêng này. Phép đọc dữ liệu thay cho việc chờ
công cụ thanh bên đã tháo điểm chặn thu thập kết quả W02.

**35183a5 đã lên GitHub và qua toàn bộ kiểm:** lúc 13:43 ngày 07/10 đã
đẩy staging từ 2418357 đến 35183a5d611f5f4ba3957f9e25b2f57a00c38d32.
Lượt 37583117325 hoàn tất thành công, gồm PostgreSQL, backend, giao diện,
dựng ảnh, kiểm đóng gói và xuất PDF tiếng Việt. Mã ảnh công khai đọc theo
đúng thẻ commit:
sha256:4b0016d9dd4414f6490749e1126ca544a8141d901ae18913e8495b1d09a42c89.
Bước tự triển khai Render có kết luận skipped. Người dùng đã đổi nguồn ảnh;
Render xác nhận dep-db2urke7bikc73b3l220 Live lúc 07:01:44 UTC ngày 07/10,
đúng mã ảnh trên. /api/health trả status=ok, database=true,
object_storage=true; runtime_started_at=2026-10-07T14:01:34.354062+07:00.
Đóng bước 1, không coi đây là bằng chứng đạt các ca câu trả lời A/B.
Công cụ điều khiển trình duyệt thanh bên chưa được cung cấp trong phiên này.
Đây là bước triển khai trong năm bước đã khóa, không thêm hạng mục hoặc
dùng bộ kiểm mã để cấp điểm chất lượng. Mục tiêu vẫn chưa hoàn tất.

**Chuẩn bị E, không tiêu lượt mô hình:** trên ef04f01 đã mở lại kết quả
Mộc An 5cbbce8b-70de-4fe6-8078-2ea3a474ce5d, bản 2, ngân sách chưa xác nhận
và đúng bốn câu hỏi; không sửa/lưu mới/xuất mới. Ảnh
acceptance-ef04f01/stored-result-readback.jpg. Bài demo đã sửa ngày và mã
lượt Bosch đúng 07/10, chỉ rõ báo cáo này còn chưa đạt đầy đủ, không gán
trạng thái thành công từ bằng chứng lịch sử. Không thay thế W06 toàn chuỗi
hay điểm E bằng việc mở lại này. Giữ bài demo ở trạng thái chuẩn bị cho
đến khi bản cuối đóng A/B/E/F.

**B — W02 chưa đạt trên ef04f01:** ba lượt thật eab49d78/2a2dc0a6/21a918dd
(13,6 / 14,7 / 10,9 giây). Hai lượt đầu giữ An Bình, ngân sách chưa xác nhận
và đổi riêng ngày hẹn từ 12/10 sang 14/10/2026, giờ 09:00. Lượt hai sau
viết lại bị dính tiêu đề; lượt cuối trả thời điểm máy chủ thay ngày giờ cuộc
hẹn. Không có công cụ đọc nguồn riêng hoặc ghi Google trong dấu vết.
Không ghi đạt từ việc hai lượt đầu đúng. Ngân sách khóa còn 9/16; không
chạy lặp cùng ca trước triển khai sửa. Ảnh w02-turn1/2/3.jpg trong
acceptance-ef04f01.

Nguyên nhân cấu trúc được xác định trong mã: tuyến ADK chuẩn hóa trước
nhưng không sau lượt viết lại. Đã dùng cùng phép chuẩn hóa không đổi dữ kiện
sau lượt cuối, đồng thời thêm ràng buộc nguồn chỉ có tiêu đề cho tuyến ADK.
48 phép kiểm ADK đạt, gồm ca viết lại làm dính tiêu đề và ca suy diễn ra mắt.
Về ngày hẹn: có ghi nhận nạp hội thoại nhưng đầu vào còn gắn đồng hồ máy chủ
chưa nói rõ phạm vi sử dụng. Bổ sung quy tắc dùng đồng hồ chỉ cho ngày tương
đối, không thay ngày sự kiện trong hội thoại. Đây là hướng sửa cần kiểm thật
sau triển khai, chưa chứng minh riêng lời nhắc này đủ đóng lỗi nhớ ngày.
94 phép kiểm ADK/thông tin thời gian đạt sau bổ sung quy tắc này, gồm kiểm
đầu vào thực của tuyến điều phối có quy tắc phân biệt đồng hồ/ngày hẹn.
Đợt sửa web đầu đã lưu local tại 64c5fe0; kiểm cuối nguồn/điều phối 138 phép
đạt trong 94,52 giây; quét 557 tệp không phát hiện bí mật. Chưa đẩy lên cloud.

**Đợt sửa chung đang ở local, chưa triển khai:** nguyên nhân ca company-02
không nằm riêng ở Vinamilk: bước tổng hợp có thể biến nguồn chỉ có tiêu đề
thành lời khẳng định về sự kiện. Đã ràng buộc đầu ra ở cả hai tuyến điều phối:
dòng dẫn nguồn loại này chỉ giữ tiêu đề, ngày đăng và giới hạn chưa xác minh;
loại liên kết không còn được dùng sau xử lý. Thu thập tin loại các tiêu đề
trống giả như undefined, kể cả có hậu tố ngày và nhà xuất bản. Nếu xử lý
làm vi phạm yêu cầu trình bày đã khóa thì trả trạng thái chưa hoàn tất,
không báo thành công sai. Đây không phải bằng chứng xác minh mọi nhận định
không dẫn nguồn. 179 phép kiểm nguồn/điều phối/web/cuối khóa đạt trong
67,90 giây, kiểm mã và diff đạt. Chưa chứng nhận A hoặc điểm bộ đo từ kiểm local.
Lệnh đẩy trước bị bộ duyệt chặn vì hạn mức, thời điểm thử lại được báo là
13:42 ngày 07/10; không dùng đường khác để vượt chặn. Giữ nguyên năm bước,
không thêm tính năng hay yêu cầu khóa mới.

**company-02 trên ef04f01 chưa đạt:** lượt
`f577d8bf-5a49-4178-973c-2232aa8875ef` hoàn tất 21,4 giây, web_research
thành công, tám nguồn, ba câu hỏi làm rõ. Tuy nhiên câu “Ra mắt sản phẩm mới”
dẫn [5,6] là các nguồn loại headline chỉ ghi tên sản phẩm và ngày đăng,
không chứng minh hành động ra mắt. Danh sách còn tiêu đề undefined [8].
Nguyên nhân cần xử lý chung: thu thập RSS chưa loại tiêu đề rác; kiểu nguồn
được giữ trong bằng chứng nhưng chưa ràng buộc được cách diễn giải tiêu đề
trong câu trả lời tự do. Nhắc bằng prompt chưa đủ chứng minh chặn suy diễn.
Không ghi PASS hoặc điểm thật từ việc đủ đề mục. Không gọi nguồn riêng/ghi
Google. Khóa Veridra2 hoạt động, sau ca này còn 13/16; không phải đang bị
chặn do không có ngân sách. Giữ lượt cho kiểm sau sửa, không lặp các ca cùng lỗi.
Ảnh: `design-work/qa/acceptance-ef04f01/vinamilk-web-trace.jpg`.

**B — W04 đạt trọn ba lượt trên ef04f01:** đầu vào tháng 1 là 120 triệu,
tháng 2 là 150 triệu → chênh 30 triệu, tăng 25%; sửa riêng tháng 2 thành 144
→ chênh 24 triệu, tăng 20%, giữ tháng 1; lượt cuối hai câu giữ đúng số đã
sửa và đơn vị, không quay về 150/30/25 hoặc tự gán tên chỉ tiêu kinh doanh.
Ba lượt đều dùng calculate; không đọc nguồn riêng hoặc ghi Google. Định danh:
7671705c-ba12-4e42-ace2-6d51a51e3ba3 (12,7 giây),
6f818d40-b986-4e13-9590-5d709103117a (20,9 giây),
efa16082-c7f4-42a8-9470-933921b50afe (21,9 giây).
Ghi kết quả thật vào manifest đã khóa, không thêm ca; không đóng toàn B/E
từ một chuỗi. Ảnh w04-turn1/2/3.jpg ở acceptance-ef04f01.
Khóa đang dùng sau chuỗi còn 1/16 lượt mô hình; không đủ cho một ca web
cần ba lượt. Kiểm trang Cài đặt thấy khóa Veridra2 đã lưu, đang bật dự phòng,
chưa dùng ngân sách hôm nay. Chọn chính khóa có sẵn này; màn hình xác nhận
Veridra2 đang dùng, còn 16/16. Không thêm khóa, tăng giới hạn hoặc đặt lại
bộ đếm. Số này không phải hạn mức Google đã xác minh. Ảnh:
`design-work/qa/acceptance-ef04f01/existing-key-selected.jpg`.
Không gọi lặp để chọn kết quả đẹp.

**ef04f01 qua CI:** lượt 37563231626 hoàn tất thành công, gồm PostgreSQL,
backend, giao diện và ảnh chạy. Ảnh công khai đối chiếu theo đúng commit:
`sha256:0f26be48e572d73e98a237ab5675952774bfe7f0abd309be1554f2d1d07a1f59`.
Render nhận ảnh này trong đợt dep-db2r5dks728c73abmc6g lúc 02:47:18 UTC,
Live lúc 02:49:04 UTC ngày 07/10. Ảnh bằng chứng:
`design-work/qa/acceptance-ef04f01/render-live.jpg`. Chưa ghi nghiệp vụ đạt
chỉ từ trạng thái triển khai hoặc kiểm tự động.

**Kiểm báo cáo sau sửa trên ef04f01:** lượt
`773e348f-8b36-4f7b-9dc4-eb1ff1303efb` hoàn tất 28,5 giây, web_research
thành công, sáu nguồn. Đủ ba câu hỏi do mô hình tạo; tách ngày đăng/ngày sự
kiện chưa xác minh, phạm vi tập đoàn/đơn vị Việt Nam và trạng thái chỉ đọc.
Không đọc nguồn riêng hoặc ghi Google. Đóng riêng lỗi bỏ câu hỏi.
Vẫn chêm tên lĩnh vực tiếng Anh trong giải thích; không ghi toàn bộ A hoặc
company-06 đạt đầy đủ. Ngân sách từ 9/16 còn 6/16; không chạy lại Bosch.
Ảnh: `design-work/qa/acceptance-ef04f01/bosch-web-trace.jpg`.

**Sửa nguyên nhân bỏ câu hỏi trong báo cáo:** phép kiểm qua bộ điều phối thực
tái hiện đầu ra chỉ bắt buộc answer/proposals, không bắt buộc câu hỏi làm rõ.
Một ca thất bại trước sửa. Bổ sung trường ba câu hỏi khác nhau, không rỗng,
do mô hình tạo trong chính lượt tổng hợp; kiểm dữ liệu trước khi hiển thị,
kiểm độ dài gồm cả câu hỏi và chặn nếu bước chỉnh cách trình bày làm mất
câu hỏi. Không thêm câu hỏi sau kiểm độ dài, không chèn câu mẫu hoặc dữ kiện giả.
Giữ lượt sửa cấu trúc có giới hạn đã có, không đọc lại nguồn hoặc ghi Google.
Kiểm cả ca thiếu trường được sửa một lần và ca đúng chỉ dùng một lượt;
203 phép kiểm điều phối/định tuyến/cuối khóa/cấu trúc tạo
đạt; kiểm mã, diff và bí mật đạt (557 tệp). Đang triển khai ef04f01, chưa
đóng A từ kiểm tự động. Nhắc diễn đạt bằng tiếng Việt trong lượt tổng hợp,
không tuyên bố đã chứng minh mọi cách diễn đạt ngoài mô hình kiểm.

**B — mở lại kết quả trên fea3e65:** màn hình Kết quả đã lưu mở đúng mục
`5cbbce8b-70de-4fe6-8078-2ea3a474ce5d`, bản 2, đủ bốn câu hỏi và ngân sách
chưa xác nhận; không gọi mô hình, không sửa bản. Chỉ chứng minh mở lại hiện
tại, không coi là lần tạo/sửa/xuất mới. Ảnh:
`design-work/qa/acceptance-fea3e65/stored-result-readback.jpg`.
Tìm riêng QA-FINAL-8ad36c0 trên màn hình Bộ nhớ trả không có kết quả (gồm
danh sách đang dùng và đã cất). Không xóa hoặc tạo lại dữ liệu. Ảnh:
`design-work/qa/acceptance-fea3e65/deleted-memory-search.jpg`. Đây là đối soát
trạng thái lưu hiện tại, không thay thế kiểm hỏi lại qua mô hình.

**fea3e65 đã triển khai:** CI 37561245089 thành công; Render
dep-db2qrvcs728c73aakps0 Live lúc 02:28:54 UTC ngày 07/10/2026, ảnh
`sha256:1e4e73a294e45da394bbcf5f7ba9e908bdbe43d5c6c46e4a9dd93f7497fefa54`.
Giữ đúng năm bước trong FINAL-FIVE-STEPS.md, không thêm phạm vi nghiệm thu.

**Kiểm gộp Bosch trên fea3e65:** lượt `8c2b8502-c89b-4a75-836b-b662fa116651`
hoàn tất 27,3 giây; web_research thành công, sáu dẫn nguồn. Câu trả lời giữ
phạm vi quy mô toàn cầu, ghi chưa xác minh đơn vị Việt Nam, giới hạn chỉ đọc
tiêu đề tin/chưa xác minh ngày sự kiện; trạng thái chỉ đọc, chưa gửi thư,
tạo tài liệu hoặc đặt lịch. Tuy nhiên thiếu ba câu hỏi làm rõ đã khóa;
còn dùng thuật ngữ tiếng Anh trong giải thích. Chưa đóng company-06/A.
Ngân sách giao diện từ 12/16 còn 9/16, không đặt lại bộ đếm. Không gọi
nguồn riêng hoặc thao tác ghi Google trong phép kiểm này. Bằng chứng:
`design-work/qa/acceptance-fea3e65/bosch-web-trace.jpg`.

**Nguyên nhân và sửa gộp bằng chứng web sau 9169e79:** bộ tạo dẫn chứng gán
cùng 500 ký tự đầu của tóm tắt cho mọi URL và bỏ các trường ngày nguồn.
Kiểm xác định với hai nguồn khác nhau thất bại đúng ở đoạn trích trùng nhau.
Sửa chung: nguồn trang giữ văn bản đã đọc; tin dạng tiêu đề giữ riêng tiêu đề,
ngày đăng và giới hạn chưa đọc toàn văn/chưa xác minh ngày sự kiện; nguồn do
nhà cung cấp đối chiếu giữ riêng đoạn được hỗ trợ, không cả văn bản không nguồn.
Dẫn chứng bảo toàn loại bằng chứng, ngày đăng/ngày sự kiện/thời điểm kiểm tra;
không dùng tóm tắt chung làm bằng chứng cho mọi liên kết. Bổ sung quy tắc tổng
hợp phân biệt các ngày, phạm vi tập đoàn/đơn vị, câu hỏi cần làm rõ và trạng thái
hành động chỉ đọc/chưa thực thi. Không tự thêm biên nhận duyệt hoặc thao tác ghi.
172 phép kiểm định tuyến/web/dẫn chứng/tổng hợp đạt, gồm một ca qua bộ điều phối
thực với ranh giới mô hình thay thế; kiểm mã và bí mật đạt. Kết quả live
ghi ở trên; không ghi company-06 hoặc điểm nghiệp vụ đạt từ kiểm tự động.

**9169e79 đã triển khai và kiểm URL thật:** CI 37559845504 thành công.
Render dep-db2qikss728c73a9i3m0 Live lúc 02:09:00 UTC ngày 07/10, ảnh
`sha256:e5af206ec2fdc2ecb41d9de2866c986128bf8c54d38d3b337209e2dd1bad3af2`.
Kiểm nguyên yêu cầu Bosch trước sửa, không đổi đầu vào để dễ đạt. Lượt
`a48bf09c-3662-4e81-8cec-53c91d539681` hoàn tất 28,4 giây; dấu vết có
`web_research` thành công và sáu nguồn hiển thị. Đã hết lỗi trả từ bộ nhớ
thay vì đọc website. Câu trả lời tách quy mô toàn cầu khỏi Việt Nam, không
tự gán lịch/ngân sách. Tuy nhiên ngày tin không phân biệt rõ ngày đăng với
ngày sự kiện, và thiếu trạng thái duyệt rõ ràng: chưa đóng company-06/A.
Giao diện ngân sách còn 12/16, không đồng nhất một câu hỏi với một lượt
dịch vụ. Không gọi thêm mô hình, Gmail hoặc thao tác ghi Google trong đợt này.
Ảnh bằng chứng riêng ở `design-work/qa/acceptance-9169e79/`; không có khóa
hoặc thư thật. Danh sách kết thúc cố định: [năm bước](FINAL-FIVE-STEPS.md).

**Đối soát ngày 07/10:** Vault của dự án đang chạy đã có mục bí mật hẹn giờ;
chỉ kiểm trạng thái tồn tại, không đọc giá trị. Bản a75b722 đã qua CI
37558493700 và triển khai thành công trong đợt dep-db2qaqe7bikc73ajmn3g,
Live lúc 01:52:17 UTC. Ảnh triển khai:
`sha256:adf2c4bc26232b46792756c162295dcf8571515f1f3a54b729c1c5e6efe3e3be`.

Một lần kiểm thật hồ sơ Bosch trên bản này chưa đạt: câu trả lời không có
lần đọc web trong dấu vết, dù đầu vào yêu cầu dùng website chính thức.
Nguyên nhân đã tái hiện bằng kiểm thử không gọi mô hình với khách hàng khác:
đầu vào giả lập không đi qua tuyến thông tin mới; tuyến website riêng chỉ
nhận “hồ sơ/doanh nghiệp/công ty”, bỏ sót “khách hàng/báo cáo tư vấn”.
Bổ sung hai cách diễn đạt nghiệp vụ vào tuyến website được chọn, giữ nguyên
việc không gửi tên liên hệ/đầu vào riêng vào truy vấn và chặn khi cấm web.
Trước sửa: một ca thất bại, một ca cấm web đạt. Sau sửa: 99 phép kiểm định
tuyến, giới hạn nguồn và yêu cầu cuối khóa đạt. Thay đổi định tuyến chưa
triển khai và chưa được kiểm lại trên URL thật; không ghi ca Bosch đạt.
Ngân sách ngày mới được ứng dụng cập nhật tự nhiên, không đặt lại bộ đếm;
sau lần kiểm này giao diện báo còn 15/16 lượt ở khóa dự phòng đang dùng.

**Sửa chung bộ nhận bằng chứng web, đã triển khai trong a75b722:** nhánh trả lời công ty
trước đây cho phép dùng nguyên văn mô hình nếu có liên kết nhưng không có
đoạn nhận định được nhà cung cấp đối chiếu. Câu hỏi thời sự đã chặn trường
hợp này, còn công ty bị ngoại lệ `company_name`. Bỏ ngoại lệ và chỉ chuyển
các đoạn có đối chiếu nguồn sang bước tổng hợp. Kiểm cả “không nguồn”,
“có liên kết nhưng không đoạn hỗ trợ” và “có đoạn hỗ trợ lẫn câu không nguồn”:
71 phép kiểm web/thông tin cập nhật đạt, kiểm mã đạt. Lần đầu ca giả lập
“đạt” cũ chỉ có liên kết nên bị chặn đúng; bổ sung dữ liệu hỗ trợ nguồn cho
ca dương và kiểm câu ngoài bằng chứng không lọt qua. Không gọi Gemini thật.
Không coi thay đổi này đã chứng minh sáu báo cáo doanh nghiệp đạt, hoặc
đã khắc phục đầy đủ phạm vi Việt Nam và ngày sự kiện.

**Hẹn giờ sáng thực tế đã đạt trên bản fc4733d.** CI 37489514010 thành công;
Render dep-db2hgg7lot8c73f7miig Live lúc 15:50:13 UTC với ảnh
`sha256:7ffdb94acb7929155bf212033468713d8ac8326660b203921b74eac57d7f1c10`.
Cron kích hoạt lúc 15:51 UTC, tự tắt (active=false); HTTP trả 202.
Tác vụ 38117567-629a-4e0f-aed0-2a6cfee07e44 hoàn tất trong lần đầu,
không lỗi, đọc 5/5 cuộc trao đổi và metadata 5 tệp. Nhật ký gồm một lần
liệt kê Gmail, năm lần đọc cuộc trao đổi và một lần liệt kê Drive, đều đạt;
không gọi Gemini hay ghi Google. Lưu tại phiên
c50be749-3206-4089-8adc-bb5d163ada36. Không lưu nội dung thư hoặc bí mật
trong bằng chứng. Không bật lịch lặp dài hạn từ phép thử một lần này.
Chỉ đóng mục hẹn giờ sáng; A/B/E/F toàn nhóm chưa đủ điều kiện đóng.

### Trạng thái còn lại sau lần kiểm hẹn giờ

| Nhóm | Phần còn thiếu |
|---|---|
| A | Hồ sơ chưa đủ đối soát nguồn/tin hiện tại; chuỗi xem trước → duyệt → đọc lại chưa đóng toàn bộ. P06 đã hoãn, không kiểm lại. |
| B | Hẹn giờ sáng đã đạt; lịch hiện trống nên chưa chứng minh chuẩn bị cuộc hẹn có dữ liệu thật; chưa đủ dấu vết toàn bộ bảy vai trò trong chuỗi nghiệp vụ. |
| E | Chưa đủ kết quả đạt của 24 tác vụ; không có điểm tổng hợp hợp lệ. Ngân sách ngày mới còn 15/16 lượt sau một lần kiểm; không đặt lại bộ đếm hoặc yêu cầu thêm khóa. |
| F | Đã kiểm tải mới, cài đặt và dựng giao diện của fc4733d; có kịch bản 10 phút và bộ mẫu/đáp án. Đăng nhập Google và khóa riêng trên bản tải sạch chưa kiểm đủ. Chưa gộp main khi A/B/E còn thiếu. |

### Bằng chứng bàn giao từ bản tải sạch

**Đối soát xuất bản đã lưu trên fc4733d:** mở đúng kết quả giả lập Mộc An
`5cbbce8b-70de-4fe6-8078-2ea3a474ce5d`, phiên bản 2, trên URL thật.
Tải Markdown, DOCX và PDF bằng chính liên kết xuất của giao diện. Cả ba
chứa đúng tiêu đề, ngân sách chưa xác nhận và đủ bốn câu hỏi của bản mới;
không phải bản cũ ba câu hỏi. PDF một trang A4 được dựng bằng Poppler và
kiểm trực quan: chữ tiếng Việt rõ, không cắt hoặc chồng chữ. Không gọi
mô hình, không cập nhật bản lưu hoặc ghi Google trong lần đối soát này.
DOCX mở và trích văn bản được nhưng chưa kiểm bố cục: trình dựng tài liệu
đi kèm báo `LibreOffice soffice.exe was not found on PATH`. Không dùng
kết quả PDF do Veridra xuất để thay bằng chứng bố cục DOCX. Đây là bằng
chứng phần xuất/mở lại của W06; không tự coi toàn chuỗi W06 trên cùng bản đạt.

Ngày 06/10/2026, tải nhánh thử nghiệm từ GitHub vào thư mục riêng rồi chọn
đúng fc4733d. Trước cài đặt không có `.env` hoặc tệp OAuth; không sao chép
khóa hay phiên đăng nhập của môi trường đang dùng.

- `scripts/setup.ps1` hoàn tất: tạo môi trường Python riêng, cài từ bản khóa
  phụ thuộc, chạy `npm ci`, tạo cấu hình local và bí mật ngẫu nhiên.
- `npm run build --prefix frontend` thành công, dựng 4.491 mô-đun.
- Ngày 07/10, khởi động chính backend bản tải sạch ở cổng thử 8012.
  Hoàn tất khởi động; `/` và `/api/health` trả HTTP 200, cơ sở dữ liệu và
  kho vector riêng được khởi tạo. Sức khỏe báo đúng Google/Gemini chưa
  cấu hình, không coi là đã thử kết nối hai dịch vụ. Lần gọi trước khi
  khởi động hoàn tất bị từ chối kết nối; lần sau mới đạt. Đã dừng tiến
  trình thử riêng, không đụng tiến trình local đang dùng của người dùng.
- Kiểm cấu hình xác nhận phần local hợp lệ nhưng báo thiếu khóa Gemini và
  OAuth. Đây là phần chưa hoàn tất, không phải bằng chứng đăng nhập đạt.
- Không dựng Docker trên máy. Ổ C còn khoảng 11,77 GB sau cài đặt.
- Bộ cài phát hiện cảnh báo thư viện: `source-map-js` mức cao nằm trong
  công cụ dựng, không được đưa vào ảnh máy chủ; KaTeX/Mermaid mức thấp
  còn cần đánh giá. Không sửa cưỡng bức phụ thuộc hoặc tuyên bố đã sạch
  cảnh báo chỉ vì dựng được giao diện.

Kịch bản trình bày: [DEMO-10-PHUT.md](DEMO-10-PHUT.md). Bộ mẫu và đáp án
độc lập: [manifest.json](demo/manifest.json). Hai tệp mẫu có mã SHA-256 được
đối chiếu; toàn bộ dữ kiện khách hàng trong bộ này là giả lập. Phương án
xem lại khi hết hạn mức được ghi rõ, không thay cho một phép kiểm mới.

### Lịch sử đối soát trước đó

Các đoạn dưới giữ bằng chứng tại thời điểm của từng bản, không thay trạng thái
mới nhất ở trên. Nhận xét “chưa triển khai”, “chưa có Vault” hoặc “chưa có lịch”
trong lịch sử không mô tả hiện trạng sau fc4733d.

Bản 239317f đã qua CI 37485692007, triển khai Live trên Render bằng ảnh
`sha256:c540782728f23f2a533af148781e93943e5fc41cf79a86b50a5424c1845471c3`,
đợt `dep-db2h888m7kps73ervvn0`, 15:32:37 UTC ngày 06/10/2026. Phép kiểm
Bosch sau sửa hoàn tất 29,8 giây: phần thân, bảng nguồn và thẻ liên kết khớp
mã. Không coi cả hồ sơ đạt: tin chưa chứng minh liên quan Việt Nam, chưa tách
ngày sự kiện và chưa có số liệu riêng của đơn vị Việt Nam.

Vault đã được xác nhận tồn tại đúng tên, không đọc giá trị. Bật pg_cron 1.6.4
và pg_net 0.20.4. Lịch thử tự tắt bằng cron.alter_job sau lần chạy thành công
lúc 15:36 UTC; không có lịch lặp đang bật. Lần đầu dùng UPDATE cron.job bị
chặn quyền, chưa phát sinh yêu cầu HTTP. Lần sau gọi HTTP nhưng nhận 403:
“Yêu cầu ghi phải bắt nguồn từ giao diện Veridra.” Chưa đọc Gmail/Drive,
chưa có tác vụ ứng dụng được tạo. Nguyên nhân: lớp kiểm nguồn trình duyệt
áp nhầm vào điểm gọi máy chủ đã có xác thực bearer riêng. Sửa đúng một đường
dẫn hẹn giờ; vẫn bắt buộc bearer, không miễn toàn bộ tiền tố API nội bộ.
Chưa đóng mục hẹn giờ trước khi kiểm lại trên bản triển khai có sửa này.

Bản `c27862b` đã qua CI `37482088860` và chạy Live trên Render. Lượt web
`e4250a0b-245e-4db1-accb-5ce54611500e` hoàn tất 26,5 giây, tin đúng FPT;
không còn dừng tất cả nguồn khi website bị chặn. Website chính vẫn chưa đọc
được nên hồ sơ đầy đủ chưa đạt. Hỏi tiếp sau mở lại hội thoại, lượt
`a62f6689-21bb-4fe5-bee1-9129e4f7ee12`, giữ đúng ngày 14/10/2026, 09:00,
ngân sách chưa xác nhận và ba câu hỏi; 16,8 giây, không tìm web.

Ca đối chứng Bosch `d4cc10b8-5a17-4303-abbe-fddb1b13ab9d` đã đọc website,
28,6 giây, nhưng bảng nguồn có mã `[S#]` không khớp phần thân `[n]` sau đánh
lại số. Nguyên nhân chung: bộ đánh lại số chỉ nhận `[n]`, không nhận `[S#]`
do công cụ web cung cấp. Sửa chung để hai dạng dùng cùng ánh xạ; không đổi
nội dung nguồn, không gắn ngoại lệ theo công ty. 77 phép kiểm nguồn, trích
dẫn theo trang và điều phối đạt; kiểm mã và khoảng trắng đạt. Bản sửa này
chưa được xác nhận trên URL thật, không coi Bosch đã đạt toàn bộ nghiệp vụ.

Hẹn giờ: project đang chạy chưa có pg_cron/pg_net hoặc cron.job; kiểm lại
Vault vẫn chưa có tên `veridra_scheduler_bearer_token`. Chỉ kiểm sự tồn tại,
không đọc giá trị bí mật. Chưa tạo lịch thử khi thiếu bí mật; chưa coi hẹn
giờ đạt. P06 tiếp tục hoãn; E chưa đủ mẫu; F chưa gộp main.

Danh sách điều hành được người dùng yêu cầu tinh gọn. Đợt demo chỉ còn bốn nhóm
bắt buộc A, B, E và F. Nhóm C và D được chủ sở hữu loại khỏi đợt nghiệm thu này
ngày 06/10/2026 để tránh kéo dài tiến độ. Không thêm tính năng hoặc thiết kế lại.
Tiêu chí chưa có bằng chứng giữ chưa đạt.

## Chốt thứ tự theo yêu cầu mới ngày 06/10/2026

Không tiếp tục vòng sửa hoặc gọi mô hình để kiểm PDF trong đợt này. Ca P06
được **để bản sau**, không đổi thành đạt và không xóa kết quả trước đó.
Không mở thêm hạng mục; ưu tiên web, đối soát A/B rồi E/F. Một mục để sau
không đồng nghĩa cả nhóm hoặc toàn sản phẩm đã đạt nghiệm thu.

| Nhóm | Trạng thái đối soát | Bước còn lại, không mở rộng |
|---|---|---|
| A | Ca đổi đầu vào An Bình đã đạt; PDF P06 để sau; báo cáo/dẫn nguồn/bản xem trước chưa đủ bằng chứng đóng toàn nhóm | Không chạy lại PDF; giữ các mục chưa đạt trong biên bản |
| B | Có đọc đầu ngày, lưu/đọc lại, quy trình đã lưu và kiểm nhớ/sửa/xóa; lịch trống; chưa có lần hẹn giờ thật | Kiểm đúng một bản tin đã được cho phép; không coi bấm tạo thủ công là hẹn giờ đạt |
| E | Chưa đủ 24 tác vụ và chưa có điểm tổng hợp hợp lệ | Chỉ tổng hợp bộ đã khóa; kết quả lỗi/thiếu dữ liệu không được chấm đạt |
| F | Bản 947d8ae đã qua CI và chạy Live; hướng dẫn và mẫu có sẵn; main chưa gộp | Chốt tài liệu đúng phạm vi; chỉ gộp bản đã đủ điều kiện, không gọi bản demo hạn chế là production-ready |

Web trên 947d8ae: yêu cầu `1c5cfadf-82d3-4cd7-895f-83ac592697c1`
bị chặn `unavailable_tool`: công cụ `web_research` không nằm trong tập công
cụ được cung cấp. Đã tái hiện độc lập với URL khác: thêm câu phủ định
“không đọc tài liệu riêng” làm bộ phân loại chọn trợ lý bộ nhớ thay vì
nghiên cứu web. Nguyên nhân là bộ lọc bảo vệ nguồn riêng chưa nhận diện
đúng cụm phủ định này, không phải đã chứng minh website nguồn mất kết nối.
Sửa chung chỉ nhận diện các cụm phủ định hoàn chỉnh; dữ liệu riêng được
nêu khẳng định vẫn chặn tìm web. 230 phép kiểm định tuyến, quyền công cụ,
hội thoại và xử lý câu trả lời đạt; kiểm mã đạt. Chưa kiểm live sau sửa,
không gửi lại cùng câu hỏi trên bản chưa đổi.

Ảnh Live 947d8ae: `sha256:6c9b6e6177d08f760a7911a717da32ed4c1bfe10cb6743fc29560aab5a06f5b5`;
CI `37459390271` thành công; Render `dep-db2e5t3ncjis73ed0jt0` Live lúc
12:02:49 UTC. Đây là bằng chứng triển khai, không thay thế điểm nghiệp vụ.

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

### Ưu tiên web, tạm gác PDF — 06/10/2026

- Theo quyết định mới, không tiếp tục dùng lượt mô hình để sửa/kiểm P06; mục này
  được hoãn, không ghi đạt. Không mở thêm phạm vi nghiệm thu.
- Bản `d514dc9`: CI `37461715990` đạt, ảnh
  `sha256:bf34cacbd523a69795c91cc276327556c2a25e7f91439a2dee37053752d6ff3a`
  chạy trên Render `dep-db2eeurbc2fs738b5hl0`. Câu hỏi web U04
  `ddc79210-a062-4b19-a0b2-c18eacac5263` đạt: đọc đúng trang Google,
  trả lời hạn mức theo dự án và dẫn nguồn; 32,7 giây. Bước tìm lại ghi chú đã
  quên W03 `1f0b2787-cb91-420a-97af-6adbfe9b0d76` đạt, 30,5 giây.
- Ca FPT `d6ba9fe9-85af-4a9c-8aed-16fb06a8f432` chưa đạt. Nhật ký Render
  xác nhận website trả HTTP 403 ba lần lúc 12:27:32–12:27:33 UTC. Không phải
  lỗi DNS hay hết hạn mức đã được chứng minh: cơ chế bắt mọi HTTPError thành
  lỗi truyền tải, thử lại lỗi bị từ chối và để một website làm dừng toàn bộ
  việc thu thập nguồn. Không tuyên bố đã đọc trang bị chặn.
- Sửa cơ chế chung: 403/404 không thử lại; 408/429/5xx vẫn thử lại có giới hạn.
  Thu thập website và tin công khai độc lập, đồng thời. Chỉ tạo dẫn nguồn cho
  dữ liệu thực sự đã đọc; nguồn tin còn dùng được giữ lại cùng cảnh báo chưa
  đọc được website. Tiêu đề tin không được biến thành dữ kiện toàn văn.
  Chặn địa chỉ mạng nội bộ vẫn giữ nguyên; không vượt bảo vệ website.
- Chưa đóng A/B/E/F hoặc gộp main từ các kết quả riêng này. Cần kiểm bản sửa
  web trên URL sau triển khai và hoàn tất các mục còn lại đã khóa.
- Bản `ab08afa` đã qua CI `37464793196`, Render
  `dep-db2er2p42hec73a9p4b0` Live với ảnh
  `sha256:6d20ac2fd14cbfe949230af385a45cd1de3de4946ec2740c8d03dcac9eedf6b8`.
  Lượt `f2880409-2753-4a77-97ee-00d2e3e3d24f` hoàn tất 25,9 giây, web thành
  công 6,97 giây; đã nói chưa đọc website, không bịa quy mô. Tin không liên
  quan đủ tới công ty nên vẫn chưa đạt nghiệp vụ. Bộ định tuyến hồ sơ tạo
  câu hỏi tổng quan chung, không có tên công ty; bộ tải nguồn lấy câu hỏi
  chung này làm truy vấn tin. Sửa truy vấn mặc định bám tên miền công khai
  đã chọn, không dùng nội dung liên hệ riêng. Không coi công cụ thành công
  là câu trả lời đạt chất lượng.
