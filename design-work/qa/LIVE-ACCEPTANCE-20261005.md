# Đối soát sử dụng thật ngày 05/10/2026

## Bản đã triển khai

GitHub CI `37270629909` thành công cho mã `e894fe8a8337cdeafbe0003d8fa735dee8f8de7d`. Đọc kho ảnh công khai xác nhận digest `sha256:eb28619b8db9ad2d6ff939d547d548de8d751e36996bcd8359577e3251c61bba`. Đã cập nhật nguồn đúng ảnh đó tại dịch vụ Render hiện có; triển khai `dep-db1k2mnavr4c73cadnr0` thành công, thời gian 1 phút 50 giây, bắt đầu 13:19:06 ngày 05/10 giờ Việt Nam. Trang được tải lại sau triển khai; tài khoản quản trị vẫn đăng nhập và dùng được Chat.

Các bằng chứng dưới đây thuộc bản này; không tự chuyển thành bằng chứng của bản sửa tiếp theo.

## Drive thật

Thanh bên sử dụng phiên OAuth của người dùng, không giả lập phản hồi Google. Danh sách mặc định có tệp và thư mục, nhãn “Gần đây trước”. Chọn chỉ thư mục trả 50 thư mục ở trang đầu; thêm gắn sao còn 12 thư mục, không lẫn tài liệu/bảng tính. Chọn chỉ tệp cùng gắn sao không có thư mục; bảng có 13 hàng gồm hàng tiêu đề. Bỏ gắn sao vẫn chỉ có tệp. Trả lại mặc định Tất cả và không gắn sao; sau triển khai, đọc lại danh sách thành công.

Ảnh giao diện được xem trực tiếp qua công cụ thanh bên: tìm kiếm/bộ lọc theo cùng giao diện tối. Chưa đối chiếu thời gian Google của từng mục để chứng nhận toàn bộ thứ tự gần đây; chưa đóng toàn bộ E04/E05. Công cụ đo DOM không phản hồi (`Page.getFrameTree` timeout), nên không chứng nhận đầy đủ kích thước, tràn ngang, lỗi mạng hoặc console bằng lượt này. Không ghi ảnh chứa tên tài liệu riêng vào Git.

## Hội thoại ba lượt bằng dữ liệu giả lập

Không gửi nội dung Gmail/Drive cho mô hình. Cấm đọc nguồn ngoài và bộ nhớ dài hạn; không tạo tài liệu Google. Khách hàng và số liệu trong ba câu hỏi đều giả lập.

| Ca | Kỳ vọng | Kết quả thực tế | Kết luận |
|---|---|---|---|
| Lượt 1 | Ba dòng: Minh Phát, 10 giờ 08/10/2026 giờ Việt Nam, tăng từ 100 lên 120 triệu với phép tính | Đúng khách hàng/hạn, 20 triệu và 20%; có công cụ calculate; thiếu phép tính trong câu trả lời. 25,9 giây | KHÔNG ĐẠT đầy đủ yêu cầu trình bày |
| Lượt 2 | Đổi riêng kỳ này thành 130 triệu, giữ khách hàng/hạn/ba dòng; ghi biểu thức phần trăm | Đúng cả ba dòng và `(130 - 100) / 100 * 100 = 30.0%`. 17,2 giây | ĐẠT ca hỏi tiếp này |
| Lượt 3 | Nhắc lại dữ kiện mới, không tính lại; tải lại trang khi đang chạy, không mất hoặc gửi trùng câu hỏi | Phục hồi đúng phiên đang xử lý; kết quả Minh Phát, đúng hạn, 130 triệu; mỗi lượt có một câu hỏi và một câu trả lời; không có công cụ trong dấu vết lượt cuối | ĐẠT ca tải lại này |

Lượt 3: mã yêu cầu `7a9f6a25-534c-43cb-b2f0-3bcbe7d239a7`, mô hình thực dùng `gemini-3.5-flash-lite`, 5.267 token đầu vào và 47 đầu ra, thời gian lời gọi mô hình 8.894 ms. Đây không phải thời gian toàn tác vụ. Ngân sách ứng dụng từ 13 còn 8 lượt sau ba câu hỏi; không đặt lại bộ đếm, không gọi đây là số dư Google. Dấu vết lượt đầu có calculate; lượt cuối không đọc hoặc ghi thêm nguồn.

