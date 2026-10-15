# QA — giải thích trợ lý đã được duyệt, 15/10/2026

## Phạm vi và nguồn

Chủ sản phẩm xác nhận “cho phép quay lui và duyệt bản nháp”. Chỉ thực hiện vòng đổi phiên bản Render đã trình và bản giải thích bốn bước trong `docs/AGENT-EXPLANATION-DRAFT-20261015.md`. Không thêm tính năng, không thiết kế lại toàn bộ, không thay bộ nghiệm thu.

Nguồn: bản duyệt trên; `design-work/design-brief.md`, `content-outline.md`; `frontend/src/pages/HarnessPage.tsx`, `harnessPage.css`, `components/AppShell.tsx`; kế hoạch sản phẩm ngày13/10.

## Tuyến thực thi thật

- Thiết kế: hệ thống Veridra/Fluent sẵn có, không dùng thêm bộ chỉ đạo thẩm mỹ. Giữ PNG do người dùng cung cấp, nguyên kích thước1672×941, có chú thích số minh họa.
- Render: đã đọc hướng dẫn `render-deploy` và `render-docker` tại `C:/Users/Bao Phuc/.codex/plugins/cache/openai-curated-remote/app-6a624c56bfe081918f7544f7d58f6faf/1.0.1/skills/`. MCP Render không có trong danh sách công cụ; `render --version` trước đó báo không nhận lệnh. Dùng đúng luồng nguồn ảnh Dashboard được hướng dẫn, qua `mcp__cua_repl.js` trong thanh bên đã đăng nhập.
- Trình duyệt: `cua.rewriteDocumentation`, tài liệu local-web-development/viewport, AX, nút/bàn phím, DOM chỉ đọc, ảnh chụp nguyên bản. Không dùng Playwright độc lập hoặc sửa trạng thái ẩn của trang.
- Đầu ra chỉnh sửa được là mã React/CSS thật, không phải ảnh giao diện giả. Không tạo hình mới hoặc sử dụng tài sản bên thứ ba mới; Fluent/asset cũ giữ nguyên giấy phép hiện có.

## Vòng quay lui Render — đã hoàn tất

Dịch vụ duy nhất `srv-dav5v560tbcc73dpjlc0`, My Workspace, Free/Singapore. Hai ảnh không đổi migration/core/dependencies theo diff đã kiểm trước đó.

| Chặng | Ảnh | Lần triển khai | Kết quả |
|---|---|---|---|
| Quay về bản trước | `ac46a7a22d37ee3c059d3dff560b6d39ec6a6ec2ebb5ec78b7e8be83df13a143` | `dep-db8djto473hc739ddm4g`, bắt đầu20:49:43 GMT+7 | Deploy succeeded,1m51s; tải lại Bộ nhớ vẫn có3mục |
| Trở lại bản hiện tại | `7727c538cbcb97700f7d922fddb4aea56e0839d9edaf85754dafda771cacb0bd` | `dep-db8dlom89jmc73d4o4ig`, bắt đầu20:53:38 GMT+7 | Deploy succeeded/Live,1m51s; nhật kýLive20:55:33 |

Sau trở lại: Bộ nhớ tải lại vẫn3mục (1đang dùng,2đã cất), không có ghi chú IA-QA đã xóa. Không tìm theo ý nghĩa nên không phát sinh lượt tạo chỉ mục. `/api/health` trả `status:ok,database:true,object_storage:true`, pgvector; Google/Gemini không được thăm dò bằng phép này. Nhật ký khởi động có kho tệpHTTP200,HEAD/200 và địa chỉ0.0.0.0:10000. Không đổi Environment, quyền, bí mật, gói hoặc DB. Đây là đổi phiên bản ứng dụng thật, **không phải kiểm khôi phục DB/tệp** hoặc chứng minh toàn bộ dữ liệu không mất.

Ảnh nguyên bản trong `design-work/production-20261013/qa/screenshots/`:
`render-rollback-ac46a7a-live-20261015.jpg`, `render-return-7727c538-live-20261015.jpg`.

## Giao diện đã thực hiện

Bốn bước ngắn; một trong ba ví dụ được chọn; giữ ảnh cũ; phần kỹ thuật đóng và chưa dựng thành phần khi mở trang bình thường. Không gọi API số liệu cho phần kỹ thuật khi chưa mở; gói mã của trang vẫn chứa các thành phần cũ. Giữ các liên kết domain/step; khi người dùng mở liên kết đó, phần kỹ thuật tự mở. Sửa việc bỏ nhầm lần đổi hash sau `replaceState` để chuyển liên kết thật không bị giữ ví dụ cũ. Không thay hành vi mô hình hoặc duyệt Google.

## Kiểm đã chạy

