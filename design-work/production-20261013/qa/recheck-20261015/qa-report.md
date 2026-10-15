# QA kiểm bổ sung cloud — 15/10/2026

Đầu vào: bộ `docs/verification/internal-assistant/testcases.json` phiên bản `.2`, bốn tệp giả lập A/B/C, ghi chú thử IA-QA-20261013 đã sửa v2. Không đổi oracle hoặc nội dung sản phẩm. Chi tiết đầu vào/đầu ra và kết luận ở [kết quả ngày15/10](../../../../docs/verification/internal-assistant/RESULTS-20261015.md).

## Công cụ thực đã dùng

- `mcp__cua_repl.js`: trình duyệt thanh bên đã đăng nhập; thao tác nút/ô nhập, đọc nội dung/ngữ cảnh/dấu vết thật, chụp JPEG. Hướng dẫn hiện hành của công cụ và `screenshots` đã đọc; không dùng Windows native automation hoặc giả lập giao diện.
- Render qua UI: đọc nhật ký dịch vụ hiện có, xác nhận một yêu cầu tạo chỉ mục200 cùng truy vấn ghi chú thử. Không đổi khóa, hạn mức, Environment, gói hoặc triển khai lại.
- `functions.exec`/PowerShell: đọc mã định tuyến/giới hạn gọi, nguồn đầu vào và sổ; `apply_patch` chỉ cập nhật tài liệu và manifest. Không gọi nhà cung cấp từ máy hoặc đọc khóa.
- Không tuyên bố gọi Render MCP hoặc chạy lại bộ kiểm mã trong lượt chỉ kiểm cloud này. Các bộ kiểm mã thuộc hồ sơ bản ed3fa6a trước đó.

## Kết quả

T02 đúng hai kết luận chính/có đúng hai nguồn nhưng thiếu nhắc điều kiện dữ liệu. T04 đổi số và đổi hồ sơ chạy xong;60/42giờ đúng, chưa nêu riêng18giờ tiết kiệm; không lẫn hồ sơ và không đọc nguồn cấm ở lượt chuyển. T04tính lại gặp504 ở Gemini3.5, kết quả cuối từ3.8dự phòng; không dùng nó chấm riêng3.5. Linh vật báo xong ngoài trang Chat, bấm về đúng cuộc trò chuyện. T08tìm thực chỉ trả đúng một ghi chú v2; sau xác nhận riêng của chủ sở hữu đã xóa mục này, ba mục khác giữ nguyên, mở lại trang và tìm mới trả0. Chưa kiểm câu trả lời bộ nhớ trong hội thoại mới.

Mới dùng5sinh câu trả lời+2tạo chỉ mục=7yêu cầu. Tổng đợt17+8=25/26. Tạo Google Doc mới0. Không đặt lại bộ đếm. Không chấm điểm tổng hợp hoặc chứng nhận Production từ các phép kiểm riêng.

## Ảnh và kiểm hình

Ảnh JPEG gốc ở `../screenshots/` tính từ thư mục chứa báo cáo này:

- `t02-policy-ed3fa6a-20261015.jpg`: thấy câu hỏi, phần trả lời không vừa một khung; nội dung đã đọc riêng đầy đủ qua DOM. Không dùng ảnh này làm bằng chứng hình ảnh đầy đủ câu trả lời.
- `t04-reset-ed3fa6a-20261015.jpg`: Mộc An8người và câu hỏi làm rõ, không lẫn báo giá trước.
- `mascot-response-ed3fa6a-20261015.jpg`: đang ở Bộ nhớ, thông báo có câu trả lời/badge1 và nút mở lại.
- `t08-memory-match-ed3fa6a-20261015.jpg`: truy vấn mã thử, một kết quả, đầy đủ bản sửa/phạm vi ghi chú.
- `t08-deleted-ed3fa6a-20261015.jpg`: thông báo xóa thành công sau xác nhận của chủ sở hữu.
- `t08-forgotten-ed3fa6a-20261015.jpg`: cùng mã thử,0kết quả và thông báo không tìm thấy sau lần truy xuất mới.

Đã mở và xem từng ảnh từ công cụ chụp. Khung566×676; không thay bằng chứng390mobile hoặc toàn bộ luồng vận hành. Không có ảnh giả, không sửa ảnh, không chụp khóa/thư riêng. Ảnh minh chứng sản phẩm của chủ sở hữu, không dùng tài sản bên thứ ba mới.

## Sai khác công cụ và giới hạn

