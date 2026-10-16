# Nền tảng lưu giữ dữ liệu — kiểm nội bộ 15/10/2026

Thuộc gói 14. Lượt trước là tiến bộ: đã ghi quyết định chủ sở hữu, kiểm cấu trúc cloud và đồng bộ tài liệu ở bbbd449. Lượt này thực hiện mã tại máy, chưa xóa dữ liệu thật, gọi Gemini/Google hoặc triển khai. Không nghiệm thu Production hoặc coi yêu cầu mới đã có trên URL.

## Nội dung đã thực hiện

- `backend/app/services/retention_policy.py`: mốc 30 ngày theo UTC, bản chọn có chữ ký riêng/gắn tài khoản/dấu nội dung và thời hạn 10 phút. Không mang nội dung ghi chú vào bản xác nhận, không chọn mục đang chạy. Tối đa 200 mục mỗi bản, công bố tổng/còn mục khác, không âm thầm lấy thêm mục mới. Kho chưa kiểm kê đầy đủ thì không cấp/chấp nhận bản xác nhận. Mô-đun không có đường xóa, lời gọi mạng hoặc quyền tự duyệt.
- Tách `content_updated_at` cho `SavedArtifact`, `LongTermMemory`, `CompanyProfile`. Theo dõi thay đổi nội dung thật; xem/cất và ngày kiểm chứng không tự gia hạn. Đường cập nhật hàng loạt của kết quả đã lưu dùng biểu thức trong cùng câu lệnh kiểm phiên bản, vì đường đó không phát sự kiện ORM.
- Nâng cấp SQLite 8 / PostgreSQL 7: thêm cột nullable, giữ nội dung, lấy ngày cập nhật gần nhất đã biết cho dữ liệu cũ theo hướng thận trọng; không suy đoán ngày nội dung cũ khi nhật ký không đủ. Cột nullable cho phép mã cũ chưa biết trường mới vẫn ghi được sau quay lui; bộ thực thi tương lai phải xử lý trường null theo ngày đã biết, không tự xóa sớm.
- Thêm 23 kiểm hợp đồng, 6 kiểm ngày nội dung/nâng cấp SQLite; thêm một kiểm nâng cấp PostgreSQL chỉ cho DB `veridra_ci` và có rollback giao dịch. Không dùng DB nguồn/đích khôi phục đã được miễn.

## Lệnh và kết quả thực

1. Ruff kiểm tệp mới lần đầu đạt; khi bổ sung models, Ruff phát hiện `I001`/`E501` ở dòng import dài. Đã sửa import thành khối chuẩn; `backend/.venv/Scripts/python.exe -m ruff check backend` sau sửa đạt. Không bỏ quy tắc để qua kiểm.
2. `pytest backend/tests/test_retention_policy.py`: **23 đạt**, 0 lỗi, 0 bỏ qua, 0,34 giây. Đây là kiểm thuần hợp đồng, không có DB hoặc bộ thực thi xóa.
3. Kiểm gộp policy/clocks/migrations/artifacts/memory, môi trường không nạp `.env` và bỏ biến DRIVE_AGENT_/GEMINI_/GOOGLE_ trong tiến trình thử: **46 đạt**, 0 lỗi, 0 bỏ qua, 12,89 giây. DB và tệp đều ở thư mục thử mới, không dùng lại `--basetemp` cũ.
4. Toàn bộ `backend/tests` cùng `--cov=app --cov-fail-under=85`: **1.660 đạt, 17 bỏ qua, 0 lỗi**, 286,73 giây; độ phủ báo **87,36%**. Các nhóm trên nằm trong tổng này, không cộng lặp. Có cảnh báo coverage `module-not-measured` do nạp Settings để tắt `.env` trước khi pytest khởi động; công bố đúng số báo, không gọi là đo đầy đủ mã lúc khởi động. CI cần chạy cách thông thường và kiểm PostgreSQL riêng.
5. `git diff --check` đạt; `scripts/scan_release_secrets.py` đạt với **724 tệp Git-visible** trước khi thêm hồ sơ Markdown này. Kiểm không chứng minh mọi dữ liệu đã ẩn danh hoặc mọi kho đã xóa.

XML riêng: `tmp/retention-clocks-a68dc174295048eaa3d526a23b1ec5d5/results.xml`, `tmp/retention-regression-b1a6975a381a400cb7a10c4dbaeab9b6/results.xml`. Tệp thô trong vùng bị Git bỏ qua; chỉ bản tổng hợp giả lập được đưa vào hồ sơ công khai. Không đưa XML, DB, khóa hoặc nội dung riêng lên GitHub.

