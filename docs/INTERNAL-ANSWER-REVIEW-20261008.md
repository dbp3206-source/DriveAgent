# Kiểm chất lượng nội bộ trước lượt triển khai cuối

## Quyết định

Chưa yêu cầu triển khai. Sau khi người dùng cho phép kiểm tiếp, đã thực hiện
các phép kiểm nội bộ dưới đây; không yêu cầu người dùng chạy lại bản cũ.
Không mở rộng danh sách nghiệm thu; giữ nguyên phạm vi A/B/E/F, hoãn PDF đã thống nhất.

## Đối soát mới nhất — 08/10/2026, sau 09:34 UTC

### Cập nhật sau 13:55 UTC — kiểm gộp, dừng gọi thêm mô hình

Gemini đã trả lời lại; lỗi 503 ở lượt cũ không chứng minh dịch vụ vẫn quá
tải. Không đổi mô hình trả phí, khóa hoặc bộ đếm. Khóa tại máy đã dùng
16/16 lượt bảo vệ, tự đặt lại lúc 14:00 giờ Việt Nam ngày 09/10. Hạn mức
này của Veridra, không phải hạn mức còn lại Google xác nhận.

| Phần cố định | Kết quả và việc còn lại |
| --- | --- |
| A | U01 nội bộ trả đúng ngày máy chủ 08/10, khoảng sự kiện 19/9–4/10/2026 và kết luận đã kết thúc. Company-02 có báo cáo nhưng bỏ quy mô và không nói rõ chưa xác minh tin trong 30 ngày. Chưa đóng sáu doanh nghiệp và các ca cập nhật còn thiếu; không dùng một câu đúng để cấp đạt cả A. |
| B | Giữ các chuỗi hỏi tiếp, nhớ/quên, đổi đầu vào, lưu/mở lại và tài liệu đã duyệt có bằng chứng hợp lệ. W01 lượt đầu còn dưới 200 từ; đã đọc lại dữ liệu thật, không có lỗi ký tự xuống dòng như nghi ngờ. Lịch trống và kiểm hiển thị DOCX còn giới hạn; không chạy lại phần đã đạt. |
| E | Bộ vẫn 24 tác vụ, 23 áp dụng khi hoãn P06; chưa đủ kết quả đạt để chấm điểm. Không dùng kiểm mã làm điểm 8,7/9 hoặc xác nhận bảy vai trò đều đã thực hiện. |
| F | Bản sửa chỉ ở nhánh xem xét; Render vẫn 81665f7, main chưa gộp. Chỉ bàn giao bản đã kiểm và ghi đúng giới hạn, không công bố sẵn sàng vận hành từ CI. |

Nguyên nhân và sửa chung, không gắn cứng đáp án ASIAD hoặc Vinamilk:

1. Câu trích ghép các ô bảng không xuất hiện liên tục trong nguồn; mô hình
   coi nguồn thứ cấp là chính thức. Ưu tiên trang cơ quan khi người dùng
   yêu cầu chính thức, ràng buộc trích nguyên văn và gắn lại số nguồn cùng
   nội dung. Đây là ưu tiên nguồn, không phải chứng nhận mọi trang đúng.
2. Bộ kiểm số chưa nhận ra ngày tiếng Anh và ngày tiếng Việt tương đương.
   Chuẩn hóa ngày đầy đủ hợp lệ và số thứ tự, vẫn chặn ngày sai/thiếu năm,
   số không có trong đúng nguồn và nguồn chỉ có tiêu đề.
3. Mô hình thêm ngày đồng hồ vào một dữ kiện web không có trích dẫn; một
   kết luận sai định dạng khiến cả câu bị từ chối. Tách câu hỏi ngày máy
   chủ khỏi câu hỏi gửi tổng hợp; vẫn dùng đồng hồ để đối chiếu sự kiện,
   trả ngày bằng ứng dụng. Không bỏ bộ kiểm trích đoạn để lấy câu trả lời.