Đây là một chuỗi kiểm ngữ cảnh/phục hồi bổ sung, không thay 24 tác vụ, 12 ca ngữ cảnh và 6 ca bộ nhớ dài hạn bắt buộc. Chưa có điểm tổng đủ nhóm.

## Phát hiện còn phải sửa và kiểm lại

- Sau ba lượt thật, bảng ADK cũ tăng từ 26 phiên/212 sự kiện lên 27 phiên/222 sự kiện, trong khi không có bảng ADK ở `veridra_private`. Cấu hình search_path trong URL đã không có tác dụng trên đường kết nối cloud này. Quyền đọc API các bảng cũ vẫn bị khóa. Đang bổ sung schema rõ trong câu SQL và đặt search_path theo từng giao dịch; không chuyển/xóa hàng cũ. Phải kiểm PostgreSQL thật và chạy lại sau triển khai để chứng nhận.
- Bộ xuất số đo trước sửa lấy giá mặc định 0 và có thể xuất chi phí 0 khi không biết giá. Đang sửa: giá không có là chưa định giá, chỉ xuất ước tính khi có cả hai giá và đủ dữ liệu token của mọi lượt được tính. Giá 0 chỉ hợp lệ khi được cấu hình rõ. Phép thử local không thay bằng chứng phiên bản cloud mới.
- Render Free hiển thị giới hạn 512 MB và 0,15 CPU, nhưng trang số đo yêu cầu gói trả phí để xem mức sử dụng. Đây là giới hạn cấu hình, không phải mức RAM/CPU đã đo. Không nâng gói để lấy bằng chứng.

## Bản sửa đã chạy và kiểm lại trên cloud

GitHub CI `37273959415` thành công cho mã `7813122c2aaf7f0e5dca618f1dcff5b3bc0f586a`. Kho ảnh công khai trả HTTP 200 và digest `sha256:03587e5e6fbc6f60087a960e111ec68a4feaa80df9335136630986f3aa97b304`. Render triển khai đúng digest, mã triển khai `dep-db1kklk9v7es7381bsng`, bắt đầu 13:57:26 giờ Việt Nam, thành công trong 1 phút 50 giây.

Tải lại giao diện, mở chính hội thoại trước triển khai và yêu cầu nhắc ba dữ kiện mới nhất, không đọc nguồn ngoài/không lưu bộ nhớ. Kết quả đúng Minh Phát, 10 giờ 08/10/2026 giờ Việt Nam, 130 triệu đồng; đúng ba gạch đầu dòng. Thời gian toàn tác vụ giao diện 20,5 giây. Mã yêu cầu `420c1fe3-cf80-4daa-bfdd-793efa4a2c61`; một lượt mô hình `gemini-3.5-flash-lite`, 4.776 token đầu vào, 55 đầu ra, 2.924 ms cho lời gọi mô hình; không có công cụ đọc/ghi nguồn khác. ĐẠT ca giữ ngữ cảnh cũ sau triển khai này, không thay toàn bộ bộ nhớ hoặc tác vụ Google đang thực thi.

Supabase xác nhận sau ca đó cả năm bảng ADK đã xuất hiện trong `veridra_private`; bảng cũ `public` giữ nguyên 27 phiên và 222 sự kiện, không tăng bởi ca mới. Các vai trò `anon`/`authenticated` không có quyền SELECT trên cả năm bảng cũ lẫn năm bảng mới. Bảng cũ có bảo vệ từng hàng; bảng mới ở schema riêng tư không có quyền API, chưa bật bảo vệ từng hàng bổ sung. Không di chuyển hay xóa lịch sử. Phép kiểm quyền ban đầu bị dịch vụ duyệt tự động báo quá tải, chưa thực thi; chạy lại cùng truy vấn đọc sau đó thành công. Không đọc hoặc xuất nội dung riêng qua SQL.

Sửa chi phí chưa biết đã triển khai cùng bản; bộ tự động kiểm giá thiếu, giá 0 cấu hình rõ, token thiếu và giá hợp lệ đã đạt. Chưa đọc số đo cloud được bảo vệ để chứng nhận đường xuất số đo cuối; không công bố chi phí 0 hoặc điểm chất lượng giả.

## Khóa bộ đối chiếu PDF

