# Hồ sơ kiểm chứng Veridra

Mục tiêu: giúp người đọc tự kiểm tra khả năng và giới hạn của dự án, không gộp
mọi phép kiểm thành một điểm chất lượng gây hiểu nhầm. Hồ sơ này không sửa mã sản
phẩm, không gọi thêm Gemini, không triển khai lại và không dùng dịch vụ trả phí.

## Ba lớp kiểm chứng

| Lớp | Nguồn công khai | Kết quả và ý nghĩa |
|---|---|---|
| Chất lượng và chọn công cụ | [Bộ chuẩn có sẵn](../../backend/evals/README.md), [kết quả nội bộ](evidence/offline-regression-20261011.json) | 200/200 kiểm hồi quy: 12 chọn công cụ, 12 phân loại chất lượng, 16 hợp đồng câu trả lời, 160 biến thể. Không đo chất lượng mô hình chạy thật. |
| Bảo mật và kiểm soát hành động | [Ma trận kiểm](HARNESS-COVERAGE.md), [biên nhận](evidence/security-governance-20261011.json) | 78/78 kiểm được chọn đạt, không lỗi hoặc bỏ qua. Dữ liệu và dịch vụ mô phỏng; không phải kiểm xâm nhập bản đang chạy. |
| Quy trình sản phẩm chạy thật | [Báo cáo 10 ca](DEMO-REPORT-20261011.md), [kết quả có cấu trúc](evidence/demo-results-20261011.json) | 3 đạt, 6 đạt một phần, 1 chưa đạt; gồm nhiều màn hình và quy trình, không chỉ trò chuyện. |

Không cộng 200, 78 và 10 thành một tỷ lệ chung. Các lớp dùng đối tượng, đơn vị
đo và điều kiện chạy khác nhau. Không đổi bước chưa chạy thành đạt.

## Bộ dữ liệu chuẩn

- [Bộ demo công khai](golden/README.md): 5 tệp giả lập, 10 ca, câu hỏi nối tiếp,
  tiêu chí và đáp án độc lập.
- [Các bộ dữ liệu kỹ thuật hiện có](../../backend/evals/): chọn công cụ, chất
  lượng câu trả lời mẫu, dẫn nguồn, kiểm an toàn và sáu tình huống doanh nghiệp.
- Bộ `golden_gate2.json` có nguồn ngoài kho và thông tin vị trí/hash. Không có
  quyền phân phối lại tài liệu đó trong gói này. Kiểm nguồn nghiêm ngặt chỉ chạy
  khi người kiểm có đúng tệp và quyền sử dụng; không tuyên bố tái lập được toàn bộ
  bộ này chỉ bằng cách tải kho mã.
- [Danh mục và mã băm](golden/manifest.json) khóa các đầu vào của bộ demo công
  khai. Đáp án được xác lập độc lập, không lấy câu trả lời của mô hình làm chuẩn.

## Chạy lại kiểm nội bộ không dùng hạn mức mô hình

Từ thư mục gốc của kho mã, sau khi hoàn thành [cài đặt](../START_LOCAL.md):

```powershell
.\backend\.venv\Scripts\python.exe scripts\evaluate.py
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_security.py backend/tests/test_oauth_callback.py backend/tests/test_five_user_isolation.py backend/tests/test_framework_security.py backend/tests/test_registry.py backend/tests/test_document_policy.py backend/tests/test_document_tool_execution.py backend/tests/test_relational_remote_actions.py backend/tests/test_protocols.py backend/tests/test_protonx_hardgates.py -q
```

Để lưu biên nhận mới, không ghi đè biên nhận lịch sử đã công bố:

```powershell
.\backend\.venv\Scripts\python.exe scripts\evaluate_release_offline.py --output tmp\offline-regression-new.json
```

Các lệnh trên dùng cấu hình/dữ liệu thử theo từng kiểm. Không yêu cầu khóa Gemini
hoặc đăng nhập Google và không được tính như những lượt đã chạy trên Render.

## Chạy thật và quyền riêng tư

Đọc [hướng dẫn bộ demo](golden/README.md) trước khi thao tác. Chỉ dùng tài khoản
và dữ liệu thuộc quyền của mình. Xem thư, lịch và gửi phần liên quan đến mô hình
cần chấp thuận riêng. Ghi ra Google cần quyền và bước duyệt đúng nội dung.

Báo cáo công khai rút gọn từ bằng chứng đã chạy ngày 11/10/2026. Định danh yêu cầu,
URL Google Doc, ảnh tài khoản, thư và tệp xuất riêng không được phân phối. Việc
loại định danh không biến báo cáo thành bằng chứng độc lập để người ngoài đối chiếu
mọi ảnh gốc; giới hạn này được giữ công khai.

Mã nguồn nền của lần kiểm nội bộ: `8e74fc46c35220403a12f19490c0e17994133a6b`.
Bản này chỉ thêm hồ sơ; không khẳng định mã nguồn nền là mã đã xác minh ở từng
lượt chạy thật trong báo cáo. [Kiểm GitHub của bản sửa mã trước đó](https://github.com/dbp3206-source/DriveAgent/actions/runs/38064377009)
là bằng chứng riêng, không phải kết quả chạy lại hôm nay.
