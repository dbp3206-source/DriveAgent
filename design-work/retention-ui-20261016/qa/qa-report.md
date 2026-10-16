# Kiểm tra giao diện và lưu dữ liệu theo hạn — 16/10/2026

## Kết luận

Phần nhắc người dùng xem và duyệt dọn dữ liệu đã được nối vào giao diện hiện có, các đường máy chủ cho xem trước/trạng thái/duyệt/tiếp tục đã được kiểm trên dữ liệu giả lập cô lập. **Chưa đạt trạng thái phát hành**: thay đổi còn ở nhánh làm việc, chưa chạy CI đúng mã, chưa lên GitHub `main` hoặc Render. Báo cáo này chỉ xác nhận phần đã kiểm tại máy, không phải chứng nhận toàn sản phẩm.

## Phạm vi và dữ liệu

- Giao diện React/Fluent hiện tại: hộp thoại tự nhắc mỗi ngày, số lượng lấy từ máy chủ, phạm vi dọn dữ liệu Veridra, cảnh báo đặt lại ngữ cảnh trợ lý, checkbox xác nhận mặc định bỏ chọn, để sau, xem trạng thái/tiếp tục/thử lại/hủy theo trạng thái tác vụ.
- Máy chủ: xem trước ký theo người dùng, xác nhận rõ ràng, chặn sai nguồn trình duyệt, sổ tiến độ bền, dọn tiếp sau gián đoạn và kiểm tra đọc lại. Không có cuộc gọi mô hình hoặc Google.
- Dữ liệu kiểm tra là dữ liệu giả lập trong thư mục tạm riêng; không đọc Gmail/Drive/Lịch, không ghi hoặc xóa dữ liệu trên Google/Supabase thật, không gọi Gemini/Tavily.
- Bản gốc Google, dữ liệu người khác và nội dung hội thoại chuẩn phải còn nguyên. Giao diện được kiểm với bản xem trước giả: 4 mục đến hạn, 3 mục đã chọn, 1 mục ngữ cảnh sẽ đặt lại.

## Root cause đã xác minh và sửa

Trước sửa, tuổi ngữ cảnh LangGraph được suy từ thời gian sửa của toàn bộ tệp SQLite/WAL. Vì nhiều tài khoản cùng dùng tệp đó, hoạt động mới của người khác có thể làm dữ liệu cũ của một người trông như mới, khiến họ không bao giờ nhận nhắc dọn.

Đối chiếu mã phiên bản khóa trong `backend/uv.lock` và mã nguồn thư viện đã cài: LangGraph tạo `checkpoint_id` bằng UUIDv6. Bộ kiểm tra mới đọc riêng ID checkpoint/bản ghi ghi của đúng chủ sở hữu, giải mã mốc UUIDv6, không mở hoặc giải tuần tự nội dung checkpoint. Nếu ID không biết định dạng hoặc hỏng, kiểm kê dừng an toàn thay vì đoán tuổi. Ca tích hợp giả lập đã cập nhật tệp gần đây nhưng giữ checkpoint người A 40 ngày tuổi; hệ thống vẫn nhận ra A đến hạn, trong khi dữ liệu mới của B vẫn còn.

Khi người dùng duyệt dọn, cảnh báo hiện rõ rằng ngữ cảnh làm việc của chính họ có thể được đặt lại. Việc đặt lại ngữ cảnh không xóa lịch sử chat chuẩn; người dùng khác không bị ảnh hưởng.

## Kiểm tra đã chạy

