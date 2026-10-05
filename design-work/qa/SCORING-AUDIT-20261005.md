# Đối soát cách chấm và bộ nguồn — 05/10/2026

## Phiên bản và phạm vi

Mã nền: `c755ecd11606a7be5f8612d7c6966f63a77dbfce`. Lượt này không gọi Gemini, Google hoặc thao tác trong phiên đăng nhập cloud. Các sửa hiện có trong lượt này chỉ là tài liệu khôi phục và báo cáo này. Không tạo điểm chất lượng tổng.

## Kiểm tra đã thực hiện

Chạy bằng `backend/.venv/Scripts/python.exe`:

```text
-m pytest backend/tests/test_protonx_scoring.py backend/tests/test_protonx_hardgates.py backend/tests/test_gate2_manifest.py backend/tests/test_evaluation.py -q
67 passed in 20.01s

scripts/validate_gate2.py --strict-sources --strict-answer-keys
exit code 0
```

Bộ nguồn `golden_gate2.json`, phiên bản `2026-09-20.gate2.27`: 60 ca, gồm 40 ca phát triển và 20 ca giữ riêng; 30 ca PDF/bảng; 10 ca từ chối hoặc hỏi lại. 37 ca cần dẫn chứng đều có ánh xạ nhận định–nguồn. Ba nguồn được tìm thấy và checksum khớp; không nguồn thiếu hoặc cũ so với manifest. Đây là kiểm nguồn/đáp án, **không phải chạy 60 câu hỏi thật**.

## Kết luận về cách chấm

- `scripts/protonx_scoring.py` chỉ chứng nhận cấu trúc; không suy ra nhận định đúng từ nhãn nguồn. Trường xác minh nội dung và an toàn đều giữ chưa kiểm chứng.
- `task_success`, `passed_cases` và `unauthorized_side_effects` không được gán thành công hoặc số 0 khi chưa có bằng chứng.
- Mâu thuẫn được báo đúng không tự làm ca thất bại. Ví dụ 12 nguồn/42 giây đã tách khỏi ngưỡng nghiệm thu trong `protonx_company_benchmark.json`.
- Đánh giá lại đầu ra lịch sử giữ nguyên tệp gốc và không biến thành lần chạy mới. Phép thử này dùng dữ liệu giả lập, không đọc lại nội dung thư thật.
- Các phép thử vai trò agent và báo cáo dùng thành phần giả lập hoặc gọi cục bộ. Chúng không chứng minh bảy agent đã thực hiện một chuỗi cloud xuyên suốt.

## Phần chưa đủ để đóng A1/A3/F1

### Sửa đường xuất số đo sau khi rà soát

`publish_business_benchmark.py` trước đây đối chiếu tập mã ca nhưng chưa kiểm số bản ghi; một ca trùng có thể làm mẫu số bị tăng. Báo cáo khác phiên bản/câu hỏi, điểm thiếu và thời gian thiếu cũng chưa được kiểm nghiêm ngặt trước khi xuất. Đã bổ sung kiểm mỗi ca đúng một lần, bộ mẫu không rỗng, phiên bản/câu hỏi khớp, model được chỉ định và điểm/thời gian là số hữu hạn hợp lệ; không thay dữ liệu thiếu bằng 0.

Kiểm lại: `python -m pytest backend/tests/test_business_benchmark_publication.py backend/tests/test_harness_direct.py -q` đạt **20 phép thử trong 8,82 giây**; Ruff trên hai tệp thay đổi đạt. Đây là kiểm đường xuất/đọc số đo bằng dữ liệu giả lập, không phát hành số đo mới và không gọi model. Chưa có bằng chứng người dùng thực tế từng bị ảnh hưởng bởi lỗi ca trùng.

Bộ 60 ca với ba nguồn không phải bộ 24 tác vụ phát hành gồm sáu doanh nghiệp, sáu tài liệu, sáu chuỗi phối hợp và sáu câu hỏi cập nhật. Kiểm nguồn thành công không chứng minh cả sáu PDF của kế hoạch có manifest, đáp án theo trang và lượt chạy thật. Còn cần đối chiếu nội dung nguồn với nhận định, hoàn thành W1–W3, bước duyệt–thực hiện–đọc lại và chấm kết quả thật cùng bản phát hành. Không đóng các điều kiện này bằng kết quả tự động trên.
