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

### Cloud 1629c45 — kiểm sau triển khai và đọc lại

GitHub CI `37301982475` hoàn thành thành công cả postgres-state và verify. GHCR tag mã commit trả HTTP 200 và digest `sha256:c88dd5eeab99419d71a59cdcbec10252f9fe49b0e9db059a144351243048afeb`. Đã đổi nguồn Existing Image của dịch vụ Render hiện có, không đổi gói; deploy `dep-db1ojlgu01pc73fe0sv0` live 11:30:27Z. Health database/object storage đạt, runtime bắt đầu 11:30:17Z; các kết nối provider không được health kiểm. Logs mức error 11:28:26Z–11:35:46Z trả rỗng, không chứng nhận mọi thời điểm.

Đọc lại từ tệp gốc qua UI thật: điện hoàn tất 13/13, ngân hàng 14/14. Cùng hai source_id được giữ, mã nội dung đổi tương ứng parser; nguồn điện 73.932 ký tự, ngân hàng 60.090. Supabase xác nhận tổng vẫn bảy nguồn/năm job/năm object và bucket không public. Đây là publish lại cùng nguồn từ original, không phải restore độc lập. Truy vấn đối soát đầu thiếu prefix `j.name` báo SQL ambiguous; đã sửa truy vấn chỉ đọc, không thay dữ liệu qua SQL.

P04 kiểm trong phiên Chat mới, cùng câu hỏi khóa: đọc đúng trang 2, đúng bảng 5% và nhận định 16%, không tự chọn/đánh trung bình; 19,3 giây, một lượt mô hình. Phần lỗi số đã sửa trên cloud. Câu trả lời không ghi rõ ngày/dạng dự báo, nên chưa coi toàn bộ đáp án P04 đạt đủ mọi yêu cầu.

P05 có số đúng ACB 4.324/17,6%, BID 7.574/27,2%, chênh 3.250 và 9,6 điểm phần trăm, nguồn trang 2; 12,3 giây, một lượt mô hình. Dấu vết sáu sự kiện có Tính toán. **FAIL giới hạn đơn vị:** câu trả lời tự gán tỷ đồng cho ACB và phép chênh dù bảng không ghi đơn vị chung; không nêu hạn chế như yêu cầu. Đang sửa chính sách diễn đạt có nguồn chung, không sửa oracle hoặc bỏ lỗi để chốt điểm.

Sáu API đọc không cookie đều HTTP 401 trên bản này: memories/skills/artifacts/chat sessions/local sources/evaluation jobs, không gọi model hoặc ghi dữ liệu. Chưa thay phép truy cập chéo bốn người. Supabase đọc quyền: anon/authenticated không có USAGE schema riêng, cả mười quyền SELECT trên năm bảng điều phối lịch sử public đều false. Advisor chỉ trả năm INFO về RLS không policy của các bảng cũ bị khóa; không mở policy để xóa cảnh báo. pg_cron/pg_net chưa cài. Các ca này chưa thay bộ an toàn đầy đủ hoặc thử phục hồi môi trường mới.

P06 13,3 giây, một lượt mô hình, đúng điện 7,2%/kế hoạch 7,5%/chênh 0,3 điểm phần trăm, hai nguồn riêng trang 1 và hai ngày báo cáo. **FAIL phạm vi:** câu trả lời viết lợi nhuận toàn ngành khoảng 20%, trong khi nguồn nói nhóm ngân hàng được theo dõi. Không đổi oracle để chấp nhận suy rộng. Bản sửa kế tiếp bổ sung quy tắc chung giữ tập mẫu, đơn vị đúng từng đối tượng và ngày/trạng thái dự báo; đây là hướng dẫn mô hình, chưa có xác minh ngữ nghĩa xác định từ schema biểu thức số.

Đo mở Chat đã đăng nhập bằng browser thật, máy chủ đang thức: bốn mẫu đầy đủ tới khi có ô câu hỏi là 2.180/4.592/3.497/2.102 ms. Không đủ 20 mẫu để đóng tốc độ; không có mẫu cold. Bốn mẫu đầu dùng snapshot diff và vòng chờ quá ngắn đều chưa thấy ô câu hỏi nên không tính thành số đo usable; đã sửa cách đo dùng snapshot đầy đủ và giới hạn 10 giây. Không lấy thời gian HTTP HTML thay thời gian mở sản phẩm.

