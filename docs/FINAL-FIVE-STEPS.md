# Năm bước chốt nghiệm thu

Ngày chốt: 07/10/2026. Phạm vi: A/B/E/F theo RELEASE-CLOSURE.md.
Không thêm tính năng, vòng thiết kế hay bộ đo mới. C/D loại khỏi đợt demo;
P06 hoãn; chỉ một quản trị thật. Không đổi các mục này thành đạt.

| Bước | Làm gì | Điều kiện đóng |
|---|---|---|
| 1 — Khóa bản | Đẩy một đợt sửa chung về bằng chứng web, chạy kiểm tự động và triển khai đúng ảnh; sau đó cố định bản nghiệm thu. | Kiểm GitHub đạt, dịch vụ chạy đúng bản; không dùng trạng thái triển khai của bản cũ. |
| 2 — Đóng A | Kiểm lại tuyến website bằng một ca hồ sơ doanh nghiệp sau sửa; đối soát từng nhận định với nguồn đã đọc, phạm vi doanh nghiệp và ngày tin. Hoàn tất các ca hồ sơ/thông tin cập nhật còn thiếu trong bộ đã khóa. | Có lần đọc web thật; dẫn nguồn hỗ trợ kết luận; không bịa lịch/ngân sách hoặc coi thiếu bằng chứng là đạt. |
| 3 — Đóng B | Hoàn tất phần còn thiếu của ba quy trình: đầu ngày, chuẩn bị tư vấn, xem trước/duyệt/đọc lại; kiểm hỏi tiếp đổi phạm vi, quy trình đã lưu, nhớ/quên và kết quả xuất. Dùng lại biên nhận hợp lệ, không tạo thêm tài liệu Google hoặc đọc thêm thư ngoài phép. | Chuỗi đủ bước, đầu vào mới không lẫn dữ kiện cũ; lưu/mở lại đúng; ghi rõ lịch trống và dấu vết vai trò thực sự có. |
| 4 — Đóng E | Đối soát kết quả 24 tác vụ đã khóa, P06 giữ hoãn; không chạy thêm mẫu ngoài bộ. Chỉ tính số đo từ bằng chứng thật, công bố mẫu số/ngoại lệ và kết quả chưa đạt. Chốt hướng dẫn và bài demo 10 phút bằng các kết quả này. | Đủ bằng chứng cho các tác vụ áp dụng; điểm theo ngưỡng đã khóa, không có điểm giả hoặc lỗi chức năng chính bị bỏ qua. Không dùng kết quả lịch sử khác bản như phép kiểm mới. |
| 5 — Đóng F | Khi 1–4 đạt: gộp staging vào main, kiểm CI main, triển khai đúng ảnh; kiểm ngắn đăng nhập, nguồn, kết quả đã lưu và URL. Công bố bản/mã ảnh, báo cáo nghiệm thu, giới hạn và cách quay lui. | Main và Render cùng bản đã nghiệm thu; URL dùng được; bàn giao đủ. Dừng chỉnh sửa sau bước này. |

## Trạng thái hiện hành — 07/10/2026

- Cập nhật 08/10 lúc 13:02 UTC: khóa Tavily ở máy đã cấu hình, nguồn thật
  đọc được. U01 thu được trang của Hội đồng Olympic châu Á và Chính phủ
  Nhật Bản, có khoảng ngày; chưa chấm câu trả lời. company-02 chạy công cụ
  và bộ điều phối thật, sáu nguồn, bỏ tổng hợp trung gian: đúng một lượt
  Gemini. Google trả 503 vì mô hình quá tải sau toàn lượt 10,656 giây;
  không gọi lại, không đặt lại ngân sách (11/16, còn năm lượt tại máy).
  Đây không phải nghiệm thu cloud. A còn chất lượng đầu ra; B giữ biên
  nhận hợp lệ, W01 còn giới hạn độ dài; E chưa đủ kết quả để tính điểm;
  F chưa gộp main hoặc triển khai. Chi tiết và nguồn gốc biên nhận tại
  TAVILY-FREE-SETUP.md. Không thêm công việc ngoài năm bước đã khóa.
  Các mục dưới đây là lịch sử, không phải trạng thái cấu hình khóa hiện tại.
  Đợt kiểm gộp cuối 359 đạt/134,81 giây; bốn nhóm ngoại tuyến, kiểm quy tắc
  mã và quét 566 tệp đạt. Đây là kiểm mã, không phải điểm nghiệp vụ E.

