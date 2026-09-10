# Design Brief — DriveAgent Study & Work Command Center

## Audience and viewing context
Sinh viên và người dùng non-tech làm việc local trên desktop, tablet hoặc mobile. Dữ liệu được tách theo người dùng; các thao tác ghi ra Google luôn cần người dùng xem trước và xác nhận.

## Core message
DriveAgent giúp người dùng tìm, hiểu, tạo và kiểm chứng tài liệu trong một không gian làm việc có kiểm soát.

## Desired reaction or action
Người dùng biết nên bắt đầu từ đâu, hiểu Agent đang dùng dữ liệu và công cụ nào, rồi tự tin duyệt hoặc từ chối một hành động bên ngoài.

## Source authority
Source hiện tại trong `backend/app` và `frontend/src`, test suite trong `backend/tests`, dữ liệu thật chỉ dùng cho nghiệm thu có kiểm soát. Không dùng nội dung minh họa giả làm số liệu sản phẩm.

## Content hierarchy
1. Công việc người dùng muốn hoàn thành.
2. Câu trả lời và bằng chứng.
3. Hành động tiếp theo có kiểm soát.
4. Giải thích Context, RAG, Tool, Orchestration, Multi-Agent/Protocols và Evaluation khi cần.

## Visual territory
Một “study desk” số yên tĩnh: bề mặt sâu nhưng không u tối, typography rõ ràng, điều hướng có nhãn, control bo tròn vừa đủ và khoảng trắng dùng để dẫn mắt. Trạng thái kỹ thuật được diễn giải bằng ngôn ngữ đời thường; sơ đồ harness chỉ xuất hiện khi người dùng muốn tìm hiểu sâu.

## Brand and system constraints
Giữ Be Vietnam Pro, Fluent icons và khả năng đổi theme. Component phải dùng token thống nhất, focus ring rõ, vùng bấm tối thiểu 40px và không dựa vào màu để truyền đạt trạng thái. Mobile là một luồng riêng, không phải desktop bị thu nhỏ.

## Anti-goals
Không dùng dashboard executive chung chung, glow xanh, glassmorphism, card cho mọi nhóm nội dung, emoji thay icon, KPI giả, quota hard-code hoặc component cộng đồng chỉ vì bắt mắt.

## Output contract
Ứng dụng React/FastAPI thật, không phải mockup. Mỗi vòng phải build, chạy trong trình duyệt thật và lưu bằng chứng QA theo cấu trúc `design-work/qa`. Không đổi secret hoặc xóa dữ liệu người dùng.

## Reference interpretation
Nguồn chính cho component là https://ui.shopviet247.xyz/elements. Mượn sự rõ ràng của trạng thái tương tác, hình học mềm và control HTML/CSS đơn giản; không sao chép nguyên hệ màu, animation phô trương hay tên component ngẫu nhiên. Chỉ dùng source cụ thể sau khi kiểm tra trang tác giả và license. Component “Hard pig 16” của Boryana trên Uiverse được khảo sát như một ví dụ input có icon, MIT; DriveAgent sẽ diễn giải lại bằng token và icon Fluent hiện có thay vì chép nguyên SVG/CSS.