### Bản sửa nghiệp vụ tiếp theo — chưa nghiệm thu cloud

### Cloud d544a13 — đối soát sau triển khai

Lượt sửa tiếp sau d544a13: chồng thời gian tải module Chat với đăng nhập trên đường
vào Chat, dùng chung cache và thử lại nếu preload lỗi. Chỉ tải mã công khai, không
mount Chat hoặc gọi API riêng khi chưa đăng nhập. Hai phép kiểm thực thi App qua
harness auth trì hoãn xác nhận ranh giới này và thử lại chunk lỗi. Toàn bộ giao diện
178 đạt, lint/build đạt; chưa có phép đo trình duyệt trên bản sửa để chứng nhận tốc độ.

Hợp đồng tính toán bổ sung thứ tự phép trừ có dấu, công thức hiển thị đúng biểu thức
và giữ tập mẫu. Cùng hướng dẫn bảo toàn đơn vị/ngày/dự báo được cấp cho cả lượt sửa
định dạng thường và dự phòng; ngân sách tính cả hướng dẫn thêm. Đây vẫn là hướng
dẫn mô hình, không phải bộ xác minh ngữ nghĩa xác định. 94 phép kiểm phạm vi đạt;
toàn bộ máy chủ 1.174 đạt, 15 không chạy local, 234,87 giây. Ruff backend/scripts
và diff check đạt; không chứng nhận P06 live từ các phép kiểm này.

CI `37309375496` thành công cho commit `d544a138447e285ee150404ad868a772b2017e73`. GHCR xác nhận HTTP 200, ảnh `sha256:e73f2d0a1227e41b75ac302ee2d6444544241105c44e65b0898583cb3b7009a9`. Render `dep-db1pl23ncjis73bra1u0` hiển thị Live lúc 19:41:30 giờ Việt Nam; khởi động 19:41:24, database/kho tệp xác nhận qua health. Không gộp main hoặc dùng health để chứng nhận chức năng Google/Gemini. Supabase đọc trực tiếp vẫn có năm object, bucket riêng tư, anon/authenticated không có USAGE schema ứng dụng; pg_cron/pg_net chưa có.

P05 chạy trong phiên mới qua Chat thật: đúng 4.324/17,6%, 7.574/27,2%, chênh 3.250/9,6 điểm phần trăm; giữ số trần, nêu bảng thiếu đơn vị chung và ngày dự báo 30/03/2026, trang 2. 16,1 giây, một lượt mô hình, dấu vết có Tính toán. Lỗi tự gán đơn vị đã khắc phục trong lượt này. Chưa nêu riêng đơn vị tỷ đồng ở nhận định BID như oracle chi tiết, nên không chấm đủ toàn ca.

P06 có đúng số, hai nguồn trang 1 và ngày riêng, 14,0 giây, một lượt mô hình. **Vẫn KHÔNG ĐẠT:** suy rộng nhóm ngân hàng MBS theo dõi thành toàn ngành; câu diễn giải viết 7,2 trừ 7,5 cho độ lớn dương 0,3, không rõ dấu/thứ tự. Công cụ tính toán không chứng minh diễn giải đúng. Không thay đáp án, không lấy kiểm thử provider giả làm bằng chứng ngữ nghĩa. Quy tắc nhắc mô hình chưa đủ để đóng lỗi này.

Đo mở Chat đã đăng nhập trên cùng d544a13, máy chủ đang thức: 20/20 thấy ô câu hỏi. Mẫu ms: 2920, 5373, 5124, 6378, 5148, 3464, 4677, 5166, 5467, 5233, 5390, 4233, 2959, 5879, 6064, 3131, 5493, 5983, 6475, 6668. p50=5.303 ms; p95 nearest-rank=6.475 ms. Phương pháp đo từ trước reload tới snapshot đầy đủ thấy ô câu hỏi, gồm độ trễ điều khiển trình duyệt/đọc snapshot; không phải độ trễ mạng thuần hoặc phép phân tích nguyên nhân chậm. Chưa chứng minh mốc warm <=5 giây; chưa có ba mẫu khởi động sau ngủ. Không ghép bốn mẫu bản trước vào bộ này.