- Locator chờ nút đầu ra T02 hết thời gian trước khi tác vụ xong; đọc lại trạng thái rồi nhận đầu ra17,7giây, không gửi lại câu hỏi.
- Locator role=button không khớp phần mở nhật ký HTMLsummary; dùng nhãn chữ đang có để mở. Không coi đây là lỗi nút sản phẩm.
- Trạng thái sau chọn hội thoại/tìm bộ nhớ ban đầu còn đang tải; chờ kết quả rồi mới kết luận, không dùng danh sách trước làm chứng cứ.
- Ghi chú thử đã xóa sau xác nhận riêng “xác nhận xóa”. Click tọa độ nằm gần linh vật mở linh vật thay vì xóa; đọc lại trạng thái, thu nhỏ rồi dùng Enter trên đúng nút Xóa. Lệnh phím báo hết thời gian điều khiển; không gửi lại: trạng thái kế tiếp đã xóa thành công, không còn hộp xác nhận. Đối chiếu kết quả và nhật ký, không coi lỗi quan sát là thất bại xóa. Không xin/chạm mật khẩu database; chủ sở hữu loại khôi phục khỏi đợt ngày15/10, ghi chưa kiểm chứng.
- Phần giải thích cuối vẫn chờ góp ý bản nháp, chưa sửa UI; hai tài khoản thật và điều kiện dữ liệu còn thiếu. Không mở dữ liệu doanh nghiệp nhạy cảm hoặc gộp main dựa trên các ca này.

Không áp thang điểm thiết kế100điểm cho lượt kiểm không tạo/sửa thiết kế; báo từng bằng chứng và mức thiếu thay vì tự cấp điểm để qua cổng.

## Kiểm hồ sơ trước lưu Git

`git diff --check` đạt; hai manifest JSON đọc được. Chạy thật `scripts/scan_release_secrets.py`:701tệp Git-visible, không phát hiện theo mẫu của bộ quét. Bộ quét không chứng minh loại hết mọi dữ liệu riêng; từng ảnh được xem riêng. `scripts/validate_internal_assistant_dataset.py`:10ca/4tệp, integrity_passed=true; trần11+8/19 trong bộ đề là cấu hình lịch sử, quyền thực thi bổ sung được ghi riêng trong sổ, không sửa oracle.

Sau xóa/truy xuất mới: Render có đúng một DELETE204 lúc20:25:30, mã9195552e; yêu cầu tạo chỉ mục20:27:53 trả200. `git diff --check`/parse JSON đạt, quét bí mật lại704tệp Git-visible đạt. Hai ảnh sau xóa được mở/xem và bămSHA256, không sửa ảnh. Không chạy các kiểm vận hành chỉ mới đọc mã; không lấy việc đọc bài kiểm làm bằng chứng đã thực thi.

## Kiểm vận hành bổ sung sau đó

Chạy thật `pytest backend/tests/test_chat_tasks.py backend/tests/test_readiness_recovery.py` với cấu hìnhpytest của backend, DB/trạng thái riêng và không dùng mô hình thật:16đạt/0bỏ qua/0lỗi,26,77giây. XML16ca được đọc lại (26,719giây); có ca tiến trình thật thoát74 rồi tiến trình mới hoàn tất tác vụ. Ca hết quyền xử lý chỉnh mốc trong dữ liệu thử để khỏi chờ120giây; không đo thời gian phục hồi cloud. Các lỗi DB/kho là giả lập. Không sửa mã hoặc dừng tiến trình/dịch vụ thật. XML/DB giữ tại máy trong thư mụcvalidationđược Git bỏ qua.

Đã đọc đầy đủ ba hướng dẫn Render hiện hành `render-monitor`, `render-docker`, `render-deploy` và `render-deploy/references/post-deploy-checks.md`. MCP Render không có trong danh mục công cụ hiện hành; lệnh thật `render --version` lỗi “The term 'render' is not recognized...”. Quy trình CLI/MCP không hoàn thành; dùng giao diện thanh bên đã được chủ sở hữu chọn để thao tác nguồn ảnh dịch vụ hiện có, không dựngBlueprint/tạodịchvụ/càiCLI hoặc xin khóa. Không tuyên bố đã gọi Render MCP. Hướng dẫn ảnh giúp giữ digest bất biến, không đụng bí mật/Environment và kiểm sau triển khai; nhãn license trong baSKILLlàMIT, không phân phối mã/asset của skill.

Đối chiếu Git giữa2dbaac5vàed3fa6a: không thay DB/core/khóa dependency, hai bản cùng có thu hồi phiên. Render Source/header ban đầu đúng7727c538. Điền ảnhac46a7a trong hộp chưa lưu; Connect bị auto-review từ chối vì thiếu quyền rõ cho đúng ảnh quay lui, trước khi gửi triển khai. Không thử đường khác. Hủy modal; hai liên kết Source/header đọc lại vẫn7727c538. Ảnh `render-rollback-not-applied-ed3fa6a-20261015.jpg` được chụp/mở thực; không có secret. Chưa PASS quay lui cloud, cần xác nhận riêng của chủ sở hữu do rủi ro gián đoạn dịch vụ. Bản đang Live giữ nguyên; ngân sách25/26không đổi.

Đường dẫn hướng dẫn đã đọc: `C:/Users/Bao Phuc/.codex/plugins/cache/openai-curated-remote/app-6a624c56bfe081918f7544f7d58f6faf/1.0.1/skills/`, tương ứng ba thư mục `render-monitor`, `render-docker`, `render-deploy`. Không cài/cập nhật công cụ. Kiểm hồ sơ cuối:diffcheck/parseJSONđạt, quét705tệp Git-visible đạt; không dùng kết quả quét làm chứng nhận quyền riêng tư.
