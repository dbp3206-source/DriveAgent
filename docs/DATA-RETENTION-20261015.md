# Lưu 30 ngày và xóa sau xác nhận — đối chiếu triển khai

**Cập nhật 16/10:** CI #145 của mã d46916d đã thành công, gồm 17 ca PostgreSQL; đã xác nhận riêng phần kiểm kê ADK và tuổi nguồn cập nhật lại. Đợt tiếp theo có sổ tiến độ dọn dữ liệu bền vững, chỉ chứa ID/dấu nội dung, chưa chứa bộ thực thi xóa hoặc API. Một bản duyệt chỉ tạo một việc; tác vụ cũ hết quyền không được ghi tiếp; các mục đã xử lý/còn lại không bị mất khi mở lại DB. Có nâng cấp cộng thêm SQLite 9/PostgreSQL 8 trong mã, **chưa áp dụng lên dữ liệu thật**. Phần mới kiểm gộp tại máy 89 đạt, còn chờ CI đúng mã. Nhận xét/bản nháp/yêu cầu mới bảo vệ hội thoại và câu trả lời cha, tránh xóa kéo theo nội dung mới. **Vẫn chưa bật dọn tự động/hộp thoại trên URL**, chưa tính gói 14 đạt.

Ngày 15/10/2026. Thuộc gói 14 hiện hành, không thêm gói hoặc điểm nghiệm thu. **Chưa triển khai, chưa có trên URL, không phải biên nhận đã xóa.** Mục đích: khóa đúng phạm vi trước khi viết cơ chế có thể xóa dữ liệu. Bản đang chạy là 13938d1; các chỉnh sửa tài liệu/kiểm về sau không tự đổi bản chạy.

**Tiến độ mã và CI:** mã f46d3d0 trên nhánh `work/data-retention-20261015` đã qua [CI #143](https://github.com/dbp3206-source/DriveAgent/actions/runs/38763155806), gồm 14 kiểm PostgreSQL thật ở môi trường CI riêng. Có lõi chọn mốc 30 ngày và bản xác nhận gắn tài khoản/nội dung, hết hạn sau 10 phút, tối đa 200 mục mỗi bản (báo rõ còn mục khác); không thêm mục mới vào bản cũ. Đã tách ngày sửa nội dung cho ghi chú, kết quả đã lưu và hồ sơ công ty, không gia hạn chỉ vì xem/cất/đối chiếu lại. Có nâng cấp lược đồ SQLite 8 / PostgreSQL 7, giữ dữ liệu và cột nullable để tương thích quay lui; dữ liệu cũ lấy ngày cập nhật đã biết theo hướng thận trọng, không bịa lại ngày sửa nội dung trước đó. **Chưa có API/giao diện xác nhận hoặc bộ thực thi xóa các kho**. Không tính lõi/CI là nghiệm thu cơ chế xóa trên URL; các bước xuất ảnh và triển khai Render bị bỏ qua đúng điều kiện nhánh. [Hồ sơ kiểm nội bộ](../design-work/production-20261013/qa/retention-foundation-20261015.md).

## Quyết định và cách hiểu

**Đang nối kiểm kê:** mã 7ab69ba đã qua [CI #144](https://github.com/dbp3206-source/DriveAgent/actions/runs/38767074632), gồm 16 ca PostgreSQL, máy chủ 1.682 đạt/17 bỏ qua và giao diện 222 đạt. Đọc riêng theo tài khoản cho đủ 15 bảng nội dung ORM, không dùng giới hạn trang UI hoặc đọc bảng tài khoản/khóa. Hội thoại cũ có lượt mới được bảo vệ; tác vụ đang chạy chặn chuẩn bị xóa. Ngày mẫu nằm ở bảng phụ, giữ nguyên bảng tám cột cũ; đọc/cất/lưu nguyên nội dung không gia hạn. Sau đó đã nối kiểm kê ADK và bảo vệ nguồn vừa cập nhật lại, kiểm gộp tại máy 57 đạt; các phần mới cần CI tương ứng. Kho phụ chưa được tính hoàn tất chỉ vì đọc được DB chính. **Vẫn chưa có API/hộp thoại/bộ thực thi xóa**.

Chủ sản phẩm chọn đầu vào đa dạng, không chứa bí mật công ty, lưu khoảng 20–30 ngày và phải thông báo/xác nhận trước xóa. Chọn mốc 30 ngày. Không tự xóa khi chưa xác nhận; vì vậy đây là nhắc dọn dữ liệu có duyệt, **không phải giới hạn lưu tối đa 30 ngày tuyệt đối**. Không gọi Gemini để quyết định mục nào được xóa. Không dùng quyết định này để xóa ngay dữ liệu hiện hữu.

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
