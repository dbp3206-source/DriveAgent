# Lưu 30 ngày và tự dọn — đối chiếu triển khai

> **Trạng thái hiện hành — 17/10/2026:** bản chạy hiện vẫn yêu cầu xác nhận trước khi dọn. Chủ sở hữu vừa chọn đổi sang tự dọn khi đủ 30 ngày, kể cả khi người dùng không xác nhận; mã và lịch nền mới chưa triển khai/bật. Đây là yêu cầu đã chốt, **chưa phải giới hạn lưu có hiệu lực**. Các ghi chú lịch sử phía dưới phản ánh trạng thái tại thời điểm ghi. Bản gốc Google, tệp tải về và bản sao ngoài Veridra không nằm trong phạm vi. `/api/health` của bản hiện hành trước sửa đã trả `ok`, cơ sở dữ liệu và kho tệp sẵn sàng; điều đó không chứng minh cơ chế mới hoạt động, cũng không có nghĩa khôi phục DB/tệp, xóa toàn kho, quyền riêng tư pháp lý hoặc toàn bộ sản phẩm đã nghiệm thu.

**Cập nhật quyết định 17/10:** khi bật lịch nền, mọi mục Veridra đã quá 30 ngày cũng đủ điều kiện được đưa vào hàng đợi. Bộ điều phối phải kiểm kê đủ kho, hoãn mục đang hoạt động, xác minh xóa/đọc lại và báo lỗi thay vì coi là đã xóa. Nếu kiểm kê hoặc kho lỗi, việc chuyển sang trạng thái cần xử lý và tự thử lại có giãn cách; trong thời gian lỗi không thể cam kết xóa đúng hạn. Lịch dự kiến chạy mỗi 15 phút, không gửi nội dung người dùng sang bên thứ ba. Tác vụ tự động không thể bị hủy qua giao diện.

**Đang nối kiểm soát ghi theo tài khoản, 16/10:** yêu cầu HTTP, ba bộ máy trợ lý, công cụ và các tác vụ nền dùng chung lớp tiếp nhận; việc dọn đợi việc đã nhận, chặn ghi mới của đúng người, không tiêu hao lần thử khi bị hoãn. Luồng ghi chạy riêng vẫn được giữ quyền sau hủy, tránh ghi lại sau xóa. Kiểm gộp tại máy 342 đạt/5 bỏ qua; còn đợi CI đúng mã và kiểm riêng bổ sung tệp tạm. **Chưa có bộ điều phối/API/hộp thoại đầy đủ, chưa triển khai/xóa dữ liệu thật**. [Phạm vi và bằng chứng](../design-work/production-20261013/qa/retention-admission-20261016.md).

**Mới nhất ngày 16/10 — CI #148:** mã620c2d7 đã có bộ xóa SQL ứng dụng, mẫu/bản kiểm, làm sạch sổ thao tác nhưng giữ chống ghi lại Google, và bộ xóa ngữ cảnh ADK cũ. Đồng hồ bảng phụ không gia hạn khi chỉ xem/cất; kiểm FK tránh xóa con chưa được duyệt và giữ hội thoại mới hoạt động. PDF có thêm xóa–đọc lại, không nhận mọi 404 là không còn tệp. [CI #148](https://github.com/dbp3206-source/DriveAgent/actions/runs/38846606316) đạt **19 PostgreSQL, máy chủ 1.769 đạt/20 bỏ qua, độ phủ 88,44%, giao diện 222 đạt**; 41 ca kho tệp đạt trên Linux. Xuất ảnh/Render bỏ qua, không gọi AI/Google hoặc xóa dữ liệu thật. **Chưa có bộ điều phối đầy đủ/API/hộp thoại, chưa có trên URL**; SQL không thay chứng minh xóa tệp Supabase thật/Qdrant/ngữ cảnh mới hơn. [Hồ sơ đúng phạm vi](../design-work/production-20261013/qa/retention-purge-20261016.md).