4. Báo cáo có ba câu hỏi bắt buộc nhưng các mục nội dung chỉ là chỉ dẫn
   chung. Kết quả company-02 bỏ quy mô dù nguồn có 14 trang trại/14 nhà
   máy; tin 2024 không được trình bày rõ là bối cảnh cũ. Đã yêu cầu các mục
   tổng quan, quy mô, tin mới, nhu cầu và cuộc hẹn; nếu thiếu bằng chứng
   phải ghi thiếu ở đúng mục, không thay quy mô bằng xếp hạng. Sửa hướng
   dẫn này chưa có lượt mô hình sau sửa, không cấp đạt từ kiểm giả lập.

Biên nhận giữ tại máy, không đăng khóa hoặc dữ liệu phiên:

- U01: `acceptance-20261008/tavily-pipeline-5j4ldw8k/result.json`, 3,691 giây,
  đúng một lượt tổng hợp trên sáu trang công khai đã thu thật trước đó,
  không tìm lại nguồn. Câu trả lời dùng trang Chính phủ Nhật Bản và OCA.
  Khoảng ngày được chứng minh trực tiếp bởi trang Chính phủ; phần kết luận
  kết thúc đối chiếu đồng hồ và nguồn bế mạc. Không coi đoạn trích ngắn ở
  OCA tự chứng minh riêng ngày bế mạc. Bộ chẩn đoán thử ban đầu dùng thứ tự
  nguồn trước sắp xếp nên báo sai lỗi; đối soát lại chính câu trả lời với
  nguồn trả về đã qua kiểm, không gọi thêm mô hình hoặc đổi kết quả gốc.
- Company-02: `acceptance-20261008/tavily-pipeline-dca2egbz/result.json`,
  27,303 giây, công cụ và bộ điều phối thật trong phiên SQLite riêng, sáu
  nguồn, một lượt Gemini. Không đọc nguồn riêng hoặc ghi Google/cloud.
  Tổng quan, sản phẩm, nhu cầu giả lập và ba câu hỏi có; thiếu các phần
  trên nên không cấp đạt nghiệp vụ.
- W01: `acceptance-20261008/w01-readback-20261008.md`, đọc Supabase có điều
  kiện đúng quản trị/phiên/lượt; không ghi hoặc gọi Gemini. Kết quả vẫn có
  hai nguồn, 24 người, 5760 phút và 1152 phút theo giả thuyết, thiếu độ dài.

Đợt gộp cuối gồm cả sửa hướng dẫn báo cáo: 363 phép kiểm đạt trong 86,81
giây; không gọi mô hình hoặc mạng. Bốn nhóm ngoại tuyến
12/12, 12/12, 16/16, 160/160 đạt; quét 566 tệp Git thấy được không phát
hiện bí mật. Các nhóm có phần giao nhau, không cộng thành điểm nghiệp vụ.
Những mục bên dưới là lịch sử theo bản, không phải tình trạng hiện hành.

### Cập nhật 13:02 UTC — nguồn đã đọc, mô hình quá tải

Khóa tìm kiếm đã cấu hình tại máy, không đọc/công bố giá trị. Tìm nguồn U01
theo nguyên câu hỏi đã khóa trả sáu trang trong 4,051 giây; có trang Hội đồng
Olympic châu Á và Chính phủ Nhật Bản. Trang Chính phủ có khoảng 19/9–4/10/2026,
tách riêng kỳ thể thao người khuyết tật. Không gắn cứng đáp án, URL hoặc ngày
vào mã. Biên nhận: validation/public-source-probe-20261008T124958073597Z.json.
Đây là thu nguồn thật, chưa chứng minh câu trả lời cuối đúng hoặc nghiệm thu cloud.

Hai nguyên nhân được sửa chung: truy vấn bỏ mất yêu cầu nguồn chính thức và
khoảng ngày; đường báo cáo tổng hợp nguồn hai lần. Nay truy vấn giữ yêu cầu
bằng chứng, ưu tiên đúng trang được chỉ định. Báo cáo dùng văn bản gốc trong
một lượt tổng hợp cuối; câu hỏi web độc lập vẫn có lượt suy luận và kiểm nguồn.
Cờ hoãn tổng hợp trung gian chỉ do bộ điều phối đặt. 139 phép kiểm đạt trong
11,19 giây trước bổ sung kiểm bảo vệ cờ và bộ điều phối; không gọi dịch vụ thật.

