# Design Brief

## Audience and viewing context

Người học và lập trình viên mới đang chạy DriveAgent trên máy cá nhân. Họ dùng màn hình desktop để kết nối Google Drive, hỏi đáp tài liệu, xem bộ nhớ và kiểm tra nhật ký; giao diện vẫn phải dùng tốt trên điện thoại để tra cứu nhanh.

## Core message

DriveAgent biến kho tài liệu Google Drive của từng người dùng thành một trợ lý có thể tìm, đọc, trích dẫn, ghi nhớ và giải thích rõ mọi hành động.

## Desired reaction or action

Người dùng phải hiểu ngay dữ liệu nào đã được cấp quyền, agent vừa làm gì, câu trả lời dựa trên tệp nào và có thể thu hồi quyền hoặc xóa bộ nhớ khi cần.

## Source authority

- Các yêu cầu trực tiếp trong cuộc trao đổi với người dùng.
- `Assignment-1-TODO`, `demo-tool-registry` và `rag-demo` ở workspace cha là nguồn tham khảo chức năng.
- `RAG.pdf`, `Memories.pdf`, hai notebook Qdrant và các slide người dùng cung cấp là nguồn kiến thức kiến trúc.
- Tài liệu chính thức Google Drive API, Gemini API, LangGraph và Qdrant là nguồn xác nhận hành vi tích hợp.

## Content hierarchy

1. Trạng thái kết nối và quyền truy cập hiện tại.
2. Trò chuyện có kế hoạch thực thi, nguồn trích dẫn và trạng thái tool.
3. Duyệt, tìm kiếm, đọc và lập chỉ mục tệp Drive.
4. Quản lý bộ nhớ dài hạn theo từng người dùng.
5. Audit log và quản trị vai trò để hệ thống có thể giải thích được.

## Visual territory

Calm technical workspace: sáng sủa, tin cậy, có nhịp điệu kiểu công cụ vận hành nhưng không khô cứng. Màu cobalt làm điểm nhấn duy nhất; xanh lá chỉ dùng cho trạng thái thành công mang ý nghĩa thật.

## Brand and system constraints

- Thương hiệu trung tính: tên sản phẩm DriveAgent, không giả lập nhận diện của Google.
- Fluent UI React v9 là hệ component duy nhất cho product UI.
- CSS variables quản lý theme sáng/tối; mặc định theo hệ điều hành và có nút chuyển thủ công.
- Font chữ: `IBM Plex Sans` nếu tải được, fallback `Segoe UI`, `Arial`, sans-serif. Số liệu và request ID dùng `IBM Plex Mono`, fallback monospace.
- Một hệ bo góc 6/10/14 px; không đặt mọi nhóm nội dung trong card.
- Thiết kế bàn phím trước, focus rõ, WCAG AA, trạng thái loading/empty/error/disabled đầy đủ.

## Anti-goals

- Không dùng gradient tím-xanh, glow, glassmorphism hoặc nền lưới trang trí kiểu AI.
- Không dùng hero marketing, ba card tính năng bằng nhau, status dot trang trí hoặc emoji làm icon.
- Không bịa dữ liệu, khách hàng, chỉ số hoặc ảnh chụp sản phẩm.
- Không che giấu trạng thái OAuth, lỗi tool, thiếu nguồn hoặc phạm vi quyền.
- Không dùng em dash/en dash trong chuỗi hiển thị.

## Output contract

- Ứng dụng React + TypeScript responsive, chạy cùng FastAPI trên local.
- Màn hình desktop, mobile và dark mode đều được kiểm tra trong trình duyệt thật.
- Source code là đầu ra chỉnh sửa được; ảnh QA nằm trong `design-work/qa/screenshots/`.
- Không phụ thuộc Docker để chạy mặc định; Qdrant embedded và SQLite lưu bền vững trên local.

## Reference interpretation

- Mượn từ Fluent 2: khả năng tiếp cận, mật độ phù hợp dashboard, trạng thái rõ và component nhất quán.
- Mượn từ TasteSkill: một visual direction, tiết chế card, typography có chủ đích, chống mẫu AI và pre-flight bắt buộc.
- Không sao chép bố cục hay tài sản nhận diện của bất kỳ template hoặc sản phẩm nào.

## Design Read

Người dùng là developer/learner cần một control room cho tài liệu cá nhân, vì vậy giao diện ưu tiên bằng chứng và khả năng kiểm soát hơn hiệu ứng. Fluent UI chịu trách nhiệm cho các pattern dày dữ liệu; TasteSkill chỉ định nhịp vỏ ứng dụng và tiêu chuẩn chống giao diện đại trà.

## Design dials

- `DESIGN_VARIANCE = 4/10`: bố cục có khu vực chính/phụ lệch nhẹ nhưng giữ tính dự đoán của công cụ nghiệp vụ.
- `MOTION_INTENSITY = 3/10`: chỉ transition phục vụ phản hồi trạng thái, không animation tự chạy.
- `VISUAL_DENSITY = 6/10`: đủ chặt cho danh sách tệp và audit log, vẫn có khoảng thở cho người học.
