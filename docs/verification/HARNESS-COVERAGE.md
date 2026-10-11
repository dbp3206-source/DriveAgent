# Các bộ kiểm chất lượng, bảo mật và kiểm soát hành động

Đây là bản đồ đến dữ liệu, bộ chấm và kiểm thử thật đang có; không dựng các bảng
điểm tượng trưng. Lần kiểm nội bộ ngày 11/10/2026 không gọi thêm mô hình hoặc
Google. Các dòng dưới có thể dùng chung một kiểm; không cộng chúng thành số ca mới.

## Chất lượng câu trả lời và quy trình

| Nội dung | Dữ liệu/cách kiểm | Kết quả có thể kết luận |
|---|---|---|
| Chọn công cụ | `backend/evals/golden_routes.json` | 12/12 ví dụ chọn công cụ đúng |
| Bộ chấm phân biệt đúng/sai | `backend/evals/golden_output_quality.json` | 12/12 ví dụ được bộ chấm phân loại đúng |
| Hợp đồng câu trả lời, nguồn và bố cục | `backend/evals/golden_answer_contracts.json` | 16/16 câu trả lời tham chiếu nhất quán với tiêu chí |
| Biến thể chống chấm nhầm | `run_adversarial_mutation_regression` trong `backend/app/services/evaluation.py` | 160/160 biến thể kiểm được bộ chấm; không phải 160 câu hỏi mô hình chạy thật |
| Quy trình kết hợp nhiều màn hình | [10 ca demo](golden/testcases.json) | Kết quả lịch sử: 3 đạt, 6 đạt một phần, 1 chưa đạt |
| Sáu doanh nghiệp và an toàn | `protonx_company_benchmark.json`, `protonx_security_cases.json` | Có hợp đồng/tiêu chí; không tuyên bố đã chạy đủ mô hình và nguồn thật trong đợt này |

Xem [kết quả nội bộ](evidence/offline-regression-20261011.json) và
[hướng dẫn bộ chấm](../../backend/evals/README.md). `pass_rate=1` ở kiểm nội bộ
không có nghĩa câu trả lời thật của sản phẩm đúng 100%.

## Bảo mật

| Ranh giới được kiểm | Tệp kiểm đang có | Giới hạn |
|---|---|---|
| Mã hóa, che bí mật | `test_security.py` | Dữ liệu thử, không kiểm mọi nơi có thể rò rỉ |
| Danh sách mời, vai trò chủ, thu hồi phiên, lỗi OAuth | `test_oauth_callback.py` | Kiểm ứng dụng với dịch vụ mô phỏng, không đăng nhập mới trên Google |
| Không đọc chéo, khóa riêng | `test_five_user_isolation.py` | Năm người dùng giả lập, không phải năm người dùng thật |
| Quyền bảng phiên cũ | `test_framework_security.py` | Kiểm câu SQL trên kết nối mô phỏng, không kiểm trạng thái cloud |
| Nội dung không đáng tin, nguồn web, lịch chỉ đọc | `test_protonx_hardgates.py` | Chỉ các tình huống đã định nghĩa; không chứng nhận chống mọi tấn công |
| Xác thực giao thức công cụ | `test_protocols.py` | SDK thật, kiểm cục bộ không mô hình |

## Kiểm soát hành động

| Ranh giới được kiểm | Tệp kiểm đang có | Giới hạn |
|---|---|---|
| Vai trò và quyền Google theo nghiệp vụ | `test_document_policy.py` | Ma trận quyền của dữ liệu thử |
| Chốt ghi ngoài, giới hạn quyền chủ, chặn và ghi nhật ký | `test_registry.py` | Không thực sự gửi thư hoặc ghi Google |
| Cố định bản xem trước, thực thi một lần, lưu mốc, đọc lại | `test_document_tool_execution.py` | Dịch vụ Google mô phỏng; Doc thật thuộc báo cáo demo riêng |
| Chặn phát lại mã hành động | `test_relational_remote_actions.py` | Cơ sở dữ liệu SQLite thử, không kiểm nhiều máy cloud |
| Chỉ thử lại lỗi phù hợp, nhật ký an toàn, hoàn tác khi lỗi | `test_registry.py` | Không thay kiểm khôi phục toàn bộ hệ thống |

Ma trận có selector cụ thể ở [security-governance-cases.json](golden/security-governance-cases.json).
Biên nhận lần chạy [78/78 kiểm đạt](evidence/security-governance-20261011.json)
ghi từng tệp, số kiểm, thời gian, mã nguồn nền và lệnh. Không có kiểm bỏ qua.
Không chia các kiểm giao nhau thành nhiều tỷ lệ độc lập.

## Không tuyên bố vượt bằng chứng

Chưa có kiểm xâm nhập độc lập, chứng nhận tuân thủ, kiểm đủ người dùng thật,
khôi phục cloud hoặc bảo đảm mọi chỉ dẫn độc hại đều bị chặn trong đợt này.
Các nội dung này là giới hạn, không tự mở thêm công việc phát triển. Tài liệu
[bảo mật](../SECURITY.md) và [cổng kiểm công cụ](../TOOL_REGISTRY.md) mô tả thiết kế;
biên nhận chạy mới là bằng chứng của những kiểm cụ thể.