- Cập nhật 08/10 sau khi người dùng đồng ý Tavily miễn phí: đã bổ sung
  cấu hình khóa chỉ ở máy chủ và đường tìm nguồn có văn bản trang, bỏ lần
  tìm kiếm Gemini bị từ chối khi có Tavily. Đợt gộp cuối đạt 186 phép kiểm trong máy;
  chưa có khóa để kiểm thật, chưa triển khai hoặc đóng A/E/F. Không thêm
  tiêu chí, không chạy lại phần B đã đạt. Hướng dẫn nhập khóa và giới hạn
  nằm tại TAVILY-FREE-SETUP.md. Các kết quả bên dưới là lịch sử theo bản.

- Đối soát mới nhất 08/10 sau 09:34 UTC: bản xem xét 8296376 đã qua CI,
  nhưng chưa triển khai và còn sửa chọn nguồn/tiết kiệm lượt đang kiểm trong
  máy. Bộ sáu báo cáo gộp không dùng làm nghiệm thu vì lẫn dữ kiện giữa ca;
  năm ca kiểm riêng không lẫn nguồn khác nhưng chất lượng chưa đều. U01
  công cụ thật chỉ có tiêu đề, chưa đủ nguồn chính thức. A/E/F chưa đóng;
  B giữ các biên nhận đã đạt, không chạy lại phần không bị sửa. Không nới
  hạn mức hoặc chuyển tìm kiếm trả phí. Chi tiết mới nhất nằm ở đầu báo cáo
  INTERNAL-ANSWER-REVIEW-20261008.md; các mục bên dưới là lịch sử.

- Đã chạy đúng một lượt nội bộ được cho phép ngày 08/10: sáu báo cáo nhận
  đủ nguồn và trả lời, không lỗi kết nối. Chưa nghiệm thu: các lĩnh vực thiếu
  dẫn nguồn, quy mô Vinamilk bị bỏ sót, bối cảnh Bosch và ngôn ngữ chưa đủ
  rõ; bộ tin có mục không liên quan/không có tiêu đề. Đã sửa hai lỗi đọc tin
  có tái hiện và đồng bộ hướng dẫn tổng hợp với sản phẩm, chưa chạy thêm
  Gemini hoặc triển khai. Báo cáo chi tiết giữ kết quả gốc, không cấp điểm giả.

- Cập nhật mới nhất 08/10: đã đọc hai câu trả lời Vinamilk và ASIAD trên 81665f7.
  Không còn lỗi kết nối ở hai tác vụ, nhưng Vinamilk thiếu phần giới thiệu hữu ích,
  lặp tiêu đề; ASIAD chưa đọc được khoảng ngày từ nguồn chính thức. Giữ hai ca
  một phần, không cấp đạt. Đã sửa chung ranh giới câu có nguồn, tránh lặp nguồn
  tiêu đề, hướng tổng hợp báo cáo và truy vấn tìm tin; kiểm trong máy, chưa triển
  khai. Biên nhận và giới hạn trong INTERNAL-ANSWER-REVIEW-20261008.md. Không
  tiếp tục yêu cầu người dùng chạy lặp bản cũ; A/E/F chưa đóng, B giữ phạm vi
  bằng chứng đã có, không chạy lại các đoạn không bị sửa.

- Cập nhật tiếp 08/10: W01 hỏi tiếp 82bea3d1-e3e7-43a8-b45b-d0185bab8758
  completed, giữ đúng ngữ cảnh 24 người/12 phút, ba câu hỏi, ngân sách chưa
  xác nhận và mức giảm 20% chỉ giả định; không đọc thêm nguồn. Bản lưu
  a8e73a8e-a363-4f4c-91fc-1af7b847c051 revision 1 giữ nội dung và hai liên
  kết nguồn; người dùng xác nhận mở lại. Đóng riêng đoạn hỏi tiếp/lưu, không
  cấp đạt toàn W01 vì lượt đầu thiếu độ dài. Công cụ thanh bên lỗi khởi tạo
  sandbox cả trước và sau reset, Chrome DevTools chỉ có about:blank; không
  tự chạy được ca web tiếp theo. Không yêu cầu nhập tay hoặc bỏ qua đăng
  nhập; A/E/F chưa đóng, không gộp main khi còn bằng chứng bắt buộc thiếu.