Đợt gộp sau cùng đạt 359 phép kiểm trong 134,81 giây: nguồn, suy luận,
định tuyến, bộ điều phối thật với biên mô hình giả lập, định dạng, bộ nhớ,
điều kiện phát hành và quét bí mật. Bốn nhóm đánh giá ngoại tuyến đạt
(12/12 định tuyến, 12/12 bộ đánh giá, 16/16 hợp đồng trả lời, 160/160
kiểm biến đổi); không gọi mô hình hoặc ghi cloud. Quy tắc mã máy chủ/script
và khoảng trắng đạt; quét 566 tệp Git thấy được không phát hiện bí mật.
Các bộ có phần trùng nhau, không cộng thành điểm chất lượng nghiệp vụ.
Biên nhận ngoại tuyến: validation/release-evaluation-tavily-final.json.

company-02 dùng công cụ, bộ điều phối và phiên thử tách biệt thật: sáu nguồn,
đúng một lượt Gemini, tổng 10,656 giây; không đọc nguồn riêng hoặc ghi Google.
Google trả HTTP 503 UNAVAILABLE, thông báo mô hình đang quá tải. Lỗi quan sát
trong đầu ra thực thi; biên nhận vẫn giữ trạng thái chưa nghiệm thu, không có
báo cáo để chấm: acceptance-20261008/tavily-pipeline-cuxr0fl_/result.json.
Ngân sách tại máy tăng 10 → 11/16, còn năm lượt; đây không phải hết ngân sách.
Không gọi lại hoặc tăng giới hạn. Các câu tiếp theo trong đợt gộp không chạy.

A chưa đóng chất lượng cuối; B giữ kết quả hợp lệ cũ, W01 vẫn thiếu độ dài;
E chưa có đủ kết quả áp dụng để cấp điểm; F chưa gộp main. Chưa yêu cầu triển
khai bản chưa có đầu ra đạt. Tài liệu phía dưới là lịch sử, không phải trạng thái
khóa hiện hành. Không biến lỗi dịch vụ ngoài thành đạt hoặc sửa quanh một mẫu.

### Bổ sung sau chấp thuận nguồn tìm kiếm miễn phí

Người dùng đã đồng ý Tavily miễn phí. Đã triển khai trong máy đường tìm
nguồn `basic` → văn bản trang → tổng hợp có căn cứ; không dùng câu trả lời
tự sinh của Tavily, không gọi tìm kiếm Gemini trước khi dùng Tavily. Không
đưa ngữ cảnh tư vấn riêng vào truy vấn doanh nghiệp. Đạt 119 phép kiểm trong
máy; đợt gộp cuối 186 đạt trong 14,87 giây, không gọi dịch vụ thật. Chưa có
khóa Tavily để kiểm nguồn và chất lượng
thật; chưa nghiệm thu A/E/F hoặc cập nhật điểm. Chi tiết và thao tác an toàn
tại TAVILY-FREE-SETUP.md. Những số đo ở dưới giữ nguyên nguồn gốc lịch sử,
không được dùng làm số đo của đường tìm kiếm mới.

### Kết quả thực, không thay bằng điểm kiểm mã

- CI của bản xem xét 8296376 đạt: 1379 phép kiểm máy chủ, 13 bỏ qua,
  mức phủ 87,46%; 187 phép kiểm giao diện và 12 phép kiểm PostgreSQL đạt.
  Đường công bố ảnh và triển khai bỏ qua theo điều kiện nhánh. Bản này chưa
  lên Render; dịch vụ vẫn ở 81665f7. CI này không bao gồm sửa tiếp bên dưới.
- Lượt gộp sáu doanh nghiệp lúc 09:12 UTC dùng một lần gọi Gemini, mất
  45,673 giây; 5/6 báo cáo đủ cấu trúc, nhưng KHÔNG phải 5/6 nghiệp vụ đạt.
  FPT lẫn tên sản phẩm của Viettel trong cùng đầu vào gộp; Samsung thiếu
  chữ trang. Bộ kiểm gộp không chứng minh sáu phiên trò chuyện độc lập.
  Không dùng nó để kết luận sản phẩm đã lẫn dữ liệu người dùng hoặc để cấp đạt.