Người dùng cho phép project khôi phục miễn phí trong tổ chức Veridra. Công cụ Supabase báo chi phí 0/tháng; đã tạo `Veridra-restore-check-20261005`, project `scsxkanbmtexylgbrsla`, riêng biệt nguồn `ltvzdrvjmljvrnhwxade`, PostgreSQL 17.11, trạng thái ACTIVE_HEALTHY. **Chưa sao chép/khôi phục dữ liệu**. Đã tìm thấy và chạy `pg_dump`/`pg_restore` 17.10 tại `C:/Program Files/PostgreSQL/17/bin`; nhận định trước đây không có công cụ trên PATH không còn đồng nghĩa chưa cài. Còn cần kết nối có mật khẩu và bí mật kho tệp được nhập an toàn, không ghi vào Chat/Git.

Đã sửa trước hẹn: mặc định chọn sự kiện trong 60 phút tới, có timezone rõ; không lấy quá khứ/all-day/cancelled. Job theo owner và fingerprint ID+revision provider+trường nguồn thay dedupe theo giờ. Khi chạy đọc lại Calendar trước nguồn khác: sự kiện đổi/hủy/dời không tiếp tục tạo báo cáo; không tạo chat rỗng. Payload hỏng có checkpoint lỗi an toàn, xóa lease và không cản job sau. Calendar lỗi riêng một owner không cản owner còn lại; lỗi giao dịch chung không bị nuốt. Giữ Google read-only, luồng sáng và quyền hiện có. Chưa có lịch thật dương, nguồn đánh thức ngoài hoặc pg_cron, nên không đóng toàn bộ quy trình trước hẹn.

Kiểm bản sửa đơn vị/phạm vi và scheduler chung: 1.170 máy chủ đạt, 15 không chạy local, 186,13 giây; Ruff backend/scripts và diff check đạt. Scheduler focused 28 đạt; source-contract integration chỉ dùng provider giả, không thay câu trả lời live. Không thay đổi schema dữ liệu, không tăng quota, không tạo dịch vụ trả phí.

Đọc theo tọa độ giữ toàn bộ văn bản gốc, bổ sung các dòng có ít nhất ba cột số căn lặp trên ít nhất ba dòng. Không tự gán tên chỉ tiêu; nhận định nhiều dòng chỉ ghép khi có ranh giới ngang quan sát được, không ghép văn xuôi gần đó theo suy đoán. Xử lý khoảng trắng vô hình chồng lên chữ số; số 0 không bị đổi thành ô rỗng. Phép đối chiếu local trang 2 điện cho dòng chứa HDG giữ `162 | 5% | -43% | 1,101 | 56%` và nhận định cùng dòng 16%. Nhãn dòng gồm cả tên nhóm ngành quan sát được, không chỉ ticker. Không OCR hoặc gửi nội dung mới ra ngoài trong kiểm parser.

Kiểm toàn bộ máy chủ: **1.153 đạt, 15 không chạy, 202,70 giây**. Lệnh đầu chạy từ thư mục backend thiếu đường dẫn scripts, dừng ở bảy lỗi import khi thu thập; đã chạy lại từ gốc với `PYTHONPATH=backend;.`. Ruff phạm vi sửa và git diff --check đạt. Quét bí mật đạt 546 tệp Git-visible và 889 blob lịch sử có giới hạn; không chứng nhận mọi dữ liệu cá nhân. Phép kiểm trang thực đầu dùng đường dẫn tương đối sai trả trạng thái error; chạy lại đường dẫn tuyệt đối đúng trả text, 2,083 giây. Kiểm chuỗi nhãn chỉ `HDG` thất bại vì nhãn còn tên nhóm ngành; đối chiếu dòng thực xác nhận các giá trị, không đổi parser để ép khớp nhãn giả.

Chưa có bằng chứng câu trả lời cloud từ parser sửa này; phải triển khai ảnh đã qua CI và bấm đọc lại từ tệp gốc. Cùng nguồn_id được giữ qua cơ chế reextract đã có kiểm thử, không xóa nguồn người dùng hoặc nạp thành bản trùng.