**Mới nhất — CI #147:** mã 4be8c27 đã qua [đợt kiểm cuối](https://github.com/dbp3206-source/DriveAgent/actions/runs/38841271707), bao gồm hai bổ sung sau CI #146: PostgreSQL 18 đạt, máy chủ 1.722 đạt/19 bỏ qua, độ phủ 88,36%, giao diện 222 đạt. Dựng/khởi động gói/PDF đạt; GHCR/Render bỏ qua. Đây là bằng chứng mã hàng đợi/kiểm kê, **không phải nghiệm thu xóa xuyên kho/API/hộp thoại hoặc bằng chứng trên URL**.

**CI #146:** phần hàng đợi mã b58cccd đã qua [kiểm đầy đủ](https://github.com/dbp3206-source/DriveAgent/actions/runs/38840537752), gồm PostgreSQL thật 18 đạt, máy chủ 1.719 đạt/19 bỏ qua và giao diện 222 đạt; không xuất ảnh GHCR/triển khai Render. Có bổ sung nhỏ sau đó về yêu cầu đã hủy và hình dạng danh sách tiến độ, chưa dùng CI cũ chứng minh mã bổ sung. Giới hạn chưa có bộ thực thi/API/hộp thoại trên URL giữ nguyên.

**Cập nhật 16/10:** CI #145 của mã d46916d đã thành công, gồm 17 ca PostgreSQL; đã xác nhận riêng phần kiểm kê ADK và tuổi nguồn cập nhật lại. Đợt tiếp theo có sổ tiến độ dọn dữ liệu bền vững, chỉ chứa ID/dấu nội dung, chưa chứa bộ thực thi xóa hoặc API. Một bản duyệt chỉ tạo một việc; tác vụ cũ hết quyền không được ghi tiếp; các mục đã xử lý/còn lại không bị mất khi mở lại DB. Có nâng cấp cộng thêm SQLite 9/PostgreSQL 8 trong mã, **chưa áp dụng lên dữ liệu thật**. Phần mới kiểm gộp tại máy 89 đạt, còn chờ CI đúng mã. Nhận xét/bản nháp/yêu cầu mới bảo vệ hội thoại và câu trả lời cha, tránh xóa kéo theo nội dung mới. **Vẫn chưa bật dọn tự động/hộp thoại trên URL**, chưa tính gói 14 đạt.

Ngày 15/10/2026. Thuộc gói 14 hiện hành, không thêm gói hoặc điểm nghiệm thu. **Chưa triển khai, chưa có trên URL, không phải biên nhận đã xóa.** Mục đích: khóa đúng phạm vi trước khi viết cơ chế có thể xóa dữ liệu. Bản đang chạy là 13938d1; các chỉnh sửa tài liệu/kiểm về sau không tự đổi bản chạy.

