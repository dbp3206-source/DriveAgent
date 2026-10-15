# Đặt tên và phục hồi bản duyệt tài liệu — 14–15/10/2026

Thuộc gói07/T07 đã chốt; không thêm hành trình hay lượt Gemini. Đây là kiểm bản sửa tại máy, **chưa phải nghiệm thu Render/toàn sản phẩm**.

## Nguyên nhân và cách sửa

ChatPage tự lấy dòng đầu câu trả lời làm tên Doc, nên lời dẫn “Bản xem trước…” thành tên tệp. Sửa đúng tầng: người dùng được xem/sửa tên trước khi khóa; tên một dòng,1–200ký tự, giữ tiếng Việt. Không đổi tên sau duyệt âm thầm.

Reload phục hồi metadata theo **tài khoản + mã yêu cầu**. API chỉ trả mã thao tác/digest/trạng thái/tên của docs_create, không trả thân hoặc dữ liệu người khác. SQLite và SQLAlchemy dùng bind parameters và khóa duy nhất hiện có; không migration/mở Data API/đổi RLS. Bản đã chờ/chạy/chưa rõ/thành công không tự đổi mã yêu cầu. Bản hết hạn giữ tên khi chuẩn bị lại; vẫn cần duyệt. Cơ chế thực hiện/đọc lại Google không thay đổi.

## Nguồn, công cụ và đầu ra

Nguồn: ChatPage, DocumentExportTitleDialog, documentTitle, documentPreviewRecovery, API documents, hai OperationStore và tests. Brief/outline ở design-work. Đầu ra là mã React/TypeScript/backend thật, chỉnh sửa được; không giao ảnh thay ứng dụng. Fluent/token hiện có là hướng thiết kế duy nhất, không thêm dependency/asset.

Đã đọc hướng dẫn Supabase/Postgres cho truy vấn có chủ sở hữu, gọi search_docs và đối chiếu changelog HTML sau khi changelog.md bị từ chối content-type. Thay đổi cipher HTTP TLS không áp dụng cho truy vấn Postgres này; không đổi cấu hình. Plugin Management tìm Render không trả chi tiết kết nối dùng được; không tuyên bố đã cài.

Chrome DevTools MCP chạy localhost5175/FastAPI8003 trong context riêng. Helper `run_local_ui.py --doc-preview-check` dùng SQLite dưới tmp và danh tính demo, không có khóa Gemini/OAuth, chặn host ngoài loopback. Scope fixture không phải quyền Google thật. @oai/sky chỉ liệt kê ứng dụng; không điều khiển cửa sổ Codex. Không đăng nhập Google/Render trên Chrome.

## Kết quả

| Bộ kiểm | Kết quả | Giới hạn |
|---|---|---|
| Backend liên quan |34/34,11.16s,session20262|Hai kho,HTTP/owner/auth/key sai/không tồn tại,không trả thân,duyệt/chống trùng|
| Frontend toàn bộ |219/219,0skip,10.398s,session37189|Không thay chất lượng AI|
| Frontend liên quan |23/23,2.354s|Handler thật lấy bằng AST với API giả; đã nằm trong tổng219|
| ESLint/TypeScript/Vite |Đạt,build35.59s,session48109|4496modules; cảnh báo thời gian plugin, không lỗi|
| Ruff |Đạt với backend/pyproject.toml|Gồm helper QA|

Đã thêm assertion PostgreSQL thật vào CI hiện có; chưa lấy SQLite thay kết quả PostgreSQL.

Kiểm trình duyệt thật:

1. Mở câu trả lời giả lập đã có4.0. Xuất chỉ mở hộp tên. Ctrl+A/Backspace làm nút Chuẩn bị bị khóa. Nhập tên Việt rồi Hủy:0dialog,rootHidden=null,nút xuất dùng được.
2. Chuẩn bị tên “Đề xuất thử cổng nội bộ — dữ liệu giả lập”. Hiện đúng tên cùng nút duyệt riêng; **không bấm duyệt**.
3. Reload rồi mở xuất: đúng tên cũ, không mở hộp tên mới. SQLite chế độro xác nhận chỉ1 docs_create `b4110f09-f304-4a93-970d-10d881a7270e`,pending,resource_id=null. Không Google Doc mới.
4. Một câu tính local xác định7.0 dùng mở hộp ở kích thước khác; không mô hình, không chuẩn bị bản thứ hai.
5. Desktop1920×852. Emulate390×844 xác nhận innerWidth390,scrollWidth390,hộp trái0/phải390.4,trên264.6/dưới579.4;0.4px do làm tròn,không tràn tài liệu. Light820×900:scrollWidth810,hộp104.8→704.8,306.4→593.6. Có focus rõ, thao tác bàn phím; chưa emulation giảm chuyển động hệ điều hành.
6. Console error cuối không có. Hai GET ERR_ABORTED trong reload/StrictMode được theo sau bởi200; không tuyên bố mọi request lịch sử thành công.

Ảnh gốc: `screenshots/title-selected-20261015.jpg`, `preview-recovered-20261015.jpg`, `mobile-title-390-20261015.jpg`, `light-title-820-20261015.jpg`. Ảnh14/10 giữ lịch sử. Chỉ dữ liệu giả lập.

## Lỗi kiểm/công cụ đã xử lý

- Auth test đầu thiếu SessionMiddleware:31đạt/1lỗi; thêm middleware kiểm, không bỏ xác thực. Sau thêm HTTP owner cases:34/34.
- Ruff đầu3dòng quá100ký tự đã ngắt; lần dùng nhầm config gốc cho helper báo RUF100/I001, chạy config backend đúng phạm vi đạt.
- fill_form giá trị rỗng chưa cập nhật React; bàn phím thật xác nhận nút bị khóa. Không sửa app để né lỗi công cụ.
- Wait “GÓC LÀM VIỆC” timeout10000ms; DOM/snapshot sau đó chứng minh Hủy hoàn tất. Không coi timeout quan sát là lỗi server.
- Resize390 thực ra502×732; dùng emulate và đo đúng390, không tính ảnh502 là390.
- Auto-review chặn chọn chat và mở xuất vì có nút Xóa lồng/nhãn giống ghi ngoài. Đọc DOM/source/fixture chứng minh chỉ chọn chat giả lập và mở tên localhost rồi mới được phép. Không bấm Xóa/duyệt hoặc thực hiện ngầm.
- Screenshot filePath bị từ chối “not within any configured workspace roots”; lưu nguyên JPEG inline bằng node_repl. Chuỗi đầu vượt64000byte bị từ chối, tách phần48000base64; không chỉnh ảnh. Get-CimInstance bị Access denied, không nâng quyền né.

## Điểm và giới hạn

Riêng thay đổi local: đúng19/20,cụ thể16/20,tổ chức13/15,chữ12/15,bố cục12/15,kỹ thuật12/15 = **84/100**,không phải điểm sản phẩm/AI.

Chưa triển khai bản đặt tên lên Render hoặc tạo thêm Doc thật. Trần13sinh+6chỉ mục/tổng19 đã18 vẫn giữ. Cách ly thật,khôi phục DB+tệp,điều kiện dữ liệu,các ca thiếu lượt và trình bày Agent cần góp ý vẫn chưa đóng. Chưa main/Production. Không thêm tài sản/giấy phép bên ngoài.
