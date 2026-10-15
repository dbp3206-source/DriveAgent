# T07 — kiểm gộp chuỗi duyệt tại máy

Ngày 15/10/2026. Chỉ kiểm phần còn thiếu của T07 trong bộ mười ca đã khóa; không thêm tính năng hoặc sửa mã sản phẩm. Mã ứng dụng vẫn là 13938d1. Tệp bổ sung: `backend/tests/test_document_approval_flow.py`.

## Điều đã chạy

HTTP thật trong tiến trình ASGI → bộ nhận yêu cầu FastAPI → kiểm nguồn yêu cầu → `ToolRegistry` thật, gồm quyền/phạm vi Google → `docs_prepare/docs_execute` thật → sổ thao tác thật. Hai biến thể: SQLite trực tiếp và lớp lưu trữ quan hệ chạy trên SQLite riêng. Không gọi đây là PostgreSQL thật.

Google và danh tính đăng nhập được thay bằng dữ liệu giả lập. Kết quả `verified=true` từ bộ giả lập **không phải bằng chứng đọc lại Google**; bằng chứng một Google Doc thật đã có ở hồ sơ ngày 14/10 và không được chạy lại trong lượt này. Không đóng T09 bằng danh tính giả lập.

Chuỗi kiểm xác nhận:

1. Chuẩn bị bản A không ghi Google.
2. Chèn nội dung hoặc đích khác vào yêu cầu duyệt bị chặn (422); nguồn yêu cầu ngoài ứng dụng bị chặn (403).
3. Dùng lại mã yêu cầu A với nội dung B bị chặn và bản A trong sổ không đổi.
4. Bản B mới có mã thao tác/mã băm riêng. Dùng mã duyệt A cho B bị từ chối `approval_mismatch` trước khi ghi giả lập.
5. Người khác không dùng được thao tác của chủ sở hữu; đây là kiểm lớp ứng dụng với danh tính giả lập, không phải hai tài khoản Google thật.
6. Chỉ khi duyệt đúng B mới gửi đúng tên/nội dung B tới bộ ghi giả lập. Gửi lại không ghi lần thứ hai; đọc trạng thái trả `succeeded`.

## Kết quả và lệnh thật

Ruff: đạt. Chạy tệp mới cùng `test_operations.py`, `test_document_tool_execution.py`, `test_document_preview_lookup.py`: **22 đạt, 0 lỗi, 0 bỏ qua**, pytest 5,46 giây; XML ghi 5,415 giây. Trong đó hai ca mới là hai biến thể của cùng chuỗi T07, không phải 22 lần kiểm sản phẩm qua trình duyệt.

Tiến trình thử bỏ các biến môi trường DRIVE_AGENT/GEMINI/GOOGLE, tắt đọc `.env` trong Settings trước khi nạp pytest; dùng thư mục mới đã kiểm chưa tồn tại. Không dùng DB, khóa hoặc thư mục dữ liệu đang chạy. Không Google Doc thật, Gemini, tạo chỉ mục, triển khai hoặc thay cấu hình cloud.

Sau khi làm rõ fixture không có cấu hình OAuth bằng đường dẫn tệp chưa tồn tại, chạy lại cùng 22 ca: **22 đạt, 0 lỗi, 0 bỏ qua**, pytest 4,71 giây, XML 4,684 giây. XML cuối tại `tmp/approval-chain-f7b7c773e8c1496cb0565240cf5360a1/results.xml`. Ruff đạt. Kiểm toàn vẹn dữ liệu chuẩn vẫn đủ 10 ca/4 tệp; số trần 19 trong bộ dữ liệu là ngân sách lịch sử, không thay sổ thực thi hiện đã duyệt 26 và dùng 25. T09 giữ nguyên trong bộ chuẩn để truy nguyên, chỉ được miễn trong đợt theo quyết định chủ sở hữu.

Lệnh: `backend/.venv/Scripts/python.exe -m ruff check backend/tests/test_document_approval_flow.py`; tiến trình Python cô lập gọi `pytest.main` với bốn tệp trên, `--basetemp` và `--junitxml`. XML tại máy: `tmp/approval-chain-5b48c850f3f748558592d3c10b28f800/results.xml`, không đưa DB/XML thô lên Git. Số ca/lỗi/thời gian được đọc lại bằng PowerShell XML.

## Kết luận đúng phạm vi

### Xác nhận kiểm tự động trên GitHub

[CI #142](https://github.com/dbp3206-source/DriveAgent/actions/runs/38754753285) của mã `d90a507cb49618281d1ced432588373141df7186` đã thành công ở cả `postgres-state` và `verify`. Đọc trạng thái qua kết nối GitHub rồi đọc nhật ký job `116490434642`: tệp kiểm mới có hai ca đạt; toàn bộ máy chủ **1.633 đạt, 14 bỏ qua**, 86,62 giây, độ phủ **88,12%**; giao diện **222 đạt, 0 lỗi**. Không cộng các nhóm chồng lặp thành điểm chất lượng sản phẩm.

Ảnh dựng từ mã kiểm này là `sha256:69e31a35eb33d18885af27798d6d45db4df6215860ed54ad0cb4787067e2a908`. Bước triển khai tự động bị bỏ qua. Đối chiếu Git không có thay đổi trong `backend/app`, `frontend/src`, Dockerfile hoặc các tệp phụ thuộc/khóa từ mã đang chạy `13938d1`; chỉ bổ sung bộ kiểm và hồ sơ, nên không triển khai lại ứng dụng chỉ để đổi mã ảnh. Kết nối Render xác nhận lần `dep-db8dvrqj9qps73cj7d5g` vẫn Live với ảnh `0169c264…377c1712`. Không gọi ảnh mới là đã triển khai.

Lượt xác nhận này chỉ đọc Git/GitHub/Render và lưu bằng chứng; 0 Gemini, 0 tạo chỉ mục, 0 Google Doc, không đổi quyền/cấu hình hoặc gộp main. Các quyết định loại tài liệu và thời hạn lưu/xóa vẫn chờ chủ sở hữu; T08 chưa được chạy thêm.

Đạt kiểm nối chuỗi API/sổ thao tác cho đổi bản, duyệt đúng bản và chống ghi lặp tại máy. Không phát hiện lỗi cần sửa mã sản phẩm. Không thay bằng chứng xác thực thật, môi trường Google thật hoặc toàn bộ T07/T08. Trần đợt AI vẫn 25/26; phần dùng bổ sung 7/7 đã hết, không tự dùng thêm lượt tạo chỉ mục.