Đã xác nhận sáu bản gốc nằm ngoài Git tại thư mục Test_RAG; kiểm SHA256 và số trang hiện tại khớp 6/6. Danh mục `backend/evals/pdf_acceptance.json` giữ đủ sáu tệp, sáu tác vụ chính trên bốn nguồn có văn bản, một ca bài dài có điều kiện và ca từ chối bản quét riêng. Đáp án có số, đơn vị, thời kỳ và trang vật lý; ghi rõ các giới hạn đơn vị của bảng ngân hàng và mâu thuẫn 5%/16% của HDG, không sửa nguồn để tạo đáp án thuận lợi. Câu hỏi đã khóa trước khi chạy mô hình.

Kỹ năng PDF bản `26.904.11930` thực sự được dùng để trích trang với pypdf và render bảy trang liên quan bằng Poppler; đã kiểm trực quan bảng HDG. Công cụ `scripts/verify_pdf_samples.py` chạy với Python đi kèm Codex: sáu checksum và số trang khớp, không tải lên/không gọi mô hình; phép thử cấu trúc/đáp án phép tính đạt. Đây không phải điểm chất lượng sản phẩm. PDF và ảnh trang riêng tư không đưa vào Git.

Bài dài: pypdf phát hiện ba trang ít hơn 40 ký tự (1, 22, 39), khác bộ trích sản phẩm trước đó ghi bốn trang không dùng được. Không lấy kết quả pypdf thay kết quả parser sản phẩm; còn phải đối soát trang thứ tư. Mã xử lý hiện có công bố phần văn bản cùng `source_id` khi tệp cần xem lại, nên không tự kết luận toàn tệp không truy xuất được; phải kiểm nguồn/trang thực tế trong ứng dụng. Không tính toàn bộ 39 trang đã được đọc.

## Công cụ và giới hạn

## PDF và tài nguyên: bằng chứng bổ sung bản 7813122

Người dùng đã cho phép gửi đoạn liên quan của năm PDF có văn bản tới Gemini qua Veridra. P01 đối soát đúng trang 5, các con số và ngày nguồn, không lấy dữ kiện tháng 4 làm hiện tại; 20,3 giây, ba lời gọi mô hình. Câu trả lời còn dùng “bps” thay vì “điểm cơ bản”; quy tắc diễn đạt chung đã sửa local, chưa tính đã kiểm bản mới.

P02 trả đúng 5.671/23,8%, 4.230/31,1%, tổng 9.901 và chênh 7,3 điểm phần trăm, citation trang 2, 18,3 giây. Dấu vết chỉ có local_source_search/read và một lời gọi mô hình, không có calculate. Vì yêu cầu nghiệm thu phải có công cụ tính toán, ca này CHƯA ĐẠT đầy đủ dù kết quả số đúng; đang sửa nhận diện ý định tính toán chung, không thêm câu prompt riêng cho mẫu.

P03 ĐẠT đối soát số tiền 7,1 tỷ USD, tỷ trọng 18,51%, năm 2025 và Cục Đầu tư nước ngoài – Bộ Tài chính; citation trang 2; 18,0 giây, hai lượt mô hình, chỉ local_source_read trong dấu vết công cụ. P04 KHÔNG ĐẠT đọc đúng trang: câu hỏi yêu cầu trang 2 nhưng bằng chứng chỉ có trang 11, kết quả từ chối vì thiếu nguồn; 12,1 giây, một lượt mô hình. Không bịa số nhưng chưa hoàn thành công việc. Đang sửa ràng buộc trang chung trong bước thu thập, không lấy tìm theo độ liên quan thay yêu cầu trang rõ ràng. Tạm hoãn P05/P06 trên bản cũ để không tiêu thêm ngân sách cho lỗi đã chứng minh; sẽ kiểm phần ảnh hưởng sau triển khai bản sửa.

Sau khi mở lại ứng dụng, cả năm nguồn PDF xuất hiện: chiến lược 40.020 ký tự, bất động sản 44.575, điện 70.501, ngân hàng 60.095, bài dài 77.417. Bài dài duyệt 39/39 trang, trạng thái “Cần kiểm tra”, chỉ công bố phần đã đọc; các trang 1, 14, 22, 39 không được dùng làm nguồn. Chưa xác nhận chỉ mục ngữ nghĩa. Đây là trạng thái xử lý thực, không phải tất cả trang đều đọc thành công hoặc bằng chứng tự động phục hồi sau restart giữa tác vụ.

