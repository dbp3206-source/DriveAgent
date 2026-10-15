# Đặt tên và phục hồi bản duyệt tài liệu — 14–15/10/2026

Thuộc gói07/T07 đã chốt; không thêm hành trình hay lượt Gemini. Kiểm tại máy và **kiểm phần đặt tên/phục hồi trên Render đã hoàn tất**; không phải nghiệm thu toàn sản phẩm. Phần local/hạn chế theo thời điểm được giữ dưới đây; cập nhật cloud ở cuối.

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

Đã thêm assertion PostgreSQL thật vào CI hiện có. Ngày15/10 API GitHub xác nhận CI#140/run38694316034 đúng commit ed3fa6a38b093d7aeda517df03c88cbd16880cd7 completed/success: postgres-state116287209476 và verify116287414181 đều thành công. Không lấy SQLite thay PostgreSQL hoặc suy số ca CI từ số local. Registry HTTP200 xác nhận tag full commit và digest7727c538cbcb97700f7d922fddb4aea56e0839d9edaf85754dafda771cacb0bd. Bước tự triển khai Render skipped; chưa coi CI đạt là bản đã lên URL.

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

Ở thời điểm kết thúc kiểm local, chưa triển khai hoặc tạo thêm Doc thật. Sau cập nhật cloud bên dưới, trần13sinh+6chỉ mục/tổng19 đã18 vẫn giữ. Cách ly thật,khôi phục DB+tệp,điều kiện dữ liệu,các ca thiếu lượt và trình bày Agent cần góp ý vẫn chưa đóng. Chưa main/Production. Không thêm tài sản/giấy phép bên ngoài. Không lấy điểm84local làm điểm toàn sản phẩm.

## Kiểm Render và URL thật — 15/10, sau 19:49 GMT+7

Dùng `mcp__cua_repl.js` với tab thanh bên đã đăng nhập; không sao chép cookie/khóa, không đăng nhập Chrome khác. Cập nhật duy nhất nguồn ảnh của dịch vụ hiện có sang digest7727c538cbcb97700f7d922fddb4aea56e0839d9edaf85754dafda771cacb0bd. Render `dep-db8cmkjncjis73fe9m2g` báo Deploy succeeded|Live,1m50s,nhật kýLive19:49:09GMT+7. Bucket Supabase HTTP200 và server startup complete trong nhật ký; không thay bằng bằng chứng khôi phục. Không đổi Environment/gói/quyền hoặc tạo dịch vụ mới.

Trên sản phẩm thật, dùng đáp án tính xác định4.0 có từ trước:
1. Xuất mở hộp **Đặt tên Google Doc**. Bàn phím xóa tên làm khóa nút chuẩn bị.
2. Điền **Kiểm đặt tên - dữ liệu giả lập 15-10-2026**, Hủy bằng nút ngữ nghĩa:0dialog,rootHidden=null; mở lại được.
3. Điền lại cùng tên, bấm chuẩn bị **một lần**. Hiện đúng tên,bản nội dung đã khóa,nút xác nhận riêng. Không bấm xác nhận,không tạo Google Doc mới.
4. Kiểm trạng thái chỉ đọc; tải lại trang rồi bấm xuất ở cùng đáp án. Phục hồi đúng tên/bản chờ duyệt,0hộp tên mới. Bản xem trước để chờ duyệt/hết hạn, không tự xóa.
5. Tập100sự kiện Audit đã tải chứa một docs_prepare mới ngày15/10 trước/sau phục hồi:fa78c383,0.63s,thành công; không có docs_execute ngày15/10 trong tập này. Đây là đối chiếu nhật ký,không giả là truy vấn đếm mọi hàng DB. Không có câu hỏi mới hoặc lượt Gemini/chỉ mục trong đợt; số16/16trênUI không đặt lại ngân sách đợt19.
6. DOM cuối566×676,scrollWidth556; console error cuối `[]`. Ảnh gốc Render, hộp tên, bản khóa và bản sau tải lại nằm trong screenshots với tiền tốrender-/cloud- và mãed3fa6a. Ảnh hộp tên chụp vùng640×328 từ API; không ghép/chỉnh nội dung. Ảnh sản phẩm chỉ có phép tính và tên giả lập,không chứa email/tài liệu riêng.

Giới hạn công cụ: Connect đầu hết giờ trước dispatch; đọc lại modal vẫn mở rồi mới bấm lại, sau đó chỉ theo dõi đúng deploy. Một click xuất hết giờ nhưng mở hộp thành công; quan sát trước khi làm tiếp. Click Hủy bằng AX không đóng,wait hidden cũng hết giờ; kiểm nút không disabled rồi click ngữ nghĩa Playwright đóng được và gỡ ARIA, không sửa mã để né lỗi điều khiển. Tab sản phẩm từng chuyển sang Nhật ký trong lúc kiểm; đọc lại URL trước thao tác,không lặp lệnh vào trang sai. Không coi các timeout này là bằng chứng lỗi sản phẩm. Không chụp/công khai bảng Audit có email.

Kết luận: đóng lỗi tên/phục hồi trên cùng bản đã triển khai. Chưa xác nhận phần T07 đổi nội dung/đích sau duyệt trên cloud, chưa tạo lại Doc thật sau bản sửa, chưa đóng những điều kiện Production khác. [Biên nhận phát hành](../../../docs/RELEASE-CANDIDATE-ed3fa6a.md).