- Cập nhật 08/10, bản 81665f7 đã Live đúng ảnh b80b2bd6... trên Render
  dep-db3kafaj9qps7380tps0, CI 37742152484 thành công. W01 thật
  766df02c-e80b-4a34-8436-9af39ab3205a trả lời sau khoảng 16.46 giây,
  nhật ký tác vụ 14.328 giây, một lần gọi mô hình. Hai nguồn và phép tính
  đúng (24 người, 5760 phút/tháng, 1152 phút tiết kiệm giả định). Đóng riêng
  lỗi vòng gọi gây hết thời gian; không đóng toàn W01 vì câu trả lời dưới
  200 từ và bộ kiểm sửa định dạng phát hiện thay đổi dấu trích dẫn. Không
  chạy lại lượt đầu để tăng số mẫu. Còn hỏi tiếp và lưu/mở lại; A/E/F chưa
  đóng. Chi tiết trong LOCAL-SOURCE-TIMEOUT-20261008.md.

- Cập nhật 08/10: ngân sách tự đặt lại đúng 14:00 giờ Việt Nam. W01
  d3b1a9af-52b0-4172-9b2c-c51e2871eb8a đọc cả hai nguồn và tính thành công,
  nhưng vòng điều phối chạm 5 lượt/phút, chờ lượt rồi bị giới hạn tổng
  60 giây cắt ngang. Không kết luận Gemini quá tải từ lượt này. Sửa chọn
  tuyến nguồn để tái sử dụng luồng đọc có sẵn; chưa triển khai hoặc chấm
  câu trả lời. Xem LOCAL-SOURCE-TIMEOUT-20261008.md. Không chạy lặp bản cũ.

- Lượt company-02 trên 1baf5e6 đã chạy: nguồn web đọc thành công
  một lần; Gemini chính trả 504, dự phòng báo quá tải 503. Toàn lượt
  49,381 giây, không chạy lại web. Biên nhận
  3766fd3e-7397-495d-9bd2-b2878de90083. Cơ chế phục hồi đã kiểm đúng,
  nhưng chưa có báo cáo để chấm; giữ A/E chưa đạt, không kiểm lặp ngay.
- Đối soát B không gọi mô hình: W04 lịch sử vẫn có đủ ba câu trả lời
  đúng 30 triệu/25%, sửa thành 24 triệu/20%, giữ 120/144 và hai câu.
  W03 có câu trả lời tìm không thấy ghi chú đã xóa; kiểm dữ liệu hiện tại
  không còn QA-FINAL-8ad36c0. Kết quả Mộc An vẫn phiên bản 2,
  không lưu trữ, bốn câu hỏi và ngân sách chưa xác nhận. Đây không phải
  chạy lại chuỗi hoặc xuất tệp mới trên 1baf5e6. Nhãn bảy vai trò ready
  trong dấu vết không chứng minh cả bảy vai trò đã thực hiện công việc.

- Bản sửa phục hồi báo cáo 1baf5e6 đã Live đúng ảnh f406f454...:
  Render dep-db35i9vlk1mc739gm7tg kết thúc 14:39:13.703355 UTC.
  CI 37637232987 thành công; kết nối công khai xác nhận máy chủ,
  cơ sở dữ liệu và kho tệp. Bước triển khai đóng; còn đúng một lượt
  company-02 để kiểm đường lập báo cáo bị ảnh hưởng. Chưa đóng A/E/F.
  Kết quả 5267996 giữ trong prior_5267996_results, không biến thành
  kết quả mới. Công cụ thao tác thanh bên khởi động lỗi nên chưa tự
  gửi được câu hỏi; không bỏ qua đăng nhập hay ghi Chat trực tiếp qua SQL.

- Company-02 trên 5267996 chưa đạt: lượt
  18cadd6d-9392-4b93-9b74-afb1a7f91872 bị hết thời gian khi lập báo cáo.
  Nguồn web đã đọc xong; mã gốc là Gemini 504, rồi lớp đổi khóa chạy lại
  toàn quy trình gần giới hạn 60 giây. Đang sửa thời gian và phạm vi phục hồi,
  không kiểm lại U04 hoặc W02; chưa đóng A/E và chưa gộp main.