Render MCP đọc trong My Workspace do người dùng xác nhận: 2026-10-05T10:04:29Z, RAM 184.700.930 byte (~176,1 MiB), giới hạn 536.870.900 byte (~512 MiB), CPU giới hạn 0,15. Chỉ có một điểm RAM; CPU sử dụng, độ trễ HTTP và lượng request trả danh sách rỗng. Không suy ra p95, mức đỉnh hoặc PASS thử tải từ điểm này. Trang thanh bên đã gặp màn hình Render khởi động từ 16:59:35; không ghi được chính xác thời điểm đầu tiên sẵn sàng, nên không công bố thời gian cold-start đo đủ.

Đọc lịch sử Render từ 06:50Z tới lúc kiểm chỉ trả sự kiện triển khai thành công 06:59:20Z; không thấy sự kiện server_failed/server_restarted/image_pull_failed trong phạm vi truy vấn. Không coi thiếu sự kiện lỗi là chứng nhận không bao giờ lỗi.

## Kiểm mã bản sửa kế tiếp — chưa thay bằng chứng cloud

### Đối soát cloud d6ac259 — không gộp với kết quả bản trước

GitHub CI 37296955324 hoàn thành thành công, gồm PostgreSQL thật và kiểm image chạy. Render `dep-db1nrfqd0e5s738krf4g` đã live với đúng ảnh `sha256:e7a243642638e10cc8c05860f88cc99856427669807b1f4384c3d757a9dd3673`, hoàn tất 10:38:31Z. Health HTTP 200 xác nhận database và object storage; cấu hình Gemini toàn cục tắt là chủ đích khóa riêng, không phải phép kiểm khóa người dùng. Nhật ký mức lỗi trong khoảng 10:36:50Z–10:40:29Z trả rỗng; không suy ra không có lỗi mọi thời điểm.

P02 kiểm lại qua Chat thật: đúng 5.671/23,8%, 4.230/31,1%, tổng 9.901 và chênh 7,3 điểm phần trăm, trích trang 2; 14,2 giây, hai lượt mô hình. Dấu vết bảy sự kiện có tìm tài liệu, đọc tài liệu và **Tính toán**. Ca này đạt đối soát kết quả và tuyến công cụ trên d6ac259, không thay điểm toàn bộ nhóm.

P04 kiểm lại đã đọc đúng trang 2 nhưng trả **62%** thay vì **5%** trong bảng, so với 16% ở nhận định. Ca vẫn FAIL, 17,3 giây, một lượt mô hình. Đối chiếu trích xuất local cho thấy số 162 bị tách thành `1 62`, cột và nhận định chưa được tách đủ rõ. Đã sửa cách đọc theo tọa độ ký tự và dòng số căn cột; chưa xác nhận sửa thành công trên cloud. Nguồn đã lưu phải được đọc lại từ PDF gốc, không dùng câu trả lời cũ làm bằng chứng.

Render MCP trong My Workspace đọc d6ac259, instance `ndmpt`, từ 10:38Z tới 11:07Z: RAM tối đa trong các mẫu phút là 215.797.760 byte (~205,8 MiB), so với giới hạn 536.870.900 byte (~512 MiB), khoảng 40,2%. CPU cao nhất ghi nhận 0,101141214/0,15 ở 10:39Z (~67,4%); sau đó các mẫu không vượt 0,0302986. Đây là mẫu quan sát một admin, không phải kiểm bốn người hoặc đỉnh giữa các mẫu. Độ trễ HTTP trả rỗng, không công bố p95 giả.

### Sửa đọc bảng PDF — kiểm trước khi đẩy staging

Đọc theo tọa độ giữ toàn bộ văn bản gốc, bổ sung các dòng có ít nhất ba cột số căn lặp trên ít nhất ba dòng. Không tự gán tên chỉ tiêu; nhận định nhiều dòng chỉ ghép khi có ranh giới ngang quan sát được, không ghép văn xuôi gần đó theo suy đoán. Xử lý khoảng trắng vô hình chồng lên chữ số; số 0 không bị đổi thành ô rỗng. Phép đối chiếu local trang 2 điện cho dòng chứa HDG giữ `162 | 5% | -43% | 1,101 | 56%` và nhận định cùng dòng 16%. Nhãn dòng gồm cả tên nhóm ngành quan sát được, không chỉ ticker. Không OCR hoặc gửi nội dung mới ra ngoài trong kiểm parser.

