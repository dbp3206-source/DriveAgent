# Sự cố cách ly phép kiểm LangGraph — 16/10/2026

## Sự cố và phạm vi đã biết

Phép kiểm mới truyền `data_dir=tmp_path` vào `Settings`. Đây là thuộc tính tính toán,
không phải trường cấu hình; cấu hình bỏ qua trường thừa. Vì vậy `initialize()` đã mở
tệp cục bộ có sẵn:

`C:\Users\Bao Phuc\Documents\DriveAgent\drive-agent\data\langgraph_checkpoints.db`

Phép kiểm khởi tạo luồng giả lập và chạy đồ thị thật trong tệp này. Phép kiểm đặt lại
bộ nhớ tạm sau đó lấy **mọi** `thread_id` khác nhau, không giới hạn tài khoản giả lập,
rồi gọi `AsyncSqliteSaver.adelete_thread()` cho mỗi kết quả. Mã thư viện được kiểm tra
trực tiếp: thao tác xóa các hàng của hai bảng `checkpoints`, `writes` theo luồng và
ghi giao dịch. Thư viện dùng chế độ WAL nên các tệp phụ `-wal`/`-shm` cũng có thể đã
thay đổi trong thời gian kết nối.

Phép kiểm ngay trước đó quan sát được **27 luồng**. Không ghi lại số lượng chính xác
của vòng lặp xóa hoặc tổng trước/sau sự cố; không trình bày 27 như số đã xóa được
xác minh. Không đọc hoặc đưa nội dung riêng trong các bản ghi này vào báo cáo.

Đây là lỗi của phép kiểm, không phải thao tác người dùng xác nhận dọn dữ liệu.
Không có thao tác khôi phục hoặc xóa bổ sung trên tệp thực sau khi phát hiện.
Không có bằng chứng khôi phục các hàng bộ nhớ tạm đã xóa, nên không khẳng định có
thể hoàn tác. Lịch sử trò chuyện chính và bộ nhớ tạm điều phối là hai kho khác nhau;
không được coi việc bộ nhớ tạm bị xóa là toàn bộ dữ liệu sản phẩm đã được dọn.

## Những gì không được gọi trong nhóm phép kiểm này

- Cơ sở dữ liệu ứng dụng dùng máy SQL riêng trong `tmp_path/canonical.db` từ đầu,
  với `SessionFactory` của bộ điều phối được thay bằng máy SQL thử.
- Không khởi tạo kho Qdrant, ADK hoặc kho tệp nguồn. Không gọi API Google, Gemini,
  tạo chỉ mục, Supabase hoặc Render. Mô hình trả lời là đối tượng giả lập ngoại tuyến.
- Không triển khai hoặc ghi dữ liệu lên môi trường đang phục vụ người dùng.

Những nhận định trên dựa trên đường gọi trong mã phép kiểm; không phải một bản
giám sát pháp chứng toàn bộ hệ thống tệp. Ngoài đường dẫn bộ nhớ tạm nêu trên,
các tệp kết quả và cơ sở dữ liệu thử được tạo dưới `tmp`.

## Khắc phục phép kiểm

1. Dùng đúng các trường `state_dir`, `database_url`, `qdrant_path`, đều nằm trong
   `tmp_path`; tắt cấu hình kho quan hệ bên ngoài và kho Supabase cho đối tượng thử.
2. Kiểm tra đường dẫn dữ liệu và Qdrant đã phân giải trước khi khởi tạo bộ điều phối.
3. Kiểm tra `PRAGMA database_list` trỏ đúng tệp LangGraph thử trước khi cho phép chạy ca.
4. Trước vòng lặp xóa, khẳng định mọi luồng có đúng tiền tố tài khoản/phiên/yêu cầu
   giả lập. Đóng bộ điều phối và máy SQL trong `finally`.
5. Chặn việc tạo khách Gemini thật; thay mô hình LangChain bằng mô hình ngoại tuyến.
6. Bỏ các biến môi trường `DRIVE_AGENT_`, `GEMINI_`, `GOOGLE_` của tiến trình thử,
   vô hiệu hóa việc đọc `.env`, dùng thư mục `--basetemp` mới cho mỗi lượt chạy.

