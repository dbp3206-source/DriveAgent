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

Lõi không chứng minh đã xác nhận người dùng, chống phát lại trong sổ bền vững, khóa thao tác đồng thời hoặc xóa mọi bản dẫn xuất. Bộ thực thi phải tự kiểm nguồn yêu cầu, nhận đúng một lần, đọc lại dưới khóa trước tác động đầu tiên và tiếp tục an toàn sau lỗi; không được lấy `validate()` làm phép xóa đã được duyệt.

Còn nối kiểm kê/bộ thực thi với mọi kho trong `docs/DATA-RETENTION-20261015.md`, kiểm lỗi và tiếp tục, hộp thoại theo giao diện hiện có, kiểm thật bằng dữ liệu giả lập và triển khai có kiểm soát. Mẫu đã lưu riêng trong adapter Skills cũng cần ngày nội dung; chưa thay ở lượt nền tảng này. Chưa gộp staging/main, chưa tạo thẻ hoặc đổi ảnh Render chỉ để trình diễn một lớp chưa hoàn chỉnh. Nhánh công việc riêng không khớp điều kiện xuất ảnh/triển khai của CI; không thay workflow hoặc bí mật.