Đã sửa chung nhận diện yêu cầu số học có nguồn, đọc trang vật lý rõ ràng ở cả điều phối ADK và bước thu thập xác định, đọc tiếp có giới hạn và quyền chủ tài liệu. Không lấy snippet tìm kiếm trang khác làm citation của trang đã chọn. Phạm vi trang bị phủ định không tự được đọc; trang thiếu không chuyển sang tìm kiếm trang khác; yêu cầu nhiều tệp có phạm vi trang không rõ bị từ chối để làm rõ. Quy tắc tính toán không nhầm tóm tắt với tổng số hoặc bắt tính lại tỷ lệ đã được nguồn công bố khi người dùng chỉ hỏi đọc.

Kiểm thực local: toàn bộ máy chủ 1.144 đạt, 15 không chạy, 216,50 giây; các phép PostgreSQL thật còn cần CI. Giao diện 176/176 đạt; thêm nhãn người dùng được kiểm lại 5/5; lint và TypeScript/Vite build đạt. Ruff dùng đúng cấu hình CI cho backend và scripts đều đạt. Lệnh gộp Ruff ban đầu dùng sai cấu hình cho scripts trả 21 lỗi; không sửa hàng loạt tệp không liên quan, đã chạy lại hai lệnh đúng cấu hình. Lần toàn bộ đầu tiên thu thập giữa lúc test đang viết gặp tên tham số `request` dành riêng của pytest; đã đổi tên và toàn bộ lần sau đạt.

Quét bí mật cả tệp Git-visible và lịch sử đạt: 546 tệp, 873 blob đủ điều kiện, không in giá trị khớp; đây không phải chứng nhận không có mọi loại dữ liệu cá nhân. Bộ quét được tối ưu đọc Git theo lô, giữ nguyên giới hạn 5 MB, quy tắc loại mẫu giả/khóa giả và fail-closed; sáu phép kiểm kho Git giả lập đạt. Bộ quét cũ cũng hoàn thành cùng 873 blob, đối soát không bỏ dữ liệu khi tối ưu.

Nhãn giải thích dấu vết và tiến độ PDF được diễn đạt tiếng Việt, giữ nguyên dữ liệu kỹ thuật thô và dòng mô hình thực. Không khẳng định trang ít văn bản chắc chắn là bản quét. Các thay đổi này chưa được xem trên bản cloud mới tại thời điểm ghi; không đóng UI hoặc điểm nghiệp vụ từ phép kiểm mã.

Đã dùng thao tác thật trong trình duyệt thanh bên để lọc Drive, cập nhật nguồn ảnh Render, xem kết quả triển khai và gửi/đọc Chat. Supabase chỉ đọc quyền, số hàng, danh sách bảng và phiên bản di trú, không xuất nội dung hội thoại. Kiểm mã local toàn bộ trước lượt này: 1.068 đạt, 15 không chạy; GitHub đã kiểm PostgreSQL thật của bản e894fe8.

Các mục còn chặn gồm bộ nghiệp vụ đủ mẫu, luồng đầu ngày/trước hẹn/duyệt và đọc lại, bộ nhớ đầy đủ, tốc độ khởi động/tài nguyên, khôi phục độc lập, bốn người thật và cùng phiên bản cuối. Không gộp nhánh chính hoặc tuyên bố sẵn sàng phát hành từ các kết quả thành phần ở trên.

### Cloud e03078b và sửa lỗi độ dài — ngày 05/10

CI `37314836461` thành công; ảnh được đối chiếu theo commit là
`sha256:fde145ce1a5601fbd422097078ff9d927a73b3f808114d640202028f793de723`.
Render `dep-db1q7vdg1s2s73bbkvm0` Live lúc 20:21:58 giờ Việt Nam.
Đây chưa phải phiên bản được nghiệm thu toàn bộ.