- Đã kiểm lại bằng bộ điều phối thật, mỗi doanh nghiệp một phiên dữ liệu riêng,
  chỉ cấp bộ nguồn công khai đã lưu; không có quyền đọc dữ liệu riêng hoặc ghi
  Google. Đây là nguồn cấp sẵn trong máy, KHÔNG phải Chat đăng nhập trên cloud.
  FPT, Vinamilk, Samsung, Shopee và Viettel trả lời, mỗi ca một lần gọi chính.
  Bosch bị giới hạn lượt trong phút chặn trước gọi, không phải lỗi Gemini.
  FPT không còn lẫn tên sản phẩm Viettel; Vinamilk nêu đúng 14 trang trại và
  14 nhà máy. Samsung và Viettel còn thiếu tổng quan hữu ích; bộ giới hạn
  nguồn vẫn có thể thay đoạn thiếu căn cứ bằng nhiều tiêu đề. Chưa cấp đạt
  toàn bộ báo cáo hoặc chấm điểm E.
- U01 gọi công cụ web thật lúc 09:34 UTC: hai lượt mô hình, chỉ thu tám
  tiêu đề tin, không có chữ trang hoặc khoảng ngày từ nguồn chính thức.
  Ngày máy chủ đúng; câu trả lời chưa đạt. Nhật ký bộ ngắt lỗi của khả năng
  tìm kiếm ghi loại `provider`, không phải `quota`; kết hợp nhánh dự phòng
  chỉ nhận 404/429 thì phù hợp với lỗi 404. Mã/thân lỗi gốc không được biên
  nhận lưu, nên không khẳng định chính xác lý do từ chối hay lỗi hết hạn mức.
- Kiểm thông tin mô hình bằng API chỉ đọc nhận `models/gemini-2.5-flash`
  tồn tại. Điều này KHÔNG chứng minh dự án có quyền gọi tìm kiếm; cũng không
  thể kết luận mô hình đã bị ngừng hoàn toàn. Google hiện công bố giới hạn
  quyền truy cập dòng 2.5 với dự án mới; tìm kiếm của dòng 3.x không có trong
  gói miễn phí. Không tự chuyển sang dịch vụ trả phí.
  Nguồn: https://ai.google.dev/gemini-api/docs/deprecations/ và
  https://ai.google.dev/gemini-api/docs/pricing, đọc ngày 08/10/2026.

### Sửa chung sau khi tái hiện, chưa triển khai

1. Chọn nguồn: câu “chỉ dùng/sử dụng nguồn công khai” không khớp nhánh đọc
   website; từ khóa trong câu phủ định về tài liệu trên máy kéo sang nguồn
   riêng. Đã tái hiện thất bại trước sửa; nhận thêm hai động từ cùng nhóm.
   Kiểm cả năm cách nói và bảo đảm không đưa dữ liệu riêng vào truy vấn.
2. Tiết kiệm lượt: đường dự phòng gọi tổng hợp dù chỉ có tiêu đề, trong khi
   hợp đồng cấm dùng tiêu đề làm căn cứ kết luận. Đã tái hiện rồi bỏ lượt
   tổng hợp trong trường hợp không có đoạn nguồn. Giữ nguồn, ngày máy chủ
   và lời giải thích thiếu căn cứ; không nhận đã giải quyết tìm nguồn.
3. Chẩn đoán: lưu vào nhật ký đúng mã 404/429 khi chuyển dự phòng, không
   ghi thân lỗi, câu hỏi hoặc khóa. Không nới hạn mức, không tự đổi mô hình.

Kiểm sau sửa: năm nhóm định tuyến, nguồn web, suy luận và thông tin cập nhật
đạt 123 phép kiểm trong 9,22 giây; kiểm quy tắc mã và khoảng trắng đạt.
Đợt gộp trước đó 245 đạt/1 thất bại do nguồn giả lập của phép kiểm URL không
có đoạn chữ, nên nay được dừng trước gọi đúng như ràng buộc mới. Đã bổ sung
đoạn chữ vào riêng phép kiểm URL để tiếp tục kiểm chặn URL bịa; không nới
bộ chặn trong sản phẩm hoặc đổi kết quả thật thành đạt. 123 kiểm có phần
trùng với đợt gộp, không cộng chúng để tính điểm chất lượng.