- Biên nhận lịch sử 5267996. CI 37631186037 thành công; Render
  dep-db34ug59fdbs73a05nag Live lúc 20:57:07 giờ Việt Nam, ảnh
  sha256:3abd78d3a46b407337c8c3c0741ae91b15fd34ab03c06c8a92ccaed8fcfb12f2.
  Máy chủ, cơ sở dữ liệu và kho tệp trả thành công; chưa suy ra kết nối
  Gemini của quản trị hoặc chất lượng câu trả lời từ kiểm công khai. Bước 1 đóng.
  U04 trên bản này đã đạt: trả đúng hạn mức theo dự án, không theo khóa,
  dẫn đúng trang chính thức với trích đoạn hỗ trợ. Lượt aade876b-9698-4adb-8fbc-c6b3f143fa5a,
  web 10,465 giây, toàn tác vụ 14,798 giây; không nguồn riêng hoặc ghi dữ liệu.
  Đóng ca U04, không chạy lại; tiếp tục company-02 còn thiếu, không chạy lại W02.
- Biên nhận bản trước 8c4de13: bản sửa bước suy luận web đã lên
  staging; CI 37626892424 đã hoàn tất thành công, gồm PostgreSQL, máy chủ,
  giao diện, dựng/chạy ảnh và xuất PDF tiếng Việt. Ảnh theo commit được đọc
  HEAD HTTP 200: sha256:aed79992105db137f087fab7b8287db2189f148b96e9436eb6de70693071600b.
  Bước tự triển khai skipped; người dùng đã đổi nguồn ảnh. Render xác nhận
  dep-db34erpsrm7s73e33krg Live lúc 20:23:34 giờ Việt Nam ngày 07/10;
  kết nối công khai trả máy chủ, cơ sở dữ liệu và kho tệp thành công. Bước 1 đóng.
- A: U01 trên 42d7865 chưa đạt vì không trả ngày hiện tại/khoảng sự kiện,
  chỉ có tám tiêu đề tin. Bản sửa mới thêm bước suy luận có trích đoạn và
  căn cứ và đã Live. U04 vừa chạy chưa đạt: trang chính thức HTTP 200 nhưng
  bước tổng hợp lỗi source_bundle_summary_failed; chưa có câu trả lời để chấm.
  Mã lỗi gốc chưa được giữ lại, nên chưa kết luận nguyên nhân hoặc hết hạn mức.
  Đã xác định lệch định dạng gửi cấu trúc: ràng buộc cấm trường thừa không
  thuộc định dạng cũ. Bản sửa dùng định dạng JSON Schema như phần trò chuyện,
  qua 85 phép kiểm gồm SDK thật với kết nối giả lập, đã Live trên 5267996;
  câu trả lời thật U04 sau sửa đã đạt. Không suy rộng thành mọi ca web đều đạt.
  Giữ mã lỗi an toàn để phân biệt nguyên nhân nếu còn lỗi. Tự tìm nguồn chính thức khi tìm kiếm
  hết hạn mức vẫn còn hạn chế. Hồ sơ doanh nghiệp chưa đủ kết quả đạt.
- B: W02 đạt đủ chuỗi. Có biên nhận lịch sử cho tính toán, đổi đầu vào quy
  trình, nhớ/quên, lưu/xuất và bản tin; không chạy lại chỉ để tăng số mẫu.
  Những biên nhận đó vẫn ghi đúng bản/phạm vi, không giả làm kiểm trên 8c4de13.
- E: thiếu kết quả hợp lệ cho toàn bộ tác vụ áp dụng trong bộ 24; P06 hoãn.
  Chưa tính điểm tổng; không lấy số phép kiểm mã thay cho chất lượng nghiệp vụ.
- F: main chưa gộp. Chỉ thực hiện sau khi các mục phía trên đạt.

## Lịch sử các bản đã kiểm — không phải trạng thái hiện hành