Trong phiên mới, báo cáo giả lập Minh Phát đọc đúng hai tệp, giữ bản sửa 24 người,
tính 5.760 phút và tiết kiệm giả thuyết 1.152 phút; 17,0 giây, một lượt mô hình.
**Không đạt độ dài:** yêu cầu khoảng 220 từ nhưng trả lời khoảng 90 từ, không có
sự kiện kiểm định dạng. Đã xác định parser chỉ nhận khoảng hai số, không nhận
mục tiêu một số. Sửa chung nhận diện độ dài với dung sai 10%, giữ nguyên giới hạn
chính xác/tối đa/tối thiểu; không sửa riêng prompt hoặc bỏ yêu cầu nghiệm thu.
80 phép kiểm trình bày đạt; toàn bộ backend **1.199 đạt, 15 bỏ qua local, 223,85 giây**.
Ruff phạm vi sửa và diff check đạt. Quét bí mật trước push: 547 tệp và 910 blob lịch
sử có giới hạn đạt; không phải chứng nhận mọi dữ liệu cá nhân.

Hỏi tiếp trong phiên bằng giới hạn 200–240 từ: trả lại 24 người, 96 giờ/tháng,
tiết kiệm giả thuyết 19,2 giờ, còn 76,8 giờ, ba câu hỏi và hai nguồn lịch sử;
19,7 giây, hai lượt mô hình, 10 sự kiện. Đây là bằng chứng thành phần của ngữ cảnh
và báo cáo, chưa đóng toàn bộ bộ nhớ hoặc quy trình. Chuẩn bị xuất Google Doc đã
hiện bước xác nhận; sau duyệt bị chính sách chỉ đọc chặn, **chưa tạo tài liệu**.
Chủ sở hữu xác nhận bật riêng quyền Doc quản trị; đã lưu
`DRIVE_AGENT_BETA_OWNER_DOCUMENT_WRITES=true` bằng Save only trong Render.
Chưa hiệu lực runtime cho tới triển khai; không đổi quyền gửi thư hoặc người khác.

P06 trên e03078b: 12,9 giây, một lượt mô hình; đọc hai trang 1, phép trừ 7,5–7,2
cho 0,3 đúng. **Vẫn không đạt phạm vi:** trả lợi nhuận toàn ngành thay nhóm ngân
hàng MBS theo dõi; thiếu hai ngày nguồn trong nội dung. Hướng dẫn bảo toàn nguồn
chưa đủ giải quyết lỗi ngữ nghĩa. Không đánh dấu đạt từ phép tính đúng.

Chủ sở hữu xác nhận đã đặt và lưu mật khẩu project khôi phục thử.
Chưa nhập mật khẩu vào Chat, chưa chuyển dữ liệu, chưa đóng điều kiện khôi phục.

## Bản d319f1d và phục hồi bản xem trước

CI 37319209752 đạt; Render dep-db1qnt17lnhs73e4v8e0 chạy ảnh
sha256:8f6d157dcf53d10cf368ca9905a2c3384c90c3426c360611ac0b896176e20f18.
Quyền tạo Doc riêng quản trị được áp dụng trong lần triển khai này; không mở gửi thư.
Câu yêu cầu khoảng 220 từ được nhận diện nhưng câu trả lời thật vẫn ngắn:
18,9 giây, hai lượt mô hình, tám sự kiện. Bản sửa lại thay dấu dẫn nguồn nên bị
từ chối; giao diện giữ bản nháp chưa đạt và khóa xuất. Chưa nghiệm thu chất lượng.

Thử xuất báo cáo giả lập hỏi tiếp trong phiên cũ bị chặn vì bản xem trước quá
30 phút. Máy chủ ghi trạng thái hết hạn, chưa tạo Google Doc. Sửa giao diện để
người dùng chủ động chuẩn bị lại sau khi đọc trạng thái hết hạn, rồi duyệt riêng;
không tạo lại khi kết quả chưa rõ hoặc đã thành công. Kiểm giao diện bằng máy:
187/187 đạt, kiểm mã và dựng ứng dụng đạt; kiểm trên URL thật còn chờ bản mới.

Phép đọc Gmail được phép trên e03078b: 14,9 giây, một lượt mô hình, năm sự kiện;
bốn thư được trình bày cùng bốn dẫn nguồn. Chưa có bằng chứng đủ để chứng nhận
đã đọc đủ năm thư hoặc toàn hộp thư. Không lưu nội dung riêng trong hồ sơ Git.
Không gửi thư và chưa có Google Doc được tạo trong lượt nghiệm thu này.