Biên nhận riêng: `design-work/qa/acceptance-20261008/isolated-jj4v_qwx/result.json`,
`isolated-tfwrvyc5/result.json`, `actual-web-093455.json` và
`design-work/qa/protonx-live-benchmark-20261008T091237720714Z.json`.
Chúng là bằng chứng nội bộ giữ tại máy, không đăng dữ liệu phiên hoặc khóa.

### Phần chưa thể đóng

Kiểm khả năng miễn phí thay thế lúc 09:49 UTC: đúng một yêu cầu tìm kiếm
với `gemini-2.5-flash-lite`, không thử lại hoặc đổi sang mô hình trả phí.
Google trả 404; thông báo chứa “no longer available” và “new users”. Chỉ
lưu các cờ chẩn đoán có/không, không lưu toàn thân lỗi hay khóa. Đây là bằng
chứng hạn chế truy cập của phương án thay thế, không phải điểm U01. Đã dừng
gọi lại; tăng bộ đếm Veridra hoặc đợi đặt lại hạn mức không sửa quyền truy cập.
Biên nhận: `design-work/qa/acceptance-20261008/free_search_capability_probe.json`.
Để đóng tìm kiếm tự do cần một nguồn tìm kiếm còn hoạt động; không coi chỉ
đọc địa chỉ do người dùng cung cấp là hoàn tất khả năng tự tìm nguồn.

A còn khả năng tự tìm/đọc nguồn chính thức và chất lượng hồ sơ chưa đều;
B dùng lại các chuỗi hợp lệ nhưng chưa đủ chứng minh toàn bộ ba quy trình;
E chưa đủ các tác vụ áp dụng để tính điểm; F chưa nhập main hoặc triển khai
bản xem xét. Công cụ thanh bên vẫn lỗi khởi tạo; không vượt đăng nhập qua
cookie hoặc SQL. Không tuyên bố sẵn sàng vận hành từ kết quả kiểm mã.

## Hai câu trả lời thật đã kiểm

| Ca | Kết quả thực | Điều còn thiếu |
| --- | --- | --- |
| Vinamilk | Đọc được trang chính thức, trả lời xong, có ba câu hỏi | Thiếu giới thiệu doanh nghiệp hữu ích; lặp tiêu đề tin; chưa tách rõ nhu cầu giả lập và dữ kiện công khai |
| ASIAD | Ngày máy chủ đúng; không bịa lịch khi thiếu nguồn | Chỉ lấy tiêu đề tin, có tin không liên quan, không tìm được khoảng ngày từ nguồn chính thức |

Mã lượt và câu trả lời nằm trong `backend/evals/release_acceptance.json`.
Trạng thái trả lời xong không đồng nghĩa chất lượng đạt. Không gán điểm tổng khi chưa đủ bằng chứng.

## Nguyên nhân và sửa chung

1. Bộ giới hạn bằng chứng trước đây thay cả dòng nếu có một nguồn chỉ chứa tiêu đề.
   Một câu có dẫn nguồn toàn văn riêng nhưng đứng cùng dòng cũng có thể bị mất.
   Đã tái hiện bằng kiểm thử thất bại rồi sửa ranh giới theo câu có dẫn nguồn riêng.
   Vẫn chặn câu dùng chung nguồn tiêu đề và toàn văn để suy diễn; không nới kiểm số liệu.
2. Tiêu đề xuất hiện lại ở danh mục nguồn bị biến thành một đoạn tin lặp.
   Đã giới hạn mỗi nguồn tiêu đề chỉ được trình bày một lần.
3. Báo cáo tư vấn cần mô tả doanh nghiệp, tách nhu cầu người dùng, phần chưa rõ và
   bước trao đổi tiếp; không thay bằng danh sách tin. Đã bổ sung yêu cầu này khi
   bằng chứng thực đã thu thập có nguồn web, kể cả đường chạy phối hợp nhiều nguồn.
   Nhu cầu giả lập không cần website xác nhận và không được gắn nguồn web giả.