**Tiến độ mã và CI:** mã f46d3d0 trên nhánh `work/data-retention-20261015` đã qua [CI #143](https://github.com/dbp3206-source/DriveAgent/actions/runs/38763155806), gồm 14 kiểm PostgreSQL thật ở môi trường CI riêng. Có lõi chọn mốc 30 ngày và bản xác nhận gắn tài khoản/nội dung, hết hạn sau 10 phút, tối đa 200 mục mỗi bản (báo rõ còn mục khác); không thêm mục mới vào bản cũ. Đã tách ngày sửa nội dung cho ghi chú, kết quả đã lưu và hồ sơ công ty, không gia hạn chỉ vì xem/cất/đối chiếu lại. Có nâng cấp lược đồ SQLite 8 / PostgreSQL 7, giữ dữ liệu và cột nullable để tương thích quay lui; dữ liệu cũ lấy ngày cập nhật đã biết theo hướng thận trọng, không bịa lại ngày sửa nội dung trước đó. **Chưa có API/giao diện xác nhận hoặc bộ thực thi xóa các kho**. Không tính lõi/CI là nghiệm thu cơ chế xóa trên URL; các bước xuất ảnh và triển khai Render bị bỏ qua đúng điều kiện nhánh. [Hồ sơ kiểm nội bộ](../design-work/production-20261013/qa/retention-foundation-20261015.md).

## Quyết định và cách hiểu

**Đang nối kiểm kê:** mã 7ab69ba đã qua [CI #144](https://github.com/dbp3206-source/DriveAgent/actions/runs/38767074632), gồm 16 ca PostgreSQL, máy chủ 1.682 đạt/17 bỏ qua và giao diện 222 đạt. Đọc riêng theo tài khoản cho đủ 15 bảng nội dung ORM, không dùng giới hạn trang UI hoặc đọc bảng tài khoản/khóa. Hội thoại cũ có lượt mới được bảo vệ; tác vụ đang chạy chặn chuẩn bị xóa. Ngày mẫu nằm ở bảng phụ, giữ nguyên bảng tám cột cũ; đọc/cất/lưu nguyên nội dung không gia hạn. Sau đó đã nối kiểm kê ADK và bảo vệ nguồn vừa cập nhật lại, kiểm gộp tại máy 57 đạt; các phần mới cần CI tương ứng. Kho phụ chưa được tính hoàn tất chỉ vì đọc được DB chính. **Vẫn chưa có API/hộp thoại/bộ thực thi xóa**.

Chủ sở hữu chọn đầu vào đa dạng, không chứa bí mật công ty và chốt chính sách cuối ngày 17/10: **cảnh báo trước hạn; tự dọn dữ liệu Veridra khi đủ 30 ngày mà không chờ xác nhận**. Người dùng vẫn có thể chủ động dọn sớm qua bước xem trước và xác nhận. Lịch tự động chỉ xếp tác vụ sau khi kiểm kê đủ kho; mục đang hoạt động hoặc kho chưa kiểm chứng được sẽ bị hoãn/đánh dấu cần xử lý, không báo đã xóa. Vì vậy, trong lúc tác vụ bị hoãn hoặc kho lỗi, sản phẩm chưa thể bảo đảm mốc xóa tuyệt đối. Không gọi Gemini để quyết định mục nào được xóa. Khi bật lịch, dữ liệu Veridra đã quá hạn cũng đủ điều kiện được xếp dọn; không xóa bản gốc Google, tệp tải về hoặc bản sao ngoài Veridra.

Đầu vào có thể chứa thông tin cá nhân: chủ sở hữu cho phép biện pháp bảo mật nhưng không xác nhận mọi tài liệu đã ẩn danh. Không tự nâng gói, thêm mô hình hoặc coi sự đồng ý này thay điều kiện Gemini. Giữ nguyên ngân sách kiểm đã duyệt.

## Kiểm kê đã đối chiếu

Đã đọc mô hình, adapter lưu trữ và truy vấn `information_schema.columns` trên project đang chạy. Truy vấn chỉ trả tên bảng/cột, không đọc nội dung, khóa, tên tệp hoặc dữ liệu người dùng; không chạy DDL/DML. Có bảng ADK ở cả `veridra_private` và `public` từ bản cũ. Sự tồn tại bảng không chứng minh nó chứa dữ liệu hay đang được dùng; phải kiểm chủ sở hữu trước xử lý, không suy ra được phép truy cập công khai.

| Phần | Nơi lưu thật cần xét | Ràng buộc khi thực hiện |
|---|---|---|
| Hội thoại | `chat_sessions`, `messages`, `chat_tasks`, `creation_proposals`, `response_feedback` | Không xóa hội thoại còn lượt mới/tác vụ đang chạy chỉ vì ngày tạo hội thoại cũ; xử lý nội dung và bản sao hàng đợi liên quan |
| Ngữ cảnh của bộ máy trợ lý | ADK `sessions`, `events`, `user_states`; `graph_checkpoints`; local `langgraph_checkpoints.db` | Cả namespace hiện hành/cũ; đúng người dùng/luồng. `app_states` dùng chung không được xóa theo một người hoặc tự coi đã sạch |
| Ghi chú nhớ lâu | `long_term_memories`, vector SQL/Qdrant | Mục đã cất vẫn chứa nội dung. Xóa SQL và chỉ mục; truy xuất mới không còn kết quả |
| Tệp nhập | `local_sources`, `pdf_ingestion_jobs`, đối tượng PDF riêng | Xóa cả văn bản/checkpoint/PDF gốc Veridra giữ; không xóa tệp Google. Không xử lý khi tác vụ nhập đang chạy |
| Tài liệu đã lập chỉ mục | `drive_file_index`, `document_chunks`, vector SQL/Qdrant | Chỉ dọn bản/chỉ mục của Veridra, không thao tác xóa trên Drive. Nguồn có thể được nhập/lập chỉ mục lại về sau theo yêu cầu mới |
| Kết quả/mẫu đã lưu | `saved_artifacts`, `skills`, `company_profiles` | Đưa vào danh sách cho người dùng duyệt, kể cả mục đã cất; không lặng lẽ loại vì khó xử lý hoặc xóa nội dung vừa được sửa |
| Tác vụ đã hẹn/bộ kiểm | `scheduled_jobs`, `evaluation_jobs` | Xét phần nội dung/checkpoint. Không để tiến trình đang chạy ghi lại dữ liệu vừa xóa |
| Sổ hành động ngoài | `operations.spec`, `operations.result` | Nội dung có thể chứa bản nháp/người nhận. Giữ dấu chống gửi lại và thông tin trạng thái tối thiểu; chưa rõ kết quả phải đối soát, không xóa sổ rồi phát lại |
| Nhật ký và bản sao | `audit_events`; dấu vết trong Message, tệp quan sát và bản sao | Phân biệt nội dung với số đo tối thiểu. Cơ chế cũ dọn dấu vết/bản sao 30 ngày không dọn mọi nội dung người dùng; không hứa xóa bản sao nhà cung cấp hoặc bản tải về máy khác |

Nguồn mã: `backend/app/db/models.py`, `db/framework_sessions.py`, `db/framework_security.py`, `agent/adk_orchestrator.py`, `agent/orchestrator.py`, `services/operations.py`, `services/relational_operations.py`, `services/skills.py`, `services/relational_skills.py`, `services/relational_evaluation.py`, `services/object_storage.py`, `services/vector_store.py`, `services/agentops.py`, `services/backup_retention.py`.

Tài khoản/quyền đăng nhập, khóa API, bộ đếm hạn mức, dấu chống phát lại và phiên bản lược đồ không phải nội dung công việc cần tự xóa theo tuổi. Không xóa tài khoản hoặc đặt lại hạn mức dưới tên “dọn dữ liệu”. Đăng xuất/ngắt quyền có cơ chế riêng. Trạng thái dùng chung hoặc dữ liệu không xác định được chủ phải báo chưa xử lý, không xóa rộng cho tiện.

## Quy trình phải triển khai

1. **Liệt kê:** máy chủ tìm dữ liệu đến hạn của đúng người đang đăng nhập; không lấy ngày/ID do trình duyệt tự quyết. Thể hiện loại, số lượng và khoảng thời gian; không đưa nội dung riêng vào nhật ký. Tuổi phải được xác định theo từng loại: lượt chat theo ngày lưu, nội dung chỉnh sửa theo lần thay đổi nội dung, nguồn nhập theo ngày nhập; thao tác xem hoặc cất không tự gia hạn.
2. **Thông báo và duyệt:** hộp thoại cho biết xóa không hoàn tác, phạm vi và các bản liên quan; có “Xóa dữ liệu đã chọn” và “Để sau”. Chưa duyệt thì không xóa. Phiên bản/nội dung đổi sau lúc xem phải làm mới danh sách và duyệt lại, không xóa thêm các mục mới đến hạn ngoài danh sách đã xem. Không chen hộp thoại lặp lại ở mỗi lần chuyển trang.
3. **Thực hiện và đối chiếu:** dùng lệnh máy chủ có kiểm tài khoản/nguồn yêu cầu, mã lần chạy chống lặp; không cho mô hình tự duyệt. Xử lý đúng các bản lưu liên quan trong kiểm kê, không gọi Gemini hoặc Google ghi. Lỗi một kho phải ghi phần còn lại và thử tiếp đúng mục, không báo hoàn tất sớm. Đọc lại danh sách, thử tìm/khôi phục ngữ cảnh và kiểm hàng đợi không tạo lại nội dung. Sau thành công làm mới trang/ẩn bản cũ đang giữ trong bộ nhớ trình duyệt.

Không dùng đường xóa hội thoại/ghi chú hiện tại làm chứng minh đã có toàn bộ quy trình này. `VectorStore.delete_points` hiện có đường chuyển sang dự phòng khi lỗi; việc không ném lỗi không đủ chứng minh vector vật lý đã bị xóa. Cần xác nhận từng kho trước công bố biên nhận.

## Kiểm gộp bắt buộc, không cần dịch vụ AI

- Mốc tuổi: trước/đúng/sau 30 ngày, múi giờ; nội dung mới trong hội thoại cũ và bản sửa mới không bị xóa nhầm. Việc đọc/cất không gia hạn.
- Xem danh sách/Hủy/Để sau/tải lại không xóa gì; không đăng nhập, tài khoản khác, yêu cầu từ trang khác, sửa mã duyệt hoặc danh sách cũ đều không được xóa.
- Cùng một mẫu giả lập chứa dấu nhận diện ở mọi kho liên quan: sau duyệt, nội dung/xem trước/tìm kiếm/ngữ cảnh không còn dấu đó; dữ liệu mới và tài khoản khác giữ nguyên.
- Giả lập kho tệp/vector mất kết nối và tiến trình dừng giữa chừng: không báo thành công toàn bộ; tiếp tục đúng mục, không gọi Google lại. Tác vụ đang chạy không ghi lại nội dung đã xóa.
- Mã chống phát lại, khóa và quyền không bị xóa; bản gốc Google không có yêu cầu ghi/xóa. Bản sao chưa quản lý được phải công bố rõ, không tính là đã xóa.
- Mở ứng dụng thật ở máy tính/điện thoại: hộp thoại theo Fluent/theme hiện có, bàn phím hoạt động, không tràn, có trạng thái chờ/lỗi/xong. Chỉ chụp dữ liệu giả lập. Kiểm qua hai kiểu lưu trữ và CI hiện có trước triển khai; không tạo môi trường trả phí hoặc đòi lại mật khẩu DB đã được miễn.

Không tạo điểm chất lượng bằng số tiêu chí vừa liệt kê; chỉ ghi đạt sau thực thi có bằng chứng. Bộ kiểm khôi phục DB và T09 vẫn được miễn, không dùng miễn kiểm để bỏ kiểm quyền trong chức năng xóa mới.

## Điều kiện bên xử lý và bằng chứng công cụ

Đã dùng skill `supabase:supabase` để kiểm kê bằng truy vấn chỉ đọc, không phải để chứng nhận tuân thủ. Đối chiếu [tài liệu xóa đối tượng Supabase](https://supabase.com/docs/guides/storage/management/delete-objects): phải xóa qua Storage API, không xóa dòng metadata bằng SQL để giả định đối tượng đã mất. Kiểm [changelog](https://supabase.com/changelog) có thông báo TLS ngày 12/10, chưa có thay đổi được xác định cần sửa adapter xóa hiện tại; không cập nhật dependency vì việc này.

Hai lần đọc URL Markdown bằng công cụ web trả `400 Unsupported content-type: text/markdown`; đã chuyển sang trang HTML chính thức và đọc được. Đây là lỗi đọc tài liệu, không phải lỗi sản phẩm hoặc Storage. Truy vấn cấu trúc cloud hoàn tất thành công; không kiểm xóa trên dữ liệu thật.

[Điều khoản Gemini](https://ai.google.dev/gemini-api/terms), đối chiếu 15/10: với dịch vụ không trả phí, không gửi dữ liệu cá nhân/nhạy cảm/bí mật; mã hóa lúc truyền/lưu không làm mất điều kiện này. Không khẳng định đã ẩn danh toàn bộ chỉ vì tìm/che được email hoặc số điện thoại. Lựa chọn xử lý dữ liệu thật phải phù hợp điều kiện nhà cung cấp, không đổi thành chỉ dữ liệu giả lập rồi gọi sản phẩm Production đầy đủ.

# Cập nhật 16/10/2026 — nghiệm thử đầy đủ tại máy

- Backend: 1.915 đạt, 28 bỏ qua, 0 lỗi, độ phủ 88,31%; 11 bài cấu hình riêng cũng đạt. Trong 28 ca bỏ qua có 23 ca PostgreSQL và 5 ca kho tệp ngoài, cần dịch vụ CI tương ứng.
- Giao diện: 222 bài đạt, lint và bản dựng cô lập đạt; ảnh trình duyệt ở sáng/tối và các kích thước chính đã được rà lại. Không gửi yêu cầu xóa trong kiểm thử.
- Quét bí mật, kiểm bộ dữ liệu giả lập và đánh giá ngoại tuyến đều đạt; đánh giá 200/200 không gọi mô hình.
- Đây là ghi nhận tại thời điểm kiểm tra tại máy, chưa phải kết quả cuối. Cập nhật CI mới nhất ở cuối tài liệu.

## Cập nhật 16/10/2026 — kết quả CI đã có

- CI GitHub Actions [#38925155479](https://github.com/dbp3206-source/DriveAgent/actions/runs/38925155479) chạy trên commit `3dad6f5b1101a95a7ecd390e5a4e6ba30686697a` và đạt. Cả hai job `postgres-state` và `verify` thành công; gồm backend, frontend, dựng/kiểm ảnh chạy và xuất PDF tiếng Việt.
- Commit đã được đẩy lên `work/data-retention-20261015`, nhưng chưa lên `main` hoặc Render. Các bước xuất bản ảnh và triển khai tự động bị bỏ qua do đây không phải nhánh phát hành; URL chưa được kiểm.
- Kết quả này thay thế nhận định trước đó rằng CI còn chờ. T09 và diễn tập khôi phục vẫn được miễn, không tính đạt; chưa có dữ liệu thật nào bị đọc hoặc xóa.
# Cập nhật 16/10/2026 — phần thực thi đã có tại máy, chưa phát hành

- Đã nối giao diện nhắc/xem trước/xác nhận và API có xác thực, kiểm nguồn, sổ tiến độ, tiếp tục sau gián đoạn; chưa gọi Google/Gemini. Kiểm thử dùng dữ liệu tổng hợp cô lập.
- Đã sửa cách tính tuổi ngữ cảnh LangGraph: không dùng mốc sửa của SQLite/WAL dùng chung; dùng mốc UUIDv6 riêng trong checkpoint và dòng ghi, lọc đúng người sở hữu, định dạng lạ thì dừng an toàn. Hộp thoại thông báo rằng dọn dữ liệu có thể đặt lại ngữ cảnh trợ lý; lịch sử chat chuẩn vẫn được giữ.
- Ruff đạt; backend chọn lọc **205 đạt/23 bỏ qua**; frontend **222 unit test đạt**, lint/build/Playwright cục bộ đạt. Chi tiết và ảnh tại [QA 16/10](../design-work/retention-ui-20261016/qa/qa-report.md).
- **Chưa production-ready và chưa có trên URL:** thay đổi còn chưa commit trên `work/data-retention-20261015`; cần CI đúng mã (gồm PostgreSQL), rà diff, đẩy theo nhánh phát hành, triển khai và xác minh URL. T09 khôi phục và bốn tài khoản vẫn được miễn, không ghi là đạt. Dữ liệu thật chưa bị đọc hoặc xóa.