Đại diện tác vụ chính đã xem mã cách ly và cho phép một lần kiểm gộp lại. Phép kiểm
cũ `test_orchestrator.py` dùng bộ lưu giả, không gọi `initialize()`; truy vấn lịch sử
mới của ca này được thay bằng `FakeDb` rỗng, không kết nối tệp thật.

## Lịch sử bằng chứng — không lấy kết quả lỗi làm đạt

| Lượt | Kết quả | Ý nghĩa |
|---|---|---|
| Thu thập đầu | Lỗi tên tham số dành riêng `request` | Chưa chạy ca; đã sửa tên trong phép kiểm mới |
| Đồ thị thật đầu | 22 đạt, 10 lỗi | Cùng lỗi `NameError: AgentState` ở bước dựng nhánh LangGraph |
| Sau sửa nhánh | 31 đạt, 1 lỗi | Phát hiện 27 luồng trong tệp không cách ly; **không dùng làm chứng nhận** |
| Sau sửa cách ly, chưa được duyệt chạy lại | Bị ngắt, không có kết quả đầy đủ | Không tính là đạt |
| Lượt gộp cách ly được duyệt | **32 đạt, 0 lỗi, 0 bỏ qua; 14,74 giây** | Tiến trình `84768` đã kết thúc với mã 0 |

Lỗi `AgentState` có nguyên nhân riêng được chứng minh bởi đồ thị thật: LangGraph
giải quyết chú thích kiểu của hàm định tuyến qua phạm vi toàn cục, trong khi
`AgentState` chỉ được nhập cục bộ hoặc khi kiểm kiểu. Hàm định tuyến đã đổi chú thích
sang `dict[str, Any]`, giữ nguyên hành vi và việc nạp LangGraph khi thực sự cần dùng.

## Kết quả lần kiểm gộp được duyệt

Đã chạy ba tệp:

- `backend/tests/test_langgraph_canonical_context.py`: 10 ca mới dùng SQL và bộ lưu
  LangGraph thật, chỉ mô hình là giả lập.
- `backend/tests/test_orchestrator.py`.
- `backend/tests/test_conversation_context.py`.

Kết quả XML của lần này:

`tmp/langgraph-canonical-verified-84cc42d7f8ad4aca92dc4f831b16ff06/results.xml`

Các ca mới chứng minh: chỉ lấy lịch sử chính của đúng tài khoản và cuộc trò chuyện;
không nạp lại công cụ hoặc câu trả lời từ luồng tạm cũ; không nhân đôi câu hiện tại;
mỗi lần chạy có luồng riêng kể cả khi thử lại cùng mã yêu cầu; xóa bộ nhớ tạm thử
không làm mất lịch sử chính gần đây; chuyển sang đầu vào mới bỏ đúng dữ kiện cũ và
giữ ranh giới đó ở câu hỏi tiếp; các lựa chọn/cấm nguồn vẫn giới hạn công cụ; ngữ cảnh
được chặn ở 32 bản ghi và 64.000 ký tự theo cùng quy tắc Compiler/ADK.

Luồng thực thi mới có dạng `{owner}:{session}:{request}:{uuidhex}`. Đây là bộ nhớ tạm
theo lượt, không phải nguồn lịch sử chính. Sửa đổi không xóa tự động luồng cũ khi
người dùng chưa duyệt dọn dữ liệu, không đổi mô hình hoặc giới hạn sử dụng.

Đã chạy Ruff trên ba tệp mã/thử có thay đổi, kết quả `All checks passed!`.
Chưa có bằng chứng CI hoặc triển khai cho thay đổi này trong báo cáo. Các phép kiểm
ngoại tuyến không chứng minh chất lượng câu trả lời của Gemini thật, không hoàn tất
toàn bộ quy trình lưu giữ/xác nhận/xóa dữ liệu và không thay thế việc công khai sự cố
cục bộ đã nêu ở trên.