4. Đường tìm nguồn dự phòng không có địa chỉ trang được chỉ định thì đưa nguyên
   câu hỏi dài vào tìm tin trong 30 ngày. Nhật ký Render xác nhận điều này ở ASIAD.
   Nó không có bước tìm trang chính thức, nên lời giải thích không thể tự tạo bằng chứng
   còn thiếu. Chưa đóng vấn đề này bằng việc sửa lời hướng dẫn hay thêm đáp án ASIAD.
   Nhật ký đã đọc không cho thấy mã lỗi của dịch vụ Gemini; không quy trách nhiệm
   cho Gemini khi chưa có bằng chứng.

## Kiểm đã thực hiện

- Chín nhóm kiểm hồi quy: **396 phép kiểm đạt**, 49,78 giây; không gọi mô hình.
  Bao gồm dẫn nguồn, bộ tổng hợp, điều phối, suy luận từ nguồn web, lỗi đọc nguồn,
  thông tin cập nhật, yêu cầu trình bày và ràng buộc cuối khóa.
- Kiểm mã bằng Ruff: đạt. Kiểm khoảng trắng bản sửa bằng Git: đạt.
- Bộ đo ngoại tuyến: định tuyến 12/12, đánh giá đầu ra 12/12,
  yêu cầu câu trả lời 16/16, chặn thay đổi trái phép 160/160.
  Tệp bằng chứng: `design-work/qa/acceptance-20261008/internal-ab-regression.json`.
- Đối chiếu nhật ký Render từ 07:38:25 đến 07:39:25 UTC ngày 08/10/2026:
  trang Vinamilk và hai đường lấy tin trả HTTP 200; ASIAD dùng toàn bộ câu hỏi
  làm truy vấn. Đây là đọc nhật ký, không phải chạy lại câu hỏi.

Các phép kiểm dùng câu trả lời giả lập kiểm tra được cơ chế xử lý, không chứng minh
Gemini sẽ viết đúng toàn bộ báo cáo thật sau triển khai. Bộ đo ngoại tuyến không
thay cho điểm chất lượng sản phẩm E. Bản sửa hiện chưa được triển khai.

Đã chạy thêm `scripts/qa_protonx_source_probe.py` để đọc song song sáu bộ nguồn
công khai, không gọi Gemini. FPT, Vinamilk, Shopee, Viettel và Bosch đọc được
chữ trang; Samsung chỉ có tiêu đề tin, không có chữ trang chính thức. Công cụ
đã được sửa để ghi trường hợp này là một phần, thay vì nhận đạt chỉ vì có tin.
Số ký tự nguồn lần lượt: 9.000, 3.970, 0, 9.000, 2.470, 9.000; ba nguồn
9.000 đã bị cắt theo giới hạn. Đây không phải sáu báo cáo tư vấn đạt chất lượng.
Kết quả chung thoát với mã 1 do Samsung thiếu nguồn; không che kết quả này.

Hướng dẫn chẩn đoán thực tế đã dùng: `render-debug`, tại
`C:/Users/Bao Phuc/.codex/plugins/cache/openai-curated-remote/app-6a624c56bfe081918f7544f7d58f6faf/1.0.1/skills/render-debug/SKILL.md`.
Thao tác thực: Render `render_list_logs`, phạm vi dịch vụ Veridra và phút nêu trên.

## Cập nhật tiếp — truy vấn và đọc nguồn

- Đã sửa truy vấn dự phòng: bỏ câu hỏi chỉ xin ngày máy chủ và các câu hướng
  dẫn trả lời/không đọc dữ liệu; giữ nguyên chủ đề còn lại. Không thu gọn
  "Google API pricing" thành "API" vì sẽ mất chủ thể. Với tên viết tắt rõ,
  lọc tiêu đề không có tên đó trước khi tính giới hạn nguồn. Không gắn nhãn
  nguồn chính thức chỉ vì tiêu đề phù hợp. Không thêm lượt gọi mô hình.
- Đợt gộp gồm mười nhóm kiểm đạt 400 phép kiểm trong 45,77 giây. Sau chỉnh
  giữ đầy đủ chủ đề thay vì thu gọn thành tên viết tắt, bốn nhóm bị tác động
  đạt 75 phép kiểm trong 5,62 giây. Hai con số có phần trùng nhau, không cộng
  chúng để tạo số mẫu hoặc điểm chất lượng.
