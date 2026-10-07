# Đối soát lỗi U04 — 07/10/2026

## Kết quả thật

- Bản đang chạy: 8c4de13b3e5a4bce2c76a25b9c706abf98f2ebd7.
- Yêu cầu: feeee879-1b26-4fad-a296-51fd1f48fdea, lúc 13:28:33 UTC.
- Trang ai.google.dev/gemini-api/docs/rate-limits trả HTTP 200 lúc 13:28:41 UTC.
- Bước tổng hợp thất bại: source_bundle_summary_failed. Không có câu trả lời để chấm.
- Trạng thái bộ ngắt của khóa đang dùng ghi generate/provider lúc 13:28:43.406412 UTC,
  không ghi quota. Điều này không chứng minh hạn mức Google còn bao nhiêu.

## Điều đã loại trừ và điều chưa biết

Đã loại trừ lỗi không tải được trang chính thức trong đúng lượt này.
Đã chạy chuyển đổi và gửi yêu cầu bằng SDK Google thật tới httpx.MockTransport,
với khóa giả, không kết nối Gemini: chuyển đổi cấu trúc và đọc phản hồi đều thành công.
Điều này chỉ loại trừ lỗi chuyển đổi cục bộ, không chứng minh máy chủ Google chấp nhận
cấu trúc gửi lên. Chưa xác định lỗi máy chủ, tên mô hình hay cấu trúc nào bị từ chối.

Nguyên nhân không thể chẩn đoán chính xác từ biên nhận hiện có: lớp bao lỗi đã bỏ
mã HTTP/loại lỗi gốc, chỉ giữ source_bundle_summary_failed. Không suy đoán sửa cấu trúc,
đổi mô hình hoặc yêu cầu đổi khóa khi chưa có bằng chứng.

## Lỗi cấu hình xác định thêm sau đối soát

Đã đọc mô tả API công khai của Google tại
https://generativelanguage.googleapis.com/$discovery/rest?version=v1beta:
Schema của responseSchema không có additionalProperties. SDK thật gửi
additional_properties=false vào responseSchema từ PublicAnswer(extra='forbid').
Đây là lệch định dạng xác định được bằng dữ liệu gửi thật và hợp đồng API,
không phải lỗi chuyển đổi cục bộ. Phần compiler của sản phẩm đã dùng
response_json_schema vì chính ràng buộc này. Tuy nhiên biên nhận U04 cũ không
giữ mã lỗi máy chủ, nên chưa thể chứng minh đây là nguyên nhân duy nhất của lượt đó.

Đã chuyển tổng hợp web sang response_json_schema, giữ đầy đủ kiểm trích đoạn
và kiểm dữ liệu cục bộ. Không đổi mô hình, không gọi thêm lượt, không bỏ bước
suy luận. Phép kiểm mới dùng SDK thật và MockTransport để xác nhận trường
responseJsonSchema có ràng buộc đúng, không gửi responseSchema cũ.

## Thay đổi giới hạn

Giữ mã HTTP thuộc danh sách cố định hoặc loại lỗi cấu hình/dịch vụ trong mã lỗi công cụ.
Không lưu thông báo thô từ nhà cung cấp, nội dung nguồn, khóa, hoặc mật khẩu.
Không tự thử lại lỗi 400/404 không thể khắc phục bằng chờ. Không tăng hạn mức,
không gọi thêm nguồn hoặc mở rộng bộ kiểm. Đây là chẩn đoán, chưa phải sửa nguyên nhân
thất bại U04. Bản sửa lệch định dạng nêu trên vẫn cần kiểm trên sản phẩm.
Chưa đóng A/E/F hoặc gộp main.

## Kiểm chứng bản chẩn đoán và sửa định dạng

59 phép kiểm đạt cho bản chẩn đoán ban đầu. Sau sửa định dạng, 85 phép kiểm
đạt trong test_web_reasoning.py, test_public_freshness.py,
test_web_source_failures.py và test_protonx_hardgates.py (17,32 giây).
Lần gọi đầu bộ kiểm mở rộng không chạy được vì tên test_protonx_tools.py không tồn tại;
đã chọn đúng test_protonx_hardgates.py rồi chạy đầy đủ, không tính lần sai là đạt.
Ruff và git diff --check đạt. Các ca mới kiểm mã 400/404/429/503, tính có thể
thử lại và không lộ nội dung riêng. Không phép nào gọi Gemini thật.

Nguồn đối soát: biên nhận lưu trong Supabase, nhật ký ứng dụng Render đúng lượt,
SDK Google cài trong backend/.venv. Thao tác đã thực hiện bằng Supabase và Render;
không tuyên bố đã xem trực tiếp giao diện thanh bên.

## Bản sửa sẵn sàng triển khai

- Mã nguồn: 52679964193864136e8e2a7c77333fd1d146c0ea.
- GitHub CI 37631186037 hoàn tất thành công, gồm postgres-state và verify.
- GHCR HEAD của nhãn đúng mã nguồn trả HTTP 200; mã ảnh:
  sha256:3abd78d3a46b407337c8c3c0741ae91b15fd34ab03c06c8a92ccaed8fcfb12f2.