| Hạng mục | Kết quả | Giới hạn |
|---|---|---|
| Backend suite tại máy | **1.915 đạt, 28 bỏ qua, 0 lỗi** trong 488,04 giây; độ phủ **88,31%** | 1.943 ca chạy trong môi trường dữ liệu tạm cô lập; 23 ca PostgreSQL và 5 ca kho tệp ngoài bị bỏ qua. 11 ca `test_config.py` chạy riêng, đạt 11/11 để không cho địa chỉ DB tạm làm sai cấu hình cố định trong bài kiểm. Tổng: 1.926 đạt/28 bỏ qua trên 1.954 ca. CI đúng commit vẫn bắt buộc. |
| Backend lint, scripts lint, dependencies | Ruff backend/scripts đạt; `pip check` không phát hiện phụ thuộc lỗi | Chỉ mã trong nhánh làm việc |
| Quét bí mật phát hành | Đạt trên 768 tệp Git-visible | Không in giá trị bí mật; không thay thế rà soát dữ liệu cá nhân |
| Đánh giá ngoại tuyến | **200/200**: điều hướng 12, bộ đánh giá 12, hợp đồng câu trả lời 16, chống sửa lệch 160 | Không gọi mô hình; không chứng minh chất lượng Gemini khi chạy thật |
| Bộ dữ liệu nghiệm thu nội bộ | Đạt cấu trúc: 10 ca/4 tệp, trần 19 yêu cầu khớp manifest | Chỉ kiểm tính toàn vẹn đầu vào, chưa chạy chấp nhận sản phẩm |
| Frontend unit | **222 đạt, 0 lỗi** | Đúng mã hiện tại |
| Frontend lint/build | Đạt; build vào `.verify-dist` cô lập rồi xóa đúng thư mục do lượt kiểm tạo | Không ghi đè `frontend/dist` có thể đang được phục vụ |
| Trình duyệt cục bộ | Đạt trên Chromium qua Playwright: sáng/tối; 1440×900, 1280×800, 390×844, 320×780; giảm chuyển động | API được giả lập trong trình duyệt, không đăng nhập tài khoản thật |
| Hành vi an toàn trên giao diện | Checkbox mặc định bỏ chọn; nút xác nhận bị khóa; không gửi yêu cầu xác nhận; bàn phím giữ tiêu điểm trong hộp thoại; không có lỗi trang hoặc yêu cầu ra ngoài máy cục bộ | Không nhấn nút xóa và không thử trên dữ liệu thật |
| Tràn bố cục | Không tràn chiều ngang hay tràn nội dung hộp thoại ở 390 và 320 px | Kiểm theo các kích thước đại diện, không thay cho kiểm thiết bị thật |
| Dấu vết phát hành thử | Tệp HTML harness không có trong `frontend/public` hoặc `frontend/dist` | Harness chỉ dùng ở `frontend/src/retention-notice-harness.tsx` và script kiểm cục bộ |
| Kho mã | `git diff --check` đạt | Chưa commit, đẩy, chạy CI, phát hành ảnh hoặc triển khai |

Hai lượt fail-fast trước đó không xác nhận lỗi sản phẩm: một lượt dùng nhầm driver SQLite cho kho quan hệ; lượt kế đặt toàn suite vào một thư mục trạng thái chung, khiến các ca mô phỏng cùng dùng một bộ đếm hạn mức. Lượt cuối bỏ cấu hình quan hệ/trạng thái chung và cô lập DB theo từng ca; toàn bộ suite đạt như bảng trên. Không sửa mã sản phẩm để che lỗi môi trường này.

Ảnh chụp đã rà soát bằng mắt:

- `screenshots/retention-dark-desktop.png`
- `screenshots/retention-dark-mobile.png`
- `screenshots/retention-light-desktop.png`

## Chấm chất lượng của phần này

**86/100 cho lát cắt lưu giữ dữ liệu và giao diện đã kiểm cục bộ**, không phải điểm tổng thể sản phẩm.

| Tiêu chí | Điểm |
|---|---:|
| Đúng yêu cầu và nội dung | 18/20 |
| Phù hợp giao diện hiện có | 16/20 |
| Cấu trúc và thứ bậc thông tin | 13/15 |
| Dễ đọc | 13/15 |
| Bố cục và khoảng cách | 13/15 |
| Hoàn thiện kỹ thuật, khả năng kiểm chứng | 13/15 |
| **Tổng** | **86/100** |

## Điều còn chặn tuyên bố production-ready

1. Chạy CI đầy đủ trên đúng commit, đặc biệt PostgreSQL riêng, dựng Docker/chạy ảnh, xuất PDF tiếng Việt và triển khai tự động theo điều kiện nhánh.
2. Rà soát bản diff đầy đủ, sau đó mới commit/đẩy theo nhánh đã thống nhất. Hiện HEAD là `f71af08efbe5823326d69ac18f9a86efd8e228b2`, nhánh `work/data-retention-20261015`; các thay đổi trong báo cáo còn chưa commit.
3. Triển khai có kiểm soát và kiểm lại đúng phiên bản trên URL. Render hiện vẫn chạy bản cũ; không được coi kiểm thử cục bộ là kiểm thử cloud.
4. PostgreSQL tại máy đã bỏ qua 23 ca và cần CI chuyên dụng để xác nhận; kiểm thử khôi phục cơ sở dữ liệu/tệp và thử bốn tài khoản thật (T09) được miễn theo quyết định trước đó, **không tính là đạt**.
5. Có shared backup đã mã hóa thì kiểm kê hiện dừng an toàn thay vì tuyên bố đã xóa bản sao đó. Bản sao nhà cung cấp/tải về bên ngoài không nằm trong phạm vi Veridra.

## Công cụ và tài sản

- Dùng design system Fluent UI 9 sẵn có, không thêm thư viện/kiểu thiết kế hoặc ảnh bên thứ ba.
- Dùng Playwright với Chromium cục bộ và dữ liệu API giả lập; không dùng trình duyệt đăng nhập của người dùng.
- Không có skill hoặc MCP thiết kế nào được viện dẫn như đã chạy.
- Ảnh chụp là đầu ra kiểm thử cục bộ, không chứa dữ liệu thật.