- Samsung vẫn thiếu chữ trang trong lần chạy lại công cụ đo, nhưng phép đọc
  chẩn đoán riêng đã nhận HTTP 200, 365.187 byte và 8.815 ký tự hiển thị;
  chạy bộ thu nguồn với tên Samsung cũng nhận nguồn toàn văn. Chưa xác định
  được nguyên nhân khác biệt, không nhận đã sửa lỗi Samsung bằng mã.
- Đọc thêm biên nhận Supabase, chỉ phạm vi quản trị hiện tại: tác vụ Vinamilk
  15.723 ms, công cụ web 9.746 ms; tác vụ ASIAD 8.777 ms, công cụ web 6.524 ms.
  Cả hai không có mã lỗi ở biên nhận. Không suy ra dịch vụ tìm kiếm bình thường
  từ trạng thái này vì đường đọc tin dự phòng có thể vẫn trả thành công.
- Google hiện công bố tìm kiếm với Gemini 2.5 Flash/Flash-Lite có hạn mức miễn
  phí chung 500 yêu cầu/ngày; Gemini 3.5 Flash-Lite không có chức năng tìm kiếm
  ở gói miễn phí. Không tự đổi mô hình hoặc nâng gói để che vấn đề.
  Nguồn đã đọc: https://ai.google.dev/gemini-api/docs/pricing và
  https://ai.google.dev/gemini-api/docs/google-search/ ngày 08/10/2026.

Như vậy, phần giới hạn nguồn và truy vấn đã có sửa kiểm được; việc tự tìm trang
chính thức khi dịch vụ tìm kiếm không cung cấp kết quả vẫn chưa có bằng chứng
đạt. Không chốt A/E/F hoặc đưa bản này triển khai chỉ từ các phép kiểm trên.

## Điều kiện dừng sửa phần này

### Kết quả một lượt đã được người dùng cho phép

Biên nhận: `design-work/qa/protonx-live-benchmark-20261008T084436927452Z.json`,
08:44:36 UTC ngày 08/10, Gemini 3.5 Flash-Lite, đúng một yêu cầu mô hình.
Toàn đợt 8,557 giây, sáu trang chính thức đều có chữ đọc được lần này.
Không có lỗi kết nối, không tự thử lại. Đây là phép kiểm nội bộ, không phải
sáu chuỗi Chat cloud hoặc nghiệm thu bản đang chạy.

- Sáu báo cáo có tổng quan, nhu cầu đầu vào và đúng ba câu hỏi; không bịa
  lịch, ngân sách hoặc hành động đã thực hiện. Phần giới thiệu không còn bị
  thay toàn bộ bằng danh sách tin như biên nhận cloud Vinamilk trước đó.
- Cả sáu thiếu nhãn nguồn ở trường lĩnh vực, nên bộ kiểm cấu trúc ghi 0/6.
  Đây không phải điểm chất lượng bằng 0, cũng không được sửa đáp án để cấp đạt.
- Vinamilk ghi quy mô chưa xác minh dù chữ nguồn có 14 trang trại và 14 nhà
  máy. FPT không nêu số nhân viên khi chữ trang chỉ có bộ đếm chưa chạy và
  số lần nhận ghi nhận; sự thận trọng này đúng, không ép lấp số còn thiếu.
- Bosch dùng bối cảnh tập đoàn toàn cầu cho trường hợp đơn vị Việt Nam,
  chưa tách đủ rõ phần chưa xác minh của đơn vị. Phần quy mô giữ chữ tiếng
  Anh; các mô tả sản phẩm, tiêu đề và nhãn đầu vào ở nhiều báo cáo cũng còn
  tiếng Anh. Viettel có tên sản phẩm nằm dưới danh sách đối tác trên trang;
  không đủ để khẳng định chúng là sản phẩm của đơn vị chỉ từ vị trí này.