- Ảnh triển khai:
  ghcr.io/dbp3206-source/veridra@sha256:3abd78d3a46b407337c8c3c0741ae91b15fd34ab03c06c8a92ccaed8fcfb12f2.
- Chưa triển khai bản sửa lên Render; không coi ảnh đã xuất bản là dịch vụ đã đổi bản.
- Công cụ điều khiển thanh bên khởi động thất bại: node_repl kernel exited unexpectedly;
  windows sandbox failed: helper_unknown_error: setup refresh had errors.
  Đã yêu cầu mở trang Settings bằng open_in_codex, kết quả queued, không coi là đã nhìn thấy trang.
- Theo hướng dẫn render-docker, dùng mã ảnh bất biến; không kích hoạt triển khai lại ảnh cũ.
  Cần người dùng đổi nguồn ảnh trong dịch vụ hiện có, không thêm dịch vụ hoặc đổi gói.

## Xác nhận triển khai sau đó

Render dep-db34ug59fdbs73a05nag đã Live đúng mã ảnh nêu trên lúc
2026-10-07T13:57:07.100928Z. /api/health trả status=ok, database=true,
object_storage=true; runtime bắt đầu 20:57:04.962576 giờ Việt Nam.
Đã thực sự gọi render_get_deploy theo hướng dẫn render-monitor và đọc kết nối
công khai. Không coi gemini_connectivity=not_probed là kết nối Gemini đã đạt.
U04 sau sửa chưa có kết quả; cần một lượt qua tài khoản quản trị trong sản phẩm.

## Kết quả sau sửa — U04 đạt

Lượt aade876b-9698-4adb-8fbc-c6b3f143fa5a hoàn tất lúc
2026-10-07T14:00:04.662107Z; câu trả lời 6cc4e938-ca29-4d98-8cd7-eb1f139e8e01
nêu đúng hạn mức theo dự án, không theo khóa, có căn cứ ngắn và [S1].
Nguồn 1 là đúng trang rate-limits được hỏi; văn bản lưu chứa quy định hỗ trợ.
web_research và agent_task đều success, lần lượt 10465 và 14798 ms;
không thao tác ghi hoặc công cụ đọc riêng. Tám nguồn được lưu nhưng câu trả lời
chỉ dùng nguồn 1; không biến các tiêu đề tin thành căn cứ kết luận.
Đã đối soát Supabase theo chủ sở hữu; không tuyên bố kiểm trực quan thanh bên.
Đóng ca này, không kiểm lặp. Đây không phải điểm tổng hay xác nhận toàn bộ web,
và chưa đóng tất cả hồ sơ doanh nghiệp/chuỗi nghiệp vụ trong A/B/E/F.

## Lỗi báo cáo doanh nghiệp sau đó — chưa đạt

Lượt 18cadd6d-9392-4b93-9b74-afb1a7f91872 trên 5267996,
đầu vào 0b6e8d05-5952-4dd2-badc-4e460867e898, thất bại sau 65679 ms.
Đây là company-02 (Vinamilk), không thay đổi kết quả U04 đã đạt.
Nguồn web đã đọc thành công trong 11654 ms; trang công ty trả HTTP 200.
Nhật ký Render lúc 14:11:01 UTC ghi Gemini 504 DEADLINE_EXCEEDED ở bước
lập báo cáo. Lúc 14:11:06 UTC lớp ngoài đổi khóa và chạy lại toàn quy trình;
web bắt đầu lần thứ hai rồi bị giới hạn tổng 60 giây cắt. Không có báo cáo
đạt để chấm; không kết luận hết hạn mức từ mã 504.

Nguyên nhân trong ứng dụng: thời gian gọi báo cáo ngắn, nhiều lượt dự phòng
cộng với việc chạy lại nguồn ở lớp đổi khóa, dù nguồn đã hoàn tất. Bản sửa
dành 25 giây cho lần lập báo cáo chính, giới hạn một lần dự phòng 10 giây,
giới hạn đầu ra 4096 đơn vị thay vì 8192 nhưng giữ đủ trường báo cáo.
Lớp đổi khóa không chạy lại toàn quy trình sau công cụ thành công; phục hồi
riêng bước tạo câu trả lời vẫn ở bên trong bộ điều phối. Giữ giới hạn tổng,
ngân sách khóa, danh sách mô hình và các kiểm nguồn/trích dẫn như cũ.
Không đảm bảo Google không bao giờ trả 504; phải kiểm một lượt thật sau
triển khai trước khi đóng company-02. Chưa sửa điểm hoặc xác nhận A/E đạt.

Kiểm mã sau sửa: 194 phép kiểm đạt trong 59,13 giây (test_adk.py,
test_compiler.py, test_chat_atomicity.py); không gọi Google thật. Có kiểm
giữ cấu hình lần chính, giới hạn lượt dự phòng, giữ cấu trúc nguồn, không
đọc lại nguồn sau lỗi 504 và vẫn đổi khóa khi chưa có công cụ hoàn tất.
Lần kiểm đầu có hai lỗi thiếu import trong phép kiểm mới (192 đạt, 2 lỗi);
đã sửa import và chạy lại đủ cả ba tệp, không ghi lần lỗi là đạt.
Ruff đạt. Đây là bằng chứng sửa mã, không thay bằng chứng câu trả lời thật.
