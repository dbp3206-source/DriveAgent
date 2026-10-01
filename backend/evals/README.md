# Evaluation Harness

DriveAgent tách các phép đo để tránh biến một con số đẹp thành kết luận sai:

| Lớp đánh giá | Đang đo bằng gì | Ý nghĩa |
|---|---|---|
| Routing regression | `golden_routes.json` + `scripts/evaluate.py` | Intent có đi đúng tool và đúng ranh giới direct/agent hay không |
| Output evaluator regression | `golden_output_quality.json` | Bộ chấm có phân biệt đúng ví dụ dương/âm và các lỗi citation hay không |
| Reference-answer contracts | `golden_answer_contracts.json` | Câu trả lời mẫu có đạt answer key, section, bảng/checklist và claim–source binding hay không |
| Tool execution | Audit log thật | Tỷ lệ hoàn tất, denied/error và latency P50/P95 |
| Human feedback | Nút Hữu ích/Chưa ổn trên từng câu trả lời | Tín hiệu trực tiếp từ đúng user |
| RAG retrieval | Test fixture có source/chunk kỳ vọng | Cách ly user, freshness, idempotency và truy xuất đúng tài liệu |
| Grounding/citation | Test + nghiệm thu live với tệp QA | Câu trả lời có bám nội dung và link đúng nguồn hay không |
| Agent trajectory | Execution.py tests + execution trace thật | ADK handoff, tool governance, retry/recovery và giới hạn vòng lặp |
| Gate 2 golden corpus | `golden_gate2.json` + source hashes | 60 task (40 development/20 holdout), PDF/Sheet, refusal/ask-back và rubric intent/output |

Chạy bộ regression không dùng quota:

```powershell
.\backend\.venv\Scripts\python.exe scripts\evaluate.py
```

Kiểm tra cấu trúc và hash nguồn của Gate 2:

```powershell
.\backend\.venv\Scripts\python.exe scripts\validate_gate2.py --strict-sources
```

Kiểm tra thêm độ đầy đủ của answer key (gate2.18: 37/37 citation cases có
binding; 20 PDF anchors đúng trang và phép tính Sheet được đối chiếu offline):

```powershell
.\backend\.venv\Scripts\python.exe scripts\validate_gate2.py --strict-sources --strict-answer-keys
```

`golden_gate2.json` được sinh bằng `backend/evals/build_gate2.py` từ các nguồn QA đã
được chỉ định. Khi tạo manifest mới trên máy khác, đặt
`DRIVE_AGENT_EVALUATION_PDF_PATH` tới file `Evaluation-Harness.pdf`; nếu bỏ trống,
builder dùng đường dẫn nguồn trong manifest hiện có (nếu còn truy cập được). Workbook tổng hợp QA nằm bền vững tại
`backend/evals/fixtures/budget.xlsx`; builder chỉ tạo khi chưa có và kiểm tra cấu trúc
trước khi khóa hash. Manifest lưu đường dẫn tuyệt đối của nguồn hiện dùng; các câu hỏi local dựa trên nguồn nêu rõ tên file để không nhầm với
tài liệu khác trong tài khoản. Bản gate2.18 phân bố 20 holdout qua cả PDF, Sheet, local,
output và safety. Runner từ chối regrade khi version, câu hỏi, answer key hoặc hash nguồn
không khớp và có fingerprint; artifact lịch sử thiếu fingerprint không được tái gán lại.
Manifest không sao chép nội dung private; chỉ lưu hash và vị trí bằng
chứng. Validator strict chứng minh dataset không bị thiếu hoặc stale, **không** chứng
minh model live đúng. Hai trường `live_model_checked=false` và
`human_review_required=true` phải được giữ cho đến khi chạy candidate thật, chấm mù
development/holdout và lưu biên bản người duyệt.

Runner live chỉ ghi nhận `live_model_checked` khi response trace có event `stage=model`
với trạng thái gọi thành công/fallback; tool/template route hoàn tất không được tính là
model call. Runner thoát mã `1` khi quality gate fail và `2` khi ca lỗi/thiếu/chạy dừng
sớm. Mỗi kết quả mới lưu fingerprint câu hỏi, answer key và hash nguồn. Regrade cũ thiếu
fingerprint phải được giữ làm lịch sử, không được tuyên bố đã kiểm chứng source-stable.
Biên nhận Workspace có thể được dùng lại sau khi đổi phiên bản rubric nếu tên và SHA-256
của từng nguồn trong manifest vẫn khớp chính xác; báo cáo mới ghi lại phiên bản của receipt.

Quality dashboard chỉ hiển thị số liệu đã quan sát. Routing, evaluator regression và
reference-answer contracts là ba lớp khác nhau. Không lớp nào tự chứng minh độ đúng
của model live. Độ đúng câu trả lời cần chạy candidate do model sinh ra trên tài liệu
thật đã gắn answer key; LLM-as-judge chỉ nên là tín hiệu bổ sung và phải được hiệu
chỉnh với human review.

Output rubric v1.3.0 vẫn là bộ hồi quy nhỏ, không phải chứng nhận chất lượng mô hình.
`passed/total` nghĩa là bộ ví dụ cố định đang xác nhận evaluator phân loại đúng cả ca
dương lẫn ca âm; nó không có nghĩa mọi câu trả lời thật đều đúng. Với `expected_facts`,
so khớp dùng ranh giới token đầy đủ, nên fact `4` không thể được thỏa mãn bởi `14`,
`4,5` hoặc một chuỗi dài hơn.

Khi một ca bắt buộc kiểm citation, answer key phải khai báo `expected_claim_citations`:

```json
[
  {
    "claim": "DA-LOCAL-2026",
    "citation_index": 1,
    "file_id": "qa-doc",
    "evidence_fact": "DA-LOCAL-2026"
  }
]
```

Evaluator kiểm tra claim có trong câu trả lời, marker nằm cùng dòng, citation trỏ đúng
`file_id`, và snippet chứa fact đã gắn nhãn. Đây là kiểm tra binding bằng answer key,
**không phải** bộ giải entailment: việc đoạn trích có thật sự chứng minh toàn bộ claim,
paraphrase có đúng hay không vẫn cần người kiểm duyệt/đánh giá ngữ nghĩa có hiệu chuẩn.
Nếu thiếu binding, ca bắt buộc citation sẽ fail closed thay vì được chấm đạt chỉ vì có
`[1]`.

`golden_answer_contracts.json` là bộ hợp đồng câu trả lời tham chiếu. Mỗi case phải có
ít nhất một ràng buộc kiểm được: fact/forbidden term, section bắt buộc, bảng Markdown,
số bullet/bước, hoặc claim–source binding. `16/16` ở suite này chỉ nói rằng câu trả lời
mẫu và rubric nhất quán; trường `live_model_checked` luôn là `false` cho đến khi có
một runner riêng thực sự gọi model và các tích hợp đã xác thực.

## Quy tắc thêm case

1. Không đưa dữ liệu cá nhân hoặc secret vào fixture.
2. Mỗi case có `id`, câu hỏi, tool kỳ vọng và cờ `expected_direct`.
3. Thêm case cho mỗi bug routing trước khi sửa để chống tái phát.
4. Không đổi expected output chỉ để làm test xanh; phải giải thích thay đổi nghiệp vụ.
5. Với RAG, lưu source/chunk kỳ vọng và kiểm tra citation, không chỉ so khớp câu chữ.

Nội dung đánh giá bám theo bài giảng Evaluation Harness: golden dataset,
regression, task success, RAG/agent evaluation và human feedback được coi là các
lớp riêng thay vì gộp thành một điểm duy nhất.