- Tin Bosch chứa bóng đá, điện thoại và hoa hậu không liên quan; FPT nhận
  cả mục chỉ có dấu gạch nối và tên nơi đăng. Hai nguyên nhân ở bộ đọc tin
  đã tái hiện bằng phép kiểm thất bại trước sửa. Sửa lọc tên nhận diện khi
  có truy vấn doanh nghiệp rõ và bỏ tiêu đề rỗng trước khi tính số nguồn.
  Không dùng bộ lọc này để chứng nhận thẩm quyền hoặc ý nghĩa của tin.
- Hướng dẫn nội bộ trước đó khác hướng dẫn tổng hợp trong sản phẩm. Đã dùng
  chung hướng dẫn báo cáo web, thêm ranh giới tập đoàn/chi nhánh, danh sách
  đối tác/sản phẩm và quy mô có căn cứ. Đây là sửa hợp đồng tổng hợp, chưa
  chứng minh câu trả lời thật mới đã đạt; không chạy thêm lượt Gemini.
- Sau sửa đọc tin, các nhóm web/dẫn chứng đạt 94 phép kiểm trong 7,63 giây.
  Đợt web, điều phối và bản xem trước đạt 224 phép kiểm trong 45,95 giây
  trước khi bổ sung hai xác nhận dùng chung hướng dẫn; không cộng số mẫu.
  CI 118d816 đạt 1376 phép kiểm máy chủ, 13 bỏ qua và mức phủ 87,45%; nó
  chưa bao gồm sửa mới sau khi đọc báo cáo này. Không gắn kết quả CI cũ cho mã mới.

Kết luận: có bằng chứng chất lượng cơ bản cải thiện, nhưng còn thiếu bằng
chứng nghiệm thu A/E/F, đặc biệt tự tìm nguồn chính thức cho U01. Chưa có
lý do để yêu cầu người dùng triển khai hoặc tuyên bố đã sẵn sàng phát hành.

### Kiểm nội bộ trước lượt triển khai tiếp

- Đồng bộ phần chữ trang được đưa vào tổng hợp với phần chữ được lưu để đối
  chiếu: cùng giới hạn 9.000 ký tự. Trước đây phần tổng hợp có thể nhận thêm
  3.000 ký tự không còn trong bản nguồn lưu; đây là sai lệch hợp đồng nguồn,
  chưa có bằng chứng nó gây ra riêng câu Vinamilk đã ghi nhận.
- Bộ kiểm sáu doanh nghiệp dùng đúng một yêu cầu có cấu trúc, tối đa 60 giây,
  một lần thử, không tìm kiếm phụ hoặc đổi mô hình. Dùng bộ đếm bảo vệ đang
  cấu hình thay vì bộ đếm riêng hoặc lượt dự phòng; hết hạn mức thì dừng trước
  khi tạo kết nối. Báo cáo yêu cầu đúng sáu trường hợp, mỗi trường hợp có ba
  câu hỏi làm rõ, không ép nguồn tiêu đề thành nội dung trang chính thức.
- Các nhóm kiểm web, dẫn chứng và cấu trúc đạt 91 phép kiểm trong 6,41 giây.
  Bộ kiểm ranh giới một lượt sau bổ sung đạt 5 phép kiểm trong 2,02 giây,
  có phần trùng với đợt trước nên không cộng số mẫu. Có dùng thư viện Google
  thật với đường truyền giả lập để xác nhận cấu trúc yêu cầu; không gọi Gemini
  thật. Đã kiểm lỗi 429/503, kết quả thiếu cấu trúc và chặn trước khi gọi khi
  hết hạn mức. Kiểm quy tắc mã đạt ở các tệp thay đổi trước bước bổ sung cuối.
- Chưa dùng lượt mô hình đang xin xác nhận, chưa triển khai, chưa nhập vào
  main. Những phép kiểm này không phải điểm chất lượng câu trả lời hoặc bằng
  chứng nghiệm thu A/E/F. Không bảo đảm kết quả thực trước khi đọc được báo cáo.

Chỉ đưa một bản triển khai gộp sau khi đường thu thập và tổng hợp đủ bằng chứng
cho các câu bắt buộc. Lượt xác nhận thật cuối chỉ chạy các đường bị sửa; không
lặp lại bộ nhớ, lưu kết quả hoặc phép tính đã đạt mà không bị tác động.
Nếu còn thiếu nguồn chính thức thì báo đúng giới hạn, không nhận đã nghiệm thu.
