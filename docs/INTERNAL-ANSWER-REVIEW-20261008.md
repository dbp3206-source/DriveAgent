# Kiểm chất lượng nội bộ trước lượt triển khai cuối

## Quyết định

Chưa yêu cầu triển khai. Không dùng thêm lượt Gemini trong đợt kiểm nội bộ này.
Không mở rộng danh sách nghiệm thu; giữ nguyên phạm vi A/B/E/F, hoãn PDF đã thống nhất.

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
