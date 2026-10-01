# Veridra — nghiệm thu ứng viên ngày 01/10/2026

**Quyết định hiện tại: HOLD. Owner đã duyệt push staging; chưa phát hành.**

Build fingerprint: `cfcfc0e770b681f95054d5dbb09a08534e8f5d795ad0b1be6e16da1b312f0b75`.
Fingerprint bao gồm backend, frontend, workflow CI, dependency lock và Dockerfile.
Mã đang chạy local tại `http://localhost:8000`.

## Kết quả đã kiểm nghiệm

| Bộ kiểm chứng | Kết quả | Giới hạn của bằng chứng |
|---|---|---|
| Backend candidate | 835 passed, 9 skipped | 9 ca PostgreSQL chờ CI database thật; test topology manifest chạy lại 36 ca sau đó |
| Coverage | 85,39%, qua gate CI 85% | Cùng mã nghiệp vụ candidate, không chứng minh chất lượng mọi output live |
| Frontend | 138 passed; ESLint và build đạt | Unit/build không thay thế kiểm thử trình duyệt |
| Regression offline | routing 12/12; output 12/12; contract 16/16; mutation 160/160 | Không chấm độ đúng mọi câu trả lời live |
| Trình duyệt cuối | 24 màn hình desktop/mobile, không lỗi network/console được ghi nhận, không overflow | Phạm vi trang và thao tác trong script smoke |
| Gmail UI | Mở mail, chuyển HTML/text ở desktop/mobile; loading chậm có thông báo và hồi phục | Không chứng minh mọi ảnh ngoài đều có thể truy cập |
| Hai PDF local trong cùng câu hỏi | completed; 2 nguồn, 9 citation có trang | Chỉ kiểm chứng thu thập nguồn/citation; chưa chấm từng nhận định với oracle độc lập |
| Tồn kho live sau sửa | Một lượt completed 816 từ; lần lặp sau có oracle số 840/590 đạt nhưng status incomplete | Chưa đạt độ ổn định: bước rewrite còn có thể thêm số mới hoặc hụt độ dài, phải giữ HOLD |
| Lint Python/dependency | Ruff đạt; pip check không phát hiện dependency hỏng | Môi trường Windows hiện tại |
| Secret scan | 852 file Git-visible đạt; 255 blob lịch sử đạt sau phân biệt đúng canary giả | Không thay thế rà soát PII, ảnh hay bản quyền |

Browser evidence riêng tư giữ tại `screenshots/browser-smoke-20260929/report.json`;
script ghi đè tên thư mục lịch sử này, lượt thực thi cuối ở ngày 01/10. Không đưa ảnh
Gmail hay raw câu trả lời riêng vào repo. Kết quả regression mới ở `regression-20261001.json`.

## Lỗi đã sửa và kiểm chứng

1. Câu hỏi nêu hai tệp local chỉ đọc tệp đầu: router giữ mọi tên tệp; source controls
   giữ toàn bộ tuyến đọc phù hợp. Mỗi tệp được lấy bằng chứng riêng.
2. PDF native text chưa có semantic index nên tuyến nhiều nguồn thất bại: local reader
   truy xuất theo từ khóa trên chunk có số trang, cùng kiểm tra owner, không cần gọi embedding.
3. Tồn kho trước đây trả 410 thay vì 840: thêm bộ tính Decimal với input rõ ràng, dùng
   cùng tuyến thực thi trong ADK và LangGraph. Kiểm thử lại cả số cơ sở và kịch bản.
   Reorder point cần so với inventory position có tính đơn mua đang chờ; không chỉ
   so với on-hand stock rồi khuyến nghị mua trùng. Đây vẫn là tính toán với input rõ ràng.
4. Rút gọn tự động cắt mất phần cuối câu hành động: giữ nguyên câu nếu không có ranh
   giới câu hoàn chỉnh; khi thiếu chuẩn độ dài, dùng bước sửa có giới hạn và báo đúng trạng thái.
5. Freshness fallback trước đây có thể lỗi khi model không dùng marker: chỉ dùng tiêu đề
   đã lấy thực và thông báo chưa xác minh khi không đủ bằng chứng. Đây là kiểm chứng
   xử lý thiếu bằng chứng, chưa phải PASS cho mọi yêu cầu thông tin cập nhật.

