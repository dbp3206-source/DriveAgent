# Dọn nội dung đã duyệt — kiểm bộ xóa SQL và đối chiếu tệp

Ngày 16/10/2026. Thuộc gói 14 đã chốt, không thêm gói nghiệm thu. **Chưa triển khai lên URL, chưa xóa dữ liệu thật, chưa đóng toàn bộ cơ chế lưu giữ hoặc Production.** Mã phát triển tiếp trên `work/data-retention-20261015`, sau CI #147; không dùng CI cũ làm bằng chứng cho mã mới.

## CI #148 đã hoàn tất

[Lần kiểm 38846606316](https://github.com/dbp3206-source/DriveAgent/actions/runs/38846606316), đúng mã **620c2d7d3f5e20d007338eb90c63568eefcab226**. Đã đọc trạng thái các bước và nhật ký qua kết nối GitHub:

- PostgreSQL riêng `veridra_ci`, job `116798460125`: **19 đạt/0 bỏ qua**, 6,52 giây. Ca mới xóa nội dung ứng dụng/state/ADK private và public cũ, vector SQL và mốc hàng đợi trong cùng một giao dịch; rollback giữ đủ, commit bỏ đúng dữ liệu cũ, còn ghi chú mới/tài khoản khác và chống phát lại Google.
- Verify `116798710529`: máy chủ **1.769 đạt/20 bỏ qua**, 74,08 giây; độ phủ **88,44%**. Giao diện **222 đạt/0 lỗi/0 bỏ qua**. SQL ứng dụng 9, ADK 9 và state 14 ca xuất hiện trong tổng máy chủ. Kho tệp **41 ca đều chạy đạt trên Linux**, bao phủ năm ca file-link bị bỏ qua tại Windows; không cộng các nhóm con vào tổng hoặc đổi số bỏ qua của tổng.
- Quét bí mật 738 tệp, kiểm ngoại tuyến/toàn vẹn bộ chuẩn, dựng giao diện, dựng/khởi động gói và PDF tiếng Việt đều thành công. **Publish the verified image** và **Deploy the exact verified image to Render** đều `skipped`. Không xuất ảnh GHCR/triển khai hoặc áp dụng schema lên Supabase thật.

CI này đóng kiểm các bộ xóa và hồi quy đã viết đúng mã; **không đóng bộ điều phối/API/hộp thoại, kiểm tệp Supabase thật, Qdrant/LangGraph hoặc toàn bộ gói 14**. Bản đang chạy giữ mã13938d1/ảnh0169c264…377c1712 theo lần Live gần nhất. Những dòng “cần CI” phía dưới là tiến độ lúc chạy tại máy trước CI #148, không phải trạng thái mới nhất.

## Phần đã thực hiện

- `retention_application.py`: xóa chính xác các bản ghi được duyệt ở 15 bảng nội dung, đúng chủ sở hữu và dấu nội dung/ngày; giữ User, ProviderCredential, hàng đợi dọn, hạn mức và quyền. Kiểm quan hệ trước tác động đầu tiên: không để xóa dây chuyền sang nội dung con chưa được duyệt, nội dung mới hoặc một tham chiếu sai tài khoản. Trả tham chiếu PDF/vector cần xử lý tiếp trước khi bỏ hàng SQL, không gọi Google hoặc mô hình.
- `retention_state.py`: kiểm kê và xóa mẫu/bản kiểm đã chọn; xóa nội dung `spec/result/error_code` của sổ thao tác nhưng giữ ID, mã yêu cầu, dấu chống lặp, trạng thái và đích đã tạo. Bản nháp chưa thực hiện chuyển sang hết hiệu lực, không thể chạy lại sau khi đã dọn. Không xóa sổ rồi mở lại quyền ghi Google. Các hàm không tự commit hoặc tự xác nhận người dùng.
- `state_content_clocks.py`: bảng phụ chỉ giữ ID/chủ sở hữu/dấu nội dung/ngày; không sao chép thân tài liệu. Nội dung thay đổi và ngày được ghi cùng giao dịch của cả hai kiểu lưu. Xem/cất/đổi trạng thái mà không đổi nội dung không gia hạn. Dữ liệu cũ được lấy ngày **quan sát kiểm chứng đầu tiên**, không bịa ngày sửa từ quá khứ; khởi động có đối chiếu được thay đổi do bản cũ, lần đọc kiểm kê không tự sửa ngày. Ngày hoặc chủ sở hữu không khớp thì chặn. Giữ nguyên cấu trúc bảng payload cũ.
- Bỏ xóa ngầm kết quả kiểm cũ khi người khác tạo bản kiểm mới; nội dung chuyển sang đường dọn có duyệt. Không bỏ cơ chế hết hạn dấu vết/bản sao kỹ thuật đã công bố.
- `retention_framework.py`: xóa đúng phiên/sự kiện/trạng thái ADK cũ trong namespace xác định, kiểm lại dấu nội dung và quan hệ phiên–sự kiện; không xóa `app_states`, marker hoặc schema. Nếu còn hội thoại mới cần hàng trạng thái người dùng, chỉ làm rỗng phần nội dung đã duyệt và giữ cấu trúc SDK yêu cầu. SDK thật vẫn đọc/ghi tiếp được hội thoại mới. Trạng thái dùng chung có nội dung vẫn chặn, không gán cho một người để xóa rộng.
- `object_storage.py`: thêm đối chiếu tồn tại và xóa–đọc lại cho PDF. Local kiểm cả đường riêng/đường cũ, từ chối liên kết sang người khác. Supabase kiểm bucket riêng còn truy cập được rồi dùng đường tải có xác thực, chỉ yêu cầu một byte và không đọc thân PDF khi còn tệp. Chỉ nhận mã không có đối tượng theo định dạng cụ thể hiện hành/cũ; không coi mọi lỗi 404, mất bucket, mất quyền, chuyển hướng hoặc thông báo DELETE thành công là đã xóa. Lỗi được trả bằng mã cố định, không đưa nội dung riêng vào lỗi.

Các bộ xóa mới **chưa đăng ký thành API/công cụ mô hình hoặc worker trong sản phẩm**. Chúng yêu cầu bộ điều phối xác nhận người dùng, kiểm đầy đủ các kho, chặn ghi đồng thời theo tài khoản và lưu tiến độ đúng giao dịch. Không lấy việc gọi được một hàm Python làm phép xóa đã được duyệt.

## Bằng chứng tại máy

| Nhóm | Kết quả | Phạm vi chứng minh |
|---|---|---|
| Hồi quy sổ thao tác/bản kiểm/mẫu | 18 đạt, 0 lỗi, 3,48 giây | Không làm hỏng đường duyệt/nhận một lần và lưu dữ liệu cũ khi thêm đồng hồ |
| SQL ứng dụng + native/relational state | 23 đạt, 0 lỗi, 15,12 giây | FK bật thật; xóa 15 loại bản ghi cũ, giữ nội dung mới/tài khoản khác/khóa; rollback dữ liệu và mốc SQL cùng nhau; giữ chống ghi lại Google |
| ADK sau sửa mẫu kiểm | 9 đạt, 0 lỗi, 9,06 giây | SDK thật, xóa/rollback/quan hệ thiếu/khác người/thay nội dung/trạng thái chung và tiếp tục hội thoại mới |
| Kiểm gộp cuối | **171 đạt, 5 bỏ qua, 0 lỗi**, 66,44 giây | Bao gồm các nhóm trên, bộ xác nhận/hàng đợi/tuổi/Skills/kho tệp và hồi quy hành động ngoài/bản lưu; không cộng lặp số ca |

Năm bỏ qua là ca liên kết tệp không khả dụng trên Windows, không tính đạt; sau đó đã chạy đạt trên CI Linux #148. XML gộp: `tmp/retention-purge-regression-f2206c499531431a8d0485022ab9040c/results.xml`. DB/XML thô giữ trong vùng bị Git bỏ qua, không đưa dữ liệu chạy lên GitHub. Ruff toàn backend và `git diff --check` đạt; quét bí mật 737 tệp Git-visible đạt trước khi thêm hồ sơ này, 738 tệp đạt sau khi thêm và trong CI.

Đã thêm ca PostgreSQL riêng: SQL nội dung, state, ADK private/public cũ, vector sinh từ SQL và mốc hàng đợi trong **cùng một giao dịch**; kiểm rollback rồi commit, tìm vector chỉ còn ghi chú mới, không mở lại sổ ghi Google. **Chưa tính ca này đạt trước CI đúng mã.** Kiểm tại máy dùng SQLite không được đổi tên thành kiểm PostgreSQL/Supabase.

## Đối chiếu nhà cung cấp thật — chỉ đọc

Dùng skill `supabase:supabase` ở `C:/Users/Bao Phuc/.codex/plugins/cache/openai-curated-remote/supabase/1.0.0/skills/supabase/SKILL.md`, phiên bản 0.1.2. Thực thi kết nối `search_docs` và `execute_sql`, không chỉ đọc skill rồi tự nhận đã dùng.

- Đã đọc [changelog](https://supabase.com/changelog) và [thông báo TLS](https://supabase.com/changelog/cbc-tls-ciphers-deprecated) hiện hành. Thay đổi tháng 11 loại một số cipher cũ; không đổi API xóa, không tắt kiểm chứng TLS hoặc nâng thư viện vì thông báo này.
- Đối chiếu [Storage schema](https://supabase.com/docs/guides/storage/schema/design) và [mã lỗi Storage](https://supabase.com/docs/guides/storage/debugging/error-codes): metadata SQL không thay việc xóa qua Storage API; phải phân biệt lỗi đối tượng, bucket, quyền và định dạng lỗi cũ/mới.
- Truy vấn `information_schema.columns` qua kết nối Supabase trên project đang chạy chỉ lấy tên/kiểu của năm cột metadata `storage.objects`. Không lấy tên tệp, nội dung, khóa hoặc dữ liệu người dùng, không DDL/DML.
- Thử đọc đối tượng ngẫu nhiên không tồn tại bằng cấu hình local **không chạy** vì không có cấu hình khớp đúng project. Chương trình dừng trước HTTP, không in URL/khóa hoặc tự chọn project khác. Vì vậy kiểm Supabase tệp ở lượt này vẫn là kiểm phản hồi giả lập, **không phải xóa/đọc lại tệp trên cloud**.

Lần tải changelog đầu trong sandbox bị chặn socket; sau quyền mạng phù hợp đã đọc được trang chính thức. Một lệnh hồi quy đầu chỉ tới tệp kiểm không tồn tại `test_relational_state.py`, chạy 0 ca; đã dùng `rg --files` xác định đúng các tệp rồi chạy đạt. Lần kiểm ADK đầu có một lỗi do mẫu đã được giả lập ngày cũ nhưng vẫn dùng dấu phiên SDK cũ: đã tải lại phiên trước append, giữ nguyên kiểm chống phiên cũ của SDK; không nới bảo vệ hoặc đổi kỳ vọng để che lỗi sản phẩm. Các lỗi định dạng khi viết mã đã sửa, Ruff cuối đạt.

## Giới hạn và việc nối tiếp — vẫn đúng gói 14

1. Bộ điều phối đầy đủ: xem trước theo quan hệ/batch 200; giữ phạm vi cố định, xét đủ dữ liệu phụ/đối tượng mồ côi, lưu tiến độ cho các kho native tách DB; chặn tác vụ ghi lại dữ liệu đã dọn. Các hàm SQL ở đây không tự đảm bảo điều đó.
2. Đặt lại bản ngữ cảnh dẫn xuất mới hơn khi nó có thể chứa nội dung cũ; nối LangGraph/local và Qdrant với xác nhận xóa thật. Xóa riêng các hàng ADK đã cũ không chứng minh mọi bản ngữ cảnh mới hơn đã quên.
3. API/hộp thoại theo giao diện hiện có, “Để sau” không xóa; kiểm trình duyệt và một mẫu cloud dùng dữ liệu giả lập, sau quyền xác nhận tại thao tác xóa. Làm mới bản đang giữ trên trình duyệt sau thành công.

Chưa gọi Gemini/tạo chỉ mục/ghi Google, chưa đổi hạn mức/gói/bí mật, chưa áp dụng bảng phụ hoặc xóa lên Supabase thật. Chưa gộp main/tag, chưa triển khai Render. T09 và diễn tập khôi phục vẫn được miễn theo chủ sở hữu, không tính đạt. Không dùng kết quả này thay toàn bộ nghiệm thu hoặc kết luận xóa vật lý pháp chứng/bản sao do bên thứ ba quản lý.