Kiểm toàn bộ máy chủ: **1.153 đạt, 15 không chạy, 202,70 giây**. Lệnh đầu chạy từ thư mục backend thiếu đường dẫn scripts, dừng ở bảy lỗi import khi thu thập; đã chạy lại từ gốc với `PYTHONPATH=backend;.`. Ruff phạm vi sửa và git diff --check đạt. Quét bí mật đạt 546 tệp Git-visible và 889 blob lịch sử có giới hạn; không chứng nhận mọi dữ liệu cá nhân. Phép kiểm trang thực đầu dùng đường dẫn tương đối sai trả trạng thái error; chạy lại đường dẫn tuyệt đối đúng trả text, 2,083 giây. Kiểm chuỗi nhãn chỉ `HDG` thất bại vì nhãn còn tên nhóm ngành; đối chiếu dòng thực xác nhận các giá trị, không đổi parser để ép khớp nhãn giả.

Chưa có bằng chứng câu trả lời cloud từ parser sửa này; phải triển khai ảnh đã qua CI và bấm đọc lại từ tệp gốc. Cùng nguồn_id được giữ qua cơ chế reextract đã có kiểm thử, không xóa nguồn người dùng hoặc nạp thành bản trùng.

Đã sửa chung nhận diện yêu cầu số học có nguồn, đọc trang vật lý rõ ràng ở cả điều phối ADK và bước thu thập xác định, đọc tiếp có giới hạn và quyền chủ tài liệu. Không lấy snippet tìm kiếm trang khác làm citation của trang đã chọn. Phạm vi trang bị phủ định không tự được đọc; trang thiếu không chuyển sang tìm kiếm trang khác; yêu cầu nhiều tệp có phạm vi trang không rõ bị từ chối để làm rõ. Quy tắc tính toán không nhầm tóm tắt với tổng số hoặc bắt tính lại tỷ lệ đã được nguồn công bố khi người dùng chỉ hỏi đọc.

Kiểm thực local: toàn bộ máy chủ 1.144 đạt, 15 không chạy, 216,50 giây; các phép PostgreSQL thật còn cần CI. Giao diện 176/176 đạt; thêm nhãn người dùng được kiểm lại 5/5; lint và TypeScript/Vite build đạt. Ruff dùng đúng cấu hình CI cho backend và scripts đều đạt. Lệnh gộp Ruff ban đầu dùng sai cấu hình cho scripts trả 21 lỗi; không sửa hàng loạt tệp không liên quan, đã chạy lại hai lệnh đúng cấu hình. Lần toàn bộ đầu tiên thu thập giữa lúc test đang viết gặp tên tham số `request` dành riêng của pytest; đã đổi tên và toàn bộ lần sau đạt.

Quét bí mật cả tệp Git-visible và lịch sử đạt: 546 tệp, 873 blob đủ điều kiện, không in giá trị khớp; đây không phải chứng nhận không có mọi loại dữ liệu cá nhân. Bộ quét được tối ưu đọc Git theo lô, giữ nguyên giới hạn 5 MB, quy tắc loại mẫu giả/khóa giả và fail-closed; sáu phép kiểm kho Git giả lập đạt. Bộ quét cũ cũng hoàn thành cùng 873 blob, đối soát không bỏ dữ liệu khi tối ưu.

Nhãn giải thích dấu vết và tiến độ PDF được diễn đạt tiếng Việt, giữ nguyên dữ liệu kỹ thuật thô và dòng mô hình thực. Không khẳng định trang ít văn bản chắc chắn là bản quét. Các thay đổi này chưa được xem trên bản cloud mới tại thời điểm ghi; không đóng UI hoặc điểm nghiệp vụ từ phép kiểm mã.

Đã dùng thao tác thật trong trình duyệt thanh bên để lọc Drive, cập nhật nguồn ảnh Render, xem kết quả triển khai và gửi/đọc Chat. Supabase chỉ đọc quyền, số hàng, danh sách bảng và phiên bản di trú, không xuất nội dung hội thoại. Kiểm mã local toàn bộ trước lượt này: 1.068 đạt, 15 không chạy; GitHub đã kiểm PostgreSQL thật của bản e894fe8.

Các mục còn chặn gồm bộ nghiệp vụ đủ mẫu, luồng đầu ngày/trước hẹn/duyệt và đọc lại, bộ nhớ đầy đủ, tốc độ khởi động/tài nguyên, khôi phục độc lập, bốn người thật và cùng phiên bản cuối. Không gộp nhánh chính hoặc tuyên bố sẵn sàng phát hành từ các kết quả thành phần ở trên.