- W02 trên bản đang chạy 42d7865 đã đạt đủ ba lượt theo đáp án đã khóa:
  giữ An Bình, đổi ngày hẹn sang 14/10/2026, giữ 09:00 và ngân sách chưa rõ;
  lượt hai 142 từ/bốn mục; lượt cuối ba câu hỏi; không đọc nguồn/ghi dữ liệu
  hoặc khẳng định hiện trạng không có bằng chứng. Đóng ca này, không chạy
  lại; các ca W02 cũ bên dưới chỉ giữ lịch sử. Toàn B/E/F chưa đóng.
- Bản mới nhất đang chạy: 42d7865, CI 37590312321 thành công. Render
  dep-db2vpo67bikc73b6p4k0 live lúc 15:05:38 giờ Việt Nam ngày 07/10,
  đúng ảnh sha256:0a02c6a7dfe2c21570e9e3e06c389a329f5040e8c45f8fb30d9d886e24ac786d.
  Kiểm kết nối công khai đạt. Bước 1 đóng; các kết quả câu trả lời trên bản
  trước vẫn giữ lịch sử, không tự tính điểm cho bản này.
- Cập nhật bản đang chạy: 2f0183a có cả hai sửa chung, CI 37587663500 đạt.
  Render dep-db2vdb0m7kps73cfms9g live lúc 07:39:01.145447 UTC ngày 07/10,
  mã ảnh sha256:d33051adc30ea6ff64b766958ef50943f7b52d020bdafe0dc2b7ec45c68dd953.
  Kiểm công khai trả status=ok, database=true, object_storage=true.
  Bước 1 đóng trên bản mới; kết quả các bản dưới đây là lịch sử, không cấp
  điểm cho bản mới. Lượt tiếp theo chỉ kiểm Vinamilk một lần, không chạy lại
  toàn bộ để tăng số phép thử.
- Đã chạy lượt Vinamilk trên 2f0183a: 97979210-6180-4a0b-b72a-ea59c423819f,
  web thành công, tác vụ 20,637 giây, tám nguồn và một lần gọi mô hình.
  Đóng lỗi gọi nhầm công cụ; không suy diễn tiêu đề thành ra mắt sản phẩm.
  Giữ PARTIAL toàn báo cáo vì số 1000 cửa hàng dẫn nguồn [1] không có dữ kiện
  đó trong chữ đã đọc (chỉ có tiêu đề [4]); danh sách còn trang sản phẩm.
  Không chạy lặp lại Vinamilk; A và E chưa đóng từ một ca riêng này.
- Bước 1: đã đẩy staging đến 35183a5, kiểm GitHub 37583117325 hoàn tất
  thành công ngày 07/10. Ảnh mới công khai đã đối chiếu theo đúng commit:
  sha256:4b0016d9dd4414f6490749e1126ca544a8141d901ae18913e8495b1d09a42c89.
  Bước tự triển khai Render bị bỏ qua; người dùng đã đổi đúng nguồn ảnh.
  Render dep-db2urke7bikc73b3l220 Live lúc 07:01:44 UTC ngày 07/10,
  đúng mã ảnh trên. URL /api/health trả status=ok, database=true và
  object_storage=true. Đóng bước 1; chưa suy ra chất lượng câu trả lời đạt.
  Lệnh đẩy không còn bị chặn.
  Kiểm local: 179 phép kiểm đạt trong
  67,90 giây, gồm nguồn, điều phối, tìm web và yêu cầu cuối khóa; kiểm mã đạt.
  CI 37563231626 thành công; ef04f01 chạy đúng ảnh trên Render,
  đợt dep-db2r5dks728c73abmc6g Live lúc 02:49:04 UTC ngày 07/10.
  Ảnh: sha256:0f26be48e572d73e98a237ab5675952774bfe7f0abd309be1554f2d1d07a1f59.
- Bước 2: ca Bosch trên ef04f01 hoàn tất 28,5 giây, đọc web thành công,
  phân biệt ngày/phạm vi/trạng thái và đủ ba câu hỏi làm rõ. Đóng riêng lỗi
  bỏ câu hỏi; còn thuật ngữ tiếng Anh. Ca Vinamilk suy diễn việc ra mắt từ
  tiêu đề sản phẩm và nhận tiêu đề rác. Đã sửa chung ở local: loại tiêu đề
  rác, chỉ trình bày tiêu đề/ngày đăng đối với nguồn chưa đọc toàn văn ở cả
  hai tuyến điều phối. Chưa kiểm thật sau sửa, chưa đủ các ca còn lại,
  chưa đóng A. Sửa này không chứng minh mọi nhận định không dẫn nguồn đều đúng.