Guard so sánh số học cũng đã được sửa để phân biệt thời gian, lượng hàng và phần
chênh lệch; 33 kiểm thử output contract đạt. Lượt live lặp lại vẫn bộc lộ hạn chế ở
bước rewrite của model. Chưa chứng minh độ ổn định cho báo cáo dài theo contract.

## Đối chiếu gate phát hành

| Gate | Trạng thái | Còn cần gì để nghiệm thu đầy đủ |
|---|---|---|
| Chat/đúng nguồn/nghiệp vụ | NOT VERIFIED toàn bộ | Bộ 24 live + holdout có oracle; đối soát từng claim, không chỉ completed |
| Thông tin cập nhật | NOT VERIFIED | Các ca dương phải trả đúng dữ kiện hiện tại từ nguồn chính thức; fallback RSS chưa đủ |
| PDF/RAG | NOT VERIFIED toàn bộ | Oracle từng trang/số liệu cho PDF native; đa cột và bảng cần đối chiếu |
| Workflow/bảy vai trò ProtonX | NOT VERIFIED toàn bộ | Sáu workflow doanh nghiệp đầu cuối; chứng minh từng vai trò bằng execution thật |
| Approval/security/isolation | NOT VERIFIED toàn bộ | Preview → duyệt → execute → readback trên build cuối, fault/retry và nhiều user |
| Durable execution | NOT VERIFIED cloud | Redeploy, checkpoint, đối soát trạng thái ghi unknown và chống trùng |
| UI | PASS smoke giới hạn | Đã có smoke cuối; đối soát toàn bộ keyboard/loading/error và mọi workflow còn lại |
| Cloud | NOT VERIFIED | Render Veridra chưa có; OAuth HTTPS/BYOK bốn người, persistence, tài nguyên và cold-start |
| Release | NOT VERIFIED | PostgreSQL thật, CI image digest, clean clone và database/Storage restore |
| AgentOps | NOT VERIFIED cloud | Logs/metrics/traces request cloud, retention và dashboard có dữ liệu thật |

Không suy ra điểm ≥9,2 hoặc production-ready từ số ca unit đã đạt. Những kết quả
Gmail/Drive/sáu doanh nghiệp và PDF ngày 30/09 là bằng chứng trước sửa; cần kiểm tra
lại phạm vi bị ảnh hưởng trước khi đưa vào manifest phát hành cùng build.

## Hạ tầng đã kiểm tra trực tiếp

Render đã đăng nhập nhưng danh sách dịch vụ chưa có Veridra. Supabase đã đăng nhập,
organization Veridra có một project Free. Không lấy hoặc in service-role key/database
password trong báo cáo. Chưa có URL public Veridra được chứng thực.

Owner đã duyệt branch `staging/veridra-closed-beta-20261001` để CI và cloud kiểm chứng
candidate. Giữ HOLD, không merge main hoặc phát hành. Staging chỉ xuất image theo SHA
và tag staging; không cập nhật tag closed-beta hay gọi deploy hook production.

OCR, scan-only PDF, paid fallback/hosting và stack Docker quan sát nặng được EXCLUDED
theo lựa chọn owner. PDF có lớp văn bản vẫn được hỗ trợ. Không xóa file gốc hay dữ liệu cá nhân.

## Cách kiểm chứng các sửa lỗi

- Tài liệu local: nạp hai PDF có lớp text; Chat chọn nguồn local; hỏi so sánh hai tên
  tệp rõ ràng. Citation phải chứa cả hai tệp và số trang.
- Tính toán: nhập kịch bản kho 1.600, nhu cầu 420/tuần ±100, lead time 3 tuần,
  safety stock 250, đơn nhập 500 đến sau 2 tuần. Kiểm tra cơ sở 1.260/840/590;
  high ending 540, low ending 1.140; không coi ngưỡng đề xuất là chính sách đã xác minh.
- Gmail: mở thư có HTML; đổi qua text rồi trở lại HTML; kiểm tra ảnh inline và
  nội dung nguyên bản. Ảnh từ máy chủ ngoài bị chặn/hỏng cần trạng thái riêng.
- Nhật ký: quyết định toàn sản phẩm phải tiếp tục HOLD khi các gate bắt buộc chưa có bằng chứng.

Hướng dẫn sử dụng ở `../../docs/VERIDRA-USER-GUIDE-AND-DEMO.md`; triển khai ở
`../../docs/DEPLOY_CLOSED_BETA.md`. Hai tài liệu hướng dẫn không tự chứng minh triển khai đã thành công.
