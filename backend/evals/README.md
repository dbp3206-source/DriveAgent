# Evaluation Harness

DriveAgent tách các phép đo để tránh biến một con số đẹp thành kết luận sai:

| Lớp đánh giá | Đang đo bằng gì | Ý nghĩa |
|---|---|---|
| Routing regression | `golden_routes.json` + `scripts/evaluate.py` | Intent có đi đúng tool và đúng ranh giới direct/agent hay không |
| Tool execution | Audit log thật | Tỷ lệ hoàn tất, denied/error và latency P50/P95 |
| Human feedback | Nút Hữu ích/Chưa ổn trên từng câu trả lời | Tín hiệu trực tiếp từ đúng user |
| RAG retrieval | Test fixture có source/chunk kỳ vọng | Cách ly user, freshness, idempotency và truy xuất đúng tài liệu |
| Grounding/citation | Test + nghiệm thu live với tệp QA | Câu trả lời có bám nội dung và link đúng nguồn hay không |
| Agent trajectory | Execution.py tests + execution trace thật | ADK handoff, tool governance, retry/recovery và giới hạn vòng lặp |

Chạy bộ regression không dùng quota:

```powershell
.\backend\.venv\Scripts\python.exe scripts\evaluate.py
```

Quality dashboard chỉ hiển thị số liệu đã quan sát. `12/12` là routing accuracy,
không phải độ đúng tổng thể của AI. Độ đúng câu trả lời cần mở rộng golden dataset
theo tài liệu thật của từng nhóm; LLM-as-judge chỉ nên là tín hiệu bổ sung và phải
được hiệu chỉnh với human review.

## Quy tắc thêm case

1. Không đưa dữ liệu cá nhân hoặc secret vào fixture.
2. Mỗi case có `id`, câu hỏi, tool kỳ vọng và cờ `expected_direct`.
3. Thêm case cho mỗi bug routing trước khi sửa để chống tái phát.
4. Không đổi expected output chỉ để làm test xanh; phải giải thích thay đổi nghiệp vụ.
5. Với RAG, lưu source/chunk kỳ vọng và kiểm tra citation, không chỉ so khớp câu chữ.

Nội dung đánh giá bám theo bài giảng Evaluation Harness: golden dataset,
regression, task success, RAG/agent evaluation và human feedback được coi là các
lớp riêng thay vì gộp thành một điểm duy nhất.
