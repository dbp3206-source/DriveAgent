# Design Brief — DriveAgent Study & Work Command Center

## Bổ sung 05/10/2026 — phục hồi bản xem trước hết hạn
Giữ giao diện Fluent và lớp `inline-approval` hiện có; chỉ thêm nút “Tạo lại bản xem trước” khi máy chủ xác nhận thao tác hết hạn. Mỗi lần chuẩn bị lại vẫn phải duyệt riêng, không tự tạo tài liệu. Phạm vi người dùng: quản trị đang nghiệm thu và người dùng có quyền tạo tài liệu. Không đổi màu, bố cục, hình ảnh hoặc quyền Google. Chỉ lưu mã yêu cầu trong bộ nhớ phiên trình duyệt, tách theo tài khoản và câu trả lời; không lưu nội dung hay khóa. Đầu ra là ChatPage và DocumentExportApproval thật; kiểm nhánh hết hạn, chưa rõ kết quả, thành công, tải lại và duyệt lại. Kiểm trình duyệt thật do lượt nghiệm thu chung thực hiện; kiểm máy không thay thế bằng chứng giao diện.

## Bổ sung 04/10/2026 — tìm nhanh trên Drive
Đối tượng hiện hành là người chuẩn bị tư vấn khách hàng theo PRODUCT-FOUNDATION.md. Tại màn hình Drive thật, giữ Fluent, Be Vietnam Pro và màu theo theme; đặt bộ lọc ngay dưới thanh tìm kiếm. Mặc định hoạt động gần đây trước, dùng thứ tự recency của Google; cho phép kết hợp mục đã gắn sao với tất cả/thư mục/tệp. Bộ lọc áp dụng trước phân trang ở Google Drive. Kiểm hình thức bằng dữ liệu giả lập được ghi nhãn trong hồ sơ QA; kiểm truy vấn và ranh giới API bằng bộ kiểm máy chủ. Không sử dụng dữ liệu giả lập làm bằng chứng Google hoạt động thật.

## Cập nhật có thẩm quyền 04/10/2026 — thay minh họa hành trình
Phạm vi lượt này: thay ảnh trong phần câu chuyện của Harness bằng PNG người dùng cung cấp; không tạo lại ảnh, không thay hệ thống thiết kế. Đối tượng và định vị hiện hành theo docs/PRODUCT-FOUNDATION.md, không lấy định vị sinh viên lịch sử bên dưới. Giữ toàn ảnh, tỷ lệ 1672×941, cả hai theme dùng cùng asset. Các số trong ảnh được ghi rõ là minh họa, không phải số đo. Nguồn: codex-clipboard-86efcc92-241c-4214-ae6d-8df9ab4b1242.png do người dùng cung cấp; không suy quyền tái sử dụng ngoài sản phẩm yêu cầu. Đầu ra là giao diện thật và asset frontend/public/harness/veridra-verified-workflow.png; kiểm đóng gói và mở trên URL thật.

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