- `npm run test:unit`:222đạt/0lỗi/0bỏ qua, gồm3hợp đồng nguồn mới. Các ca cũ có mô phỏng và kiểm cấu trúc, **không phải222lượt kiểm trình duyệt hoặc chất lượng AI**.
- ESLint, TypeScript và Vite chạy thật, build riêng `tmp/assistant-explanation-build-20261015`,4496modules,57,30giây ở lần dựng đầu. Cảnh báo outDir ngoài frontend không tự xóa là dự kiến; không dùng `--emptyOutDir`.
- Ứng dụng thật: backend cô lập8003, Vite5175. Cấu hình không có khóa/OAuth, chặn phân giải máy chủ ngoài; chỉ dùng trạng thái thử cục bộ. Không sử dụng script smoke có cookie tài khoản thật.
- Thanh bên:1440×1000 tối,820×900 sáng,390×844 sáng. DOM xác nhận4bước,1ví dụ,ảnh đã tải1672px,không tràn ngang. 390pxmột cột,820pxhai cột; ảnh chụp xem trực tiếp, không tràn chữ ở các khối mới.
- Bàn phím: Enter chọn ví dụ họp/hướng dẫn, mở/đóng phần kỹ thuật; đóng giữ focus và viềnsolid. Liên kết education bước3 → ArrowRight bước4 → liên kết ecommerce bước7 chọn đúng ô outcome. Không gửi yêu cầu chat.
- Consoleerror qua tab.dev.logs trả[] ở phiên kiểm cục bộ. Không ghi nhận lỗi tải ảnh; không có bộ ghi đầy đủ mọi yêu cầu mạng nên không tuyên bố kiểm hết mạng/hiệu năng. Phần mới không có animation/transition; DOM kiểm animation:none và0s. Không thêm hiệu ứng cần giả lập giảm chuyển động; giữ quy tắc giảm chuyển động cũ.

Ảnh: `screenshots/desktop-dark.jpg`, `tablet-light.jpg`, `mobile-light.jpg`. Ảnh là khung nhìn, không phải toàn bộ trang; nội dung kỹ thuật cũ không được chấm lại như một lần thiết kế mới.

## Điểm chất lượng của thay đổi giao diện

| Tiêu chí | Điểm |
|---|---:|
| Đúng nội dung |18/20|
| Phù hợp đối tượng |17/20|
| Cấu trúc thông tin |12/15|
| Chữ và khả năng đọc |14/15|
| Bố cục |13/15|
| Hoàn thiện kỹ thuật/kiểm chứng |12/15|
| Tổng |86/100|

Điểm là nhận xét thủ công cho phạm vi giao diện mới, không phải điểm benchmark toàn sản phẩm. Trừ điểm vì nội dung kỹ thuật cũ vẫn dài và chưa kiểm toàn bộ tổ hợp; không mở rộng sửa ngoài bản duyệt.

## Phát hành và kiểm URL thật — đã hoàn tất

Mã `13938d158b6f1df13df01186a31b541d85ff13c1` đã đẩy lên nhánhstaging và qua[CI#141](https://github.com/dbp3206-source/DriveAgent/actions/runs/38748183372). ConnectorGitHub đọc cả hai job thành công; nhật kýverify:1631đạt/14bỏ qua/92,91giây,độ phủ88,07%;frontend222đạt/0lỗi/0bỏ qua. Kiểm ngoại tuyến/bộ chuẩn/bí mật/lint/gói chạy/PDF thành công. Publish cho mã và kênhstaging cùng ảnh `sha256:0169c264a134bba62381d207785a3a7b4aaac611acdb1768b2e9208d377c1712`; bước tự triển khai skipped nên đã cập nhật nguồn đúng một lần quaDashboard.

Render `dep-db8dvrqj9qps73cj7d5g` đãLive. ConnectorRender vừa xuất hiện trong phiên, đã liệt kêMy Workspaceđúngid `tea-d9v8f5ugekts73f1uglg` (tên đã được chủ sở hữu xác nhận trước đó) và đọc deploy:created14:15:11.807UTC,started14:15:16.936,finished14:17:07.150.115,343giây từ tạo đến hoàn tất,110,214giây từ bắt đầu; không nhầm với thời gian gián đoạn người dùng. Ảnh khớpCI. Không gửi triggerlặp; MCPkhông có thao tác đổi nguồnảnh nên bước đó vẫn quaUI.

URL `/?verify=13938d1#/harness` đã mở bằng phiên quản trị trên thanh bên:4bước,1ví dụ,chi tiết chưa dựng mặc định,PNGtải thật1672px;Enterđổi ví dụ họp, mở/đóng kỹ thuật đúngaria-expanded và ôbankingbước1. Tải lại đường dẫn khôngquerydomain/step vẫn đóng ban đầu. Khung thực566×676,không tràn ngang,consoleerrors[]. Có yêu cầu override1440nhưngDOMởtabcloudvẫn566, nên **không tính đây là kiểm desktopcloud**; ba kích thước đã kiểm ở ứng dụng thật cục bộ. Ảnh `screenshots/cloud-13938d1-sidebar.jpg` là khung thanh bên thật, không chỉnh ảnh. Đã resetoverride. Endpointhealthsau phát hành:ok/DBtrue/storage true,khởi động14:16:59UTC;Google/Gemini not_probed. Không coi kiểm sức khỏe là một lượt mô hình thành công.

## Giới hạn còn lại

Đã đóng riêng phần giải thích đã duyệt và vòng quay lui.0Gemini,0embedding,0DocGoogle trong lượt. Sổ đợt vẫn25/26, không đặt lại ngân sách. Khôi phụcDB/tệp bị chủ sở hữu loại khỏi đợt và chưa kiểm chứng. Tài khoản thứ hai, điều kiện dùng dữ liệu thật và các ca chưa có bằng chứng vẫn theo sổ16gói; không tự ký Production hoặc gộp main. Ảnh cuối `screenshots/render-13938d1-live.jpg` xác nhận trạng tháiLive;Dashboardhiển thị1m50s,tương ứng thời gianstarted→finishedcủaAPI,là số khác vớicreated→finishedđãghi. Đã đóng tabkiểm tạm và dừng hai tiến trình QA do chính lượt này khởi tạo bằngCtrl+C,không dừng tiến trình người dùng/không xóa dữ liệu. Tab sản phẩm mới được giữ lại để người dùng xem.