- Bước 3: W04 đạt đủ ba lượt tính/sửa/nhớ trên ef04f01; đã đối soát mở bản
  lưu và tìm ghi chú đã xóa. W02 trên 35183a5: người dùng chạy ba lượt,
  đối soát đúng phiên d3bbbdd9 qua Supabase chỉ đọc. Lượt cuối giữ An Bình,
  14/10/2026 09:00 và ngân sách chưa xác nhận; lượt hai giữ bốn đề mục,
  143 từ tách bằng khoảng trắng. Đóng riêng lỗi nhớ giờ/định dạng.
  Hai lượt đầu vẫn khẳng định quy trình thủ công/thiếu phân loại dù đầu vào
  chưa có dữ kiện này; giữ PARTIAL cho chất lượng toàn chuỗi, không cấp điểm.
  Hẹn giờ và xuất có biên nhận lịch sử; chưa đóng toàn B.
- Bước 4 chưa đủ bộ kết quả/điểm hợp lệ. Không công bố điểm tổng hiện tại.
- Bước 5 chưa gộp main; phải chờ các bước trên.

## Phần còn lại, không mở rộng

1. Bản sửa 1047eb2 đã qua CI 37748916764 trên nhánh review, chưa triển khai.
   Các sửa nội bộ tiếp theo chưa thuộc kết quả CI đó. Chỉ gửi một bản triển
   khai gộp sau khi đánh giá báo cáo nội bộ; đang chờ xác nhận một lượt Gemini.
2. A: đối chiếu từng nhận định của báo cáo với phần chữ nguồn thực đã đọc,
   phân biệt nhu cầu giả lập, dữ kiện công khai và điều chưa rõ. Phép kiểm gộp
   nội bộ không thay sáu tác vụ Chat trong bộ đã khóa. Tự tìm nguồn chính thức
   của U01 vẫn thiếu bằng chứng; không chốt từ câu trả lời "chưa xác minh".
3. B: giữ các biên nhận hỏi tiếp, nhớ/quên, lưu/xuất, hẹn giờ và tài liệu đã
   có đúng phạm vi. Chỉ xử lý lượt đầu W01 chưa đủ độ dài và những đoạn còn
   thiếu bằng chứng; không chạy lại các thao tác đã đạt hoặc ghi Google thêm.
4. E: chỉ tính điểm từ kết quả hợp lệ của bộ đã khóa, không từ số phép kiểm
   mã hoặc đủ đề mục. P06 giữ hoãn. Hướng dẫn và bài demo đã có nhưng chỉ
   thay biên nhận sau nghiệm thu, không trình bày bản xem lại như lần chạy mới.
5. F: chỉ sau khi các điều kiện trên đạt mới gộp main, chạy CI main và triển
   khai đúng mã ảnh. Main vẫn chưa gộp; URL hiện chạy 81665f7, không phải
   1047eb2. Kiểm ngắn bản cuối và bàn giao rồi dừng chỉnh sửa.

Danh sách này không bảo đảm sẽ đạt ngưỡng khi chưa đo. Nếu hạn mức không
đủ, phải ghi chưa kiểm, không thay bằng điểm giả. Nghiệm thu giới hạn cho
một quản trị và phạm vi demo; không chứng nhận vận hành bốn người hoặc
khôi phục/an toàn/tốc độ đầy đủ khi C/D đã được loại khỏi đợt này.

## Quy tắc dừng vòng sửa

Chỉ sửa lỗi làm thất bại một bước trên, sau khi xác định nguyên nhân.
Gộp sửa và kiểm trong một đợt; không kiểm lại phần không bị ảnh hưởng chỉ để
tăng số phép thử. Một lỗi bắt buộc chưa giải quyết thì báo đúng mục bị chặn,
không phát sinh danh sách hoàn thiện mới hoặc tự cấp nhãn sẵn sàng phát hành.
Thiếu hạn mức/quyền/dữ liệu không phải lý do bịa kết quả. Không yêu cầu thêm khóa.