## Khóa việc còn lại và sửa cách viết dẫn nguồn

Danh sách điều hành cuối được ghi trong docs/RELEASE-CLOSURE.md theo sáu nhóm
đã trình người dùng; không mở phạm vi. CI 37323704603 của 4a4577d thành công.

Tái hiện bằng mô hình giả: bản sửa dùng [1, 2] thay [1][2] bị kiểm định dạng từ
chối dù bộ xử lý nguồn chấp nhận dạng nhóm. Chuẩn hóa nhóm ngay tại vị trí cũ
trước đối chiếu thứ tự/tần suất và số liệu; giữ nguyên mã, ảnh và liên kết Markdown.
Không tự thêm dấu mất hoặc đổi nguồn. Bộ kiểm trình bày/nguồn: 104 đạt trong
5,48 giây; Ruff và diff check đạt. Chưa khẳng định đây là dạng dấu cụ thể của
lượt live trước vì dấu vết không lưu bản sửa bị từ chối. Chưa chứng nhận chất
lượng ngữ nghĩa hay câu trả lời cloud từ phép kiểm mô hình giả.

CI 37333982226 của 3b3afbc02880b76b3635f97d8c8fb4cf5187a157 đã thành công.
Kho GHCR trả ảnh sha256:13546369e918ebba41fb621aad27c77b8c2e2d9da279b301684e8f6ca8ccb0c7.
Đã cập nhật nguồn ảnh dịch vụ Render hiện có; lần triển khai
dep-db1sandg1s2s73bj3chg bắt đầu 22:42:25 ngày 05/10 giờ Việt Nam,
hoàn tất Live lúc 22:44:16. Không dùng trạng thái Live để thay nghiệm thu chức năng.

## Phạm vi chốt và nhóm A — ngày 06/10

Chủ sở hữu loại nhóm C (tốc độ/khả dụng mở rộng) và D (khôi phục/quan sát/an toàn
nâng cao) khỏi đợt demo. Hai nhóm giữ nhãn `EXCLUDED`, không tính điểm và không
được đổi thành đạt. Đợt chốt chỉ còn A, B, E, F; lỗi nghiêm trọng về quyền, mất dữ
liệu hoặc ghi thiếu duyệt nếu phát hiện vẫn chặn phát hành.

Trên đúng cloud `3b3afbc`, bản xem trước Google Doc hết hạn được nhận diện; nút
**Tạo lại bản xem trước** tạo khóa mới, sau đó vẫn yêu cầu một lần xác nhận riêng.
Chủ sở hữu đã cho phép đúng một tài liệu giả lập. Sau xác nhận, giao diện báo
"Google Doc đã được tạo và đọc lại thành công" và trả liên kết tài liệu
`1D2AjL-9R8Ho5Tn0logDock0oUQUkO9NJytFfZeKZT9A`. Không gửi thư, không đổi quyền
chia sẻ và không tạo lại lần hai. Nhánh phục hồi bản xem trước của A đạt.

Ca báo cáo 200–240 từ trên cùng cloud lại lộ lỗi điều phối: cụm mô tả
"phép tính 24 × 12..." bị tuyến tính toán bắt giữa câu rồi cắt còn số 24, kết quả
chỉ là `24 = 24`, một sự kiện công cụ. Đây là lỗi thật, không dùng câu trả lời cũ
để lấp. Sửa tuyến chung: chỉ đi thẳng vào máy tính khi yêu cầu bắt đầu bằng mệnh
lệnh tính hoặc gọi rõ công cụ calculate, đồng thời phải có ít nhất hai toán hạng
và toán tử hỗ trợ. Yêu cầu báo cáo có phép tính ở giữa tiếp tục qua tổng hợp nguồn.
Hai kiểm hồi quy mới khóa đúng lỗi; bộ routing/compiler/trình bày liên quan **255
đạt**, Ruff và diff check đạt. Cần CI, triển khai và chạy lại ca báo cáo/PDF trước
khi đóng toàn nhóm A.