## CI #143 đã hoàn tất

[Lần kiểm 38763155806](https://github.com/dbp3206-source/DriveAgent/actions/runs/38763155806), mã **f46d3d02a7290e62adb3a4a92a78ac39d71a4973**, nhánh `work/data-retention-20261015`. Đã đọc trạng thái bước và nhật ký qua kết nối GitHub, không chỉ lấy việc đẩy mã làm bằng chứng. Cả hai công việc hoàn tất/thành công:

- `postgres-state`, job `116519416636`: **14 đạt**, 0 bỏ qua, 3,69 giây; tệp gồm ca nâng cấp ngày nội dung mới. DB riêng `veridra_ci`, không phải Supabase đang chạy.
- `verify`, job `116519800337`: máy chủ **1.662 đạt/15 bỏ qua**, 165,67 giây, độ phủ **88,19%**; hai tệp kiểm mới hiện rõ sáu và 23 ca đạt. Giao diện **222 đạt/0 lỗi/0 bỏ qua**. Kiểm ngoại tuyến, toàn vẹn bộ chuẩn, quét bí mật, dựng frontend, dựng/khởi động gói và xuất PDF tiếng Việt thành công.
- **Publish the verified image** và **Deploy the exact verified image to Render** đều `skipped`. Không có ảnh mới được đẩy GHCR hoặc triển khai; không gọi hook Render, đổi Environment/gói hoặc áp dụng migration lên Supabase. Gói Docker kiểm chỉ là artifact CI, không lấy nó làm bằng chứng Live.

Kết quả CI và tại máy có phần chồng lặp, không cộng thành số ca/điểm sản phẩm. Không thay kết quả bỏ qua thành đạt; số tại máy và CI được ghi tách biệt. CI này chỉ chứng minh mã nền tảng và hồi quy đúng mã, chưa chứng minh chuỗi xóa hay giao diện chưa được viết.

## Giới hạn và bước kế tiếp đúng phạm vi

### CI #145 đã hoàn tất

[Lần kiểm 38771195658](https://github.com/dbp3206-source/DriveAgent/actions/runs/38771195658), mã **d46916d192797a569b1c56d23de3ffe483b02529**. Đã đọc trạng thái bước và nhật ký GitHub: PostgreSQL `116547140137` **17 đạt/0 bỏ qua**, 4,90 giây; verify `116547457252` máy chủ **1.688 đạt/18 bỏ qua**, 87,49 giây, độ phủ **88,23%**, giao diện **222 đạt/0 lỗi/0 bỏ qua**. Ngoại tuyến, toàn vẹn bộ chuẩn, quét bí mật, dựng/khởi động gói và PDF tiếng Việt thành công. Bước xuất ảnh/Render đều `skipped`. Các thông báo PostgreSQL trùng khóa trong sổ chống phát lại là kết quả các ca cạnh tranh cố ý, không phải lỗi thử bị bỏ qua; tổng kiểm PostgreSQL thành công. CI này không chứng minh hàng đợi hoặc sửa đổi sau mã d46916d đã đạt.

### CI #146 đã hoàn tất

[Lần kiểm 38840537752](https://github.com/dbp3206-source/DriveAgent/actions/runs/38840537752), mã **b58cccdf015f39dec8076e74e70c73629e7a4040**. PostgreSQL `116779355144` **18 đạt/0 bỏ qua**, 3,72 giây, gồm ca hàng đợi cạnh tranh/nhận lại/cách ly và chỉ mục một việc mở mỗi người. Verify `116779551846`: **1.719 đạt/19 bỏ qua**, 172,80 giây, độ phủ **88,35%**; giao diện **222 đạt/0 lỗi/0 bỏ qua**. Ngoại tuyến/toàn vẹn bộ chuẩn/quét bí mật/dựng/khởi động gói/PDF đạt. Xuất ảnh GHCR và Render `skipped`. Không triển khai hoặc áp dụng lược đồ lên dữ liệu thật.

Rà soát cuối phát hiện API chat thật dùng trạng thái `cancelled`, trong khi kiểm kê ban đầu chỉ công nhận completed/failed: một yêu cầu đã hủy sẽ chặn dọn mãi. Đã đối chiếu nguồn, bổ sung riêng trạng thái kết thúc này cho chat; trạng thái không nhận diện vẫn chặn, không nới mọi loại tác vụ. Đồng thời yêu cầu JSON tiến độ thực sự là danh sách, không nhận đối tượng rỗng thay danh sách. Kiểm liên quan cuối **43 đạt/0 lỗi/0 bỏ qua**, 30,63 giây; XML `tmp/retention-final-contract-f3f850577dd84a348929c86246a126f8/results.xml`. Hai bổ sung sau b58cccd chưa được tính qua CI #146; cần CI đúng mã.

### 16/10 — hàng đợi tiến độ và bảo vệ nội dung con mới

- Thêm `CleanupJob` và nâng cấp cộng thêm SQLite 9/PostgreSQL 8. Sổ chứa bản duyệt cố định, ID/dấu nội dung, các mục đã xử lý/còn lại, quyền xử lý có hạn và trạng thái; không sao chép thân thư/tài liệu/ghi chú. Chỉ có mã nội bộ, chưa có đường API/công cụ mô hình/thao tác xóa thật.
- Một bản duyệt nhận đúng một lần; chỉ một tác vụ đang mở cho mỗi tài khoản, kể cả hai yêu cầu cạnh tranh. Bản mới quá hạn/tương lai bị chặn; việc nhận lại phản hồi cho bản cũ trả đúng ID, không chạy lại. Mã lỗi dùng danh sách cố định, không ghi nội dung lỗi nhà cung cấp.
- Mỗi lần ghi tiến độ kiểm lại mã quyền/lần xử lý còn hiệu lực bằng `UPDATE` có điều kiện. Đã tái hiện tình huống SQLite đọc trước rồi bị người xử lý mới nhận lại; người cũ không thể ghi mốc hoàn tất dù dùng thời gian cũ. Khóa đọc đơn thuần không đủ nên không dùng cập nhật chỉ theo ID.
- Kiểm tiến độ bảo toàn đúng các tham chiếu đã duyệt; không thiếu, thêm, lặp hoặc vừa còn lại vừa hoàn tất. Hỏng dấu nội dung/quyền sở hữu/bản duyệt/JSON thì dừng riêng tác vụ, không chặn mãi tài khoản khác. Chỉ báo thành công sau mốc SQL và hết mục còn lại; đây là hợp đồng tiến độ, **không chứng minh đối tượng vật lý đã được xóa**. Bộ chạy sau này phải xác minh đối tượng không còn trước khi ghi nhận.
- Mốc SQL đã kiểm commit/rollback cùng thao tác xóa ghi chú **giả lập trong DB tạm**; không liên quan ghi chú của người dùng thật. Mở lại kết nối DB giữ tiến độ, chỉ tiếp tục mục còn lại; hết ba lần thử chuyển sang cần xử lý, thử lại giữ phạm vi và tiến độ. Hủy chỉ được trước tác động không thể hoàn lại; người khác không đọc/thử lại/hủy được.
- Rà FK thật phát hiện nhận xét/bản nháp có thể mới hơn câu trả lời cha, yêu cầu hàng đợi mới hơn hội thoại. Kiểm kê nay lấy tuổi nội dung liên quan để bảo vệ cha, đồng thời lọc chủ sở hữu ở cả hai phía liên kết. Không sửa câu trả lời AI hoặc gọi lại Gemini để kiểm điểm này.
- Kiểm hàng đợi/di trú/ORM ban đầu: **36 đạt**, 19,77 giây. Sau bổ sung bảo vệ con, phiên tự hết hiệu lực và kiểm lại đầy đủ các phần lưu giữ: **89 đạt/0 lỗi/0 bỏ qua**, 35,55 giây. Các nhóm chồng lặp, không cộng số hoặc coi là điểm sản phẩm. Ruff toàn backend và diff check đạt. Đã thêm một ca PostgreSQL cạnh tranh/nhận lại/cách ly/chỉ mục riêng, **chưa tính đạt trước CI mới**.
- XML gộp giữ riêng tại `tmp/retention-cleanup-batch-02a54d89a80f4ec999ad731a5a6972ce/results.xml`, không đưa DB/XML thô lên GitHub. Quét bí mật **732 tệp Git-visible** đạt; không coi phép quét là chứng nhận dữ liệu đã ẩn danh.
- Không dùng Gemini, tạo chỉ mục hoặc ghi Google; không chạy DDL/DML trên Supabase thật, không đổi gói/bí mật/Render/main. Nhánh vẫn `work/data-retention-20261015`, không khớp điều kiện tự xuất ảnh/triển khai.

Giới hạn hiện hành: chưa có bộ thực thi xuyên kho, điều phối chặn ghi đồng thời, xác minh tệp vật lý, API và hộp thoại xác nhận. Không lấy hàng đợi hoặc kiểm DB tạm thay bằng chứng xóa trên sản phẩm; không xóa tự động chỉ vì đã đủ 30 ngày.

### CI #144 đã hoàn tất

[Lần kiểm 38767074632](https://github.com/dbp3206-source/DriveAgent/actions/runs/38767074632), mã **7ab69ba07f9fcd101a97305e41387910a694be69**. `postgres-state` (job116532963639): **16 đạt**, 4,91 giây. `verify` (job116533368844): máy chủ **1.682 đạt/17 bỏ qua**, 94,33 giây, độ phủ **88,24%**; giao diện **222 đạt/0 lỗi/0 bỏ qua**. Kiểm ngoại tuyến/toàn vẹn bộ chuẩn, dựng/khởi động gói và PDF tiếng Việt thành công. Xuất ảnh GHCR và triển khai Render đều `skipped`. Bằng chứng mới này đóng kiểm phần nối ngày mẫu/kiểm kê tại mã 7ab69ba, không chứng minh các thay đổi sau đó đã qua CI hoặc đã có bộ xóa.

### Nối kho ADK và bảo vệ nguồn vừa cập nhật — sau mã 7ab69ba

- Đọc mã thật `pdf_jobs.py` xác nhận quá trình trích xuất lại có thể sửa `LocalSource.content` nhưng giữ ngày tạo. Kiểm kê nay lấy thêm ngày công bố của tác vụ liên quan, đúng chủ sở hữu và cùng giao dịch xuất bản; không chọn nội dung vừa cập nhật chỉ vì nguồn được tạo từ lâu. Không sửa bộ đọc PDF/OCR hoặc gọi AI. Ca thử có tham chiếu sai tài khoản không được làm đổi tuổi nguồn của người khác.
- `retention_framework.py` kiểm kê ADK theo đúng namespace/local store có marker và đủ cấu trúc, chỉ đọc bản ghi thuộc người dùng. Không nhận namespace tùy ý, không diễn giải DB thiếu bảng là kho rỗng, không giải tuần tự payload nhị phân. Trạng thái dùng chung có nội dung hoặc app không nhận diện được sẽ chặn, không xóa rộng hoặc lặng lẽ bỏ qua. **Chưa bao phủ tệp checkpoint LangGraph, chưa có thao tác xóa**.
- Đã kiểm bằng `DatabaseSessionService`/Event ADK thật tại máy với dữ liệu giả lập: đọc phiên/sự kiện/trạng thái người dùng, giữ nguyên nội dung sau kiểm kê, cách ly chủ sở hữu, chặn trạng thái dùng chung, marker/bảng thiếu, namespace/app không hỗ trợ. Thêm ca PostgreSQL cho cả private và public cũ; chưa tính đạt trước CI tương ứng.
- Kiểm nguồn cập nhật lại lần đầu có một lỗi kỳ vọng timezone trong kiểm thử: SQLite trả ngày UTC dạng không gắn múi giờ. Đã sửa phép so bằng `utc(...)`, không đổi kỳ vọng ngày hoặc mã nguồn để che lỗi. Kiểm gộp sau sửa **50 đạt**, 9,13 giây; XML `tmp/retention-publication-69724ace469d49ebac5e192ce42f3a60/results.xml`.
- Kiểm gộp cuối policy/clocks/ORM/ADK/Skills: **57 đạt/0 lỗi/0 bỏ qua**, 12,29 giây; XML `tmp/retention-batch-fadb9fe866034fb29f30459e1dc1a81b/results.xml`. Ruff backend và diff check đạt; quét 730 tệp Git-visible đạt. Những nhóm này chồng lặp, không cộng thành điểm hay số ca sản phẩm.
- Theo skill `supabase:supabase`, đã dùng kết nối Supabase chỉ đọc `information_schema.columns` và số tổng hợp `app_states` của project đang chạy. Cả public/private dùng JSONB và timestamp UTC không gắn múi giờ, khớp bộ lưu ADK hiện hành. Mỗi namespace có một bản ghi app, **0 trạng thái dùng chung không rỗng** tại thời điểm đọc. Không đọc nội dung phiên/thư/tài liệu/khóa, không DDL/DML, không suy ra toàn bộ ngữ cảnh riêng là rỗng hoặc đã bị xóa. Đây là kiểm điều kiện nguồn thật, không chứng nhận bảo mật hay phép cho xóa dữ liệu.

### Phần nối kiểm kê tại máy sau CI #143

- `retention_inventory.py` đọc đủ 15 bảng nội dung của ứng dụng, gắn chủ sở hữu ở từng truy vấn, chỉ trả ID/dấu nội dung/ngày/trạng thái. Kiểm phân loại không bỏ sót bảng ORM mới; không đọc bảng tài khoản hoặc khóa. Đọc bằng luồng nhỏ, không cắt theo giới hạn UI; thử dữ liệu ở mọi bảng và 205 nguồn thêm. Hội thoại có lượt mới không được chọn theo ngày tạo cũ. Tác vụ đang chạy khiến kiểm điều kiện ứng dụng chưa sẵn sàng; không tự nâng các kiểm kho khác thành đúng.
- Adapter Skills có bảng phụ `skill_content_clocks`, không thêm cột vào bảng tám cột cũ vì bản local cũ dùng `INSERT` theo vị trí. Hai cách lưu giữ ngày khi đọc/cất/lưu nguyên nội dung, đổi ngày khi sửa; phát hiện nội dung do bản cũ sửa mà chưa cập nhật bảng phụ, dùng ngày cập nhật đã biết theo hướng thận trọng. Không tự ghi sửa bảng ngày trong một lần đọc kiểm kê. Khóa thuộc tài khoản khác/ngày hỏng chặn thao tác, không biến thành phép xóa.
- Kiểm đầu Skills: 14 đạt/0 lỗi/0 bỏ qua, 1,62 giây. Kiểm gộp đầu sau thêm kiểm kê: 50 đạt, 7,97 giây. Sau thêm ca mọi bảng/vượt 200 mục: **51 đạt/0 lỗi/0 bỏ qua**, 8,58 giây. Có lỗi định dạng import/dòng dài trong lượt viết kiểm đã sửa; Ruff toàn backend và `git diff --check` sau sửa đạt. Các nhóm chồng lặp không cộng số.
- XML sau cùng ở `tmp/retention-inventory-f0ff3aaa9926497a8ad676aa04aabbd7/results.xml`, chỉ dữ liệu giả lập và không gọi mô hình/dịch vụ ngoài. Quét bí mật 728 tệp Git-visible đạt trước khi ghi cập nhật hồ sơ này.
- Thêm hai ca PostgreSQL riêng về ngày mẫu/bảng phụ và kiểm kê hội thoại có dữ liệu mới. Chưa ghi hai ca này đạt trước khi CI tương ứng chạy xong. CI #143 chỉ bao phủ mã f46d3d0, không được dùng thay kết quả của những chỉnh sửa mới.

Lõi không chứng minh đã xác nhận người dùng, chống phát lại trong sổ bền vững, khóa thao tác đồng thời hoặc xóa mọi bản dẫn xuất. Bộ thực thi phải tự kiểm nguồn yêu cầu, nhận đúng một lần, đọc lại dưới khóa trước tác động đầu tiên và tiếp tục an toàn sau lỗi; không được lấy `validate()` làm phép xóa đã được duyệt.

Còn nối kiểm kê/bộ thực thi với các kho khác trong `docs/DATA-RETENTION-20261015.md`, kiểm lỗi và tiếp tục, hộp thoại theo giao diện hiện có, kiểm thật bằng dữ liệu giả lập và triển khai có kiểm soát. Phần ngày mẫu/ORM/ADK đã có mã kiểm kê, chưa có bộ thực thi xóa hoặc API duyệt. ADK tái dựng từ lịch sử chuẩn; LangGraph hiện còn dựa vào checkpoint riêng và chỉ thêm lượt mới. Việc xóa phải xử lý checkpoint và giữ các lượt mới, không lấy xóa Message làm bằng chứng đã quên toàn bộ. Chưa đổi luồng orchestrator trong các lượt này. Chưa gộp staging/main, chưa tạo thẻ hoặc đổi ảnh Render chỉ để trình diễn một lớp chưa hoàn chỉnh. Nhánh công việc riêng không khớp điều kiện xuất ảnh/triển khai của CI; không thay workflow hoặc bí mật.
