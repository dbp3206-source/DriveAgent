# Kiểm tính năng thông báo linh vật — 14/10/2026

## Phạm vi và nguồn
Yêu cầu: gửi Chat rồi xem trang khác; khi có phản hồi, linh vật báo và mở đúng hội thoại. Dùng hệ thống thiết kế Veridra hiện có, không tạo ảnh/nhân vật mới. Nguồn: App.tsx, ChatPage.tsx, AppShell.tsx, MascotAssistant.tsx, bộ theo dõi tác vụ và page-mascot 0.1.0 đã cài. Brief/outline tại `design-work/design-brief.md`, `design-work/content-outline.md`.

## Thực hiện
- Kết quả dựa trên sự kiện tác vụ thật, không suy ra thành công từ `busy=false`.
- Tách đang chạy, hoàn tất, bản nháp cần kiểm, lỗi, đã dừng và chưa xác nhận. Lỗi mạng chưa chứng minh tác vụ thất bại thì không báo thành công hoặc tự gửi lại.
- Thông báo chưa xem vẫn hiện khi thu nhỏ; có dấu và nút xem lại. Đóng bong bóng không xóa dấu; mở đúng cuộc trò chuyện mới xác nhận đã xem. Tải lại giữ metadata theo tài khoản/phiên tab, không lưu câu hỏi/đáp án trong thông báo.
- Chat tiếp tục theo dõi khi đổi khu vực. Sau tải lại trang khác, khôi phục theo mã tác vụ SQL, kể cả tác vụ đã xong giữa reload và truy vấn pending. Đăng nhập khác không nhận metadata của tài khoản trước.
- Tôn trọng tắt linh vật; thanh đầu trang là dự phòng. Không âm thanh, xin quyền thông báo hệ thống, gọi AI, đọc nguồn hoặc ghi Google để thông báo.
- Gợi ý trang chỉ khi người dùng tương tác; bỏ các lời khẳng định chưa kiểm như “Drive đã đồng bộ” hoặc “tài liệu đã nạp”. Giữ chọn sáu linh vật, mở Chat, chọn tài liệu/mẫu và xem hạn mức.

## Bằng chứng
- Kiểm toàn bộ giao diện ban đầu: **204/204 đạt**. Sau kiểm Render, thêm kiểm hồi quy CSS ở màn hẹp: **205/205 đạt**, không bỏ qua (session 53861, 15.788 giây). Riêng bộ trạng thái/metadata/thành phần linh vật là 12 ca; kiểm CSS là một ca riêng, không cộng các mẫu số trùng.
- ESLint đạt; TypeScript/Vite dựng cuối sau CSS thành công, 11,28 giây (session 41275, exit 0). Ruff helper QA và diff check đạt.
- Trình duyệt thật qua `mcp__cua_repl.js`, Vite 5175/FastAPI 8003, tài khoản giả lập không có khóa. Helper có cờ `--mascot-check` trì hoãn tác vụ giả lập 12/45 giây; dùng hàng đợi/SQL/UI thật nhưng **không phải thử chất lượng Gemini**.
- Máy tính 1280×720: gửi phép tính, chuyển Home, nhận notice hoàn tất; thu lại thành dấu, mở lại bằng Enter; tải lại giữ notice; nút mở đúng hội thoại có đáp án 6.0. Bản nháp giả lập hiện “Bản nháp cần kiểm tra”; không có khóa hiện “Yêu cầu chưa hoàn tất”, không báo hoàn tất.
- Điện thoại: công cụ viewport không thay kích thước tab (DOM vẫn 1280), nên không dùng ảnh đó làm bằng chứng điện thoại. Fallback: iframe cùng nguồn chạy **ứng dụng thật 390×600**, không phải mockup. DOM xác nhận innerWidth=390, innerHeight=600, scrollWidth=380; notice left=58/right=368/top=314,5/bottom=514,4 nằm trong khung. Nhận notice khi ở Home; Enter mở Chat và bỏ dấu. Khung 390×844 trước đó mở Chat và trả kết quả nhưng ảnh cuối dùng 390×600 để thấy đủ thông báo trong viewport thanh bên.
- Hỗ trợ giảm chuyển động trong CSS; thư viện page-mascot có chính sách tương ứng. Chưa giả lập tùy chọn hệ điều hành giảm chuyển động bằng công cụ này; không tuyên bố đã kiểm trên thiết bị thật.
- Gợi ý Home mở bằng nút “Cần mình hỗ trợ?” với Enter; có mở Trò chuyện/Chọn tài liệu, không tự gửi. Nhật ký console tab kiểm cuối không có lỗi (`dev.logs` mức error trả `[]`); không dùng kết quả đó để phủ nhận lỗi HMR trước reload hoặc kết nối khi cố tình dừng máy chủ QA.

Ảnh: `screenshots/desktop-completed.jpg`, `desktop-incomplete.jpg`, `desktop-failed.jpg`, `mobile-completed.jpg`, `mobile-context-help.jpg`. `viewport-override-not-applied.jpg` là bằng chứng giới hạn công cụ, không phải mobile pass. Nguồn HTML khung thử lưu ở `qa/mobile-check-source.html`; bản chạy local ở `frontend/tmp/mascot-mobile-check.html` bị loại khỏi Git. Ảnh chỉ dữ liệu giả lập.

## Lỗi trong quá trình kiểm và sửa
Lần đầu bộ bootstrap không mock hook mới: hai ca lỗi “useChatActivity is not a function”, sửa harness rồi 204/204 đạt. ESLint phát hiện callback trước khai báo/memoization; chuyển callback lên trước listener. TypeScript phát hiện optional chain không chứng minh current khác null; thêm kiểm rõ null. Không tắt kiểm. Khởi động nhầm lúc cổng QA còn dùng bị từ chối; dừng đúng tiến trình QA sở hữu rồi chạy lại. Ruff lần đầu cwd frontend làm sai đường config; chạy lại từ repo thành công. CUA có timeout quan sát và click iframe không tìm node; đọc lại trạng thái, dùng bàn phím, không sửa ứng dụng cho lỗi công cụ.

## Điểm và giới hạn
Chấm riêng tính năng/bố cục đã kiểm: đúng nội dung 19/20, riêng ngữ cảnh 17/20, tổ chức 13/15, chữ 13/15, bố cục 12/15, kỹ thuật 12/15 = **86/100**. Không phải điểm toàn sản phẩm. Nguồn/mã editable React/CSS còn nguyên; không có deliverable hình thay cho ứng dụng.

Đã triển khai commit `00def8a3ab44c24730a3bcd2331540ef46d43f37` sau CI #138 thành công: ảnh `sha256:481b0515062f8502386fe6e2e09efded46aa5d03d961e48e7792ede9709b3fb1`, lần triển khai `dep-db7h8549v7es73c2ol70` báo Deploy succeeded/Live, 1m51s, nhật ký Live 12:35:03 GMT+7 ngày 14/10/2026. Registry công khai trả HTTP 200 cho tag full commit và digest trên; config amd64/linux, không có nhãn revision/source nên không tuyên bố đã kiểm nhãn commit. Đọc nhật ký GitHub step 23 trả “Error:”; tải log archive timeout 20000ms. Không tải artifact ảnh 333MB để né lỗi; dùng manifest registry công khai, không đọc khóa.

URL thật: phép tính đầu 2.5+3.5 trả 6.0 ngay khi còn ở Chat nên không báo chưa đọc, đúng hành vi. Phép tính tiếp 4.5+2.5: gửi rồi chuyển Home trong cùng lượt điều khiển, quan sát đang xử lý, sau đó linh vật báo có câu trả lời mới. Đóng bong bóng giữ dấu 1; Enter mở lại; reload Home vẫn giữ thông báo. Bấm Xem câu trả lời mở chính hội thoại chứa hai phép tính, đáp án mới 7.0; dấu đã đọc được xóa. Console error cuối trả `[]`. Hạn mức giao diện trước/sau đều 4/16; đây là câu trả lời tính xác định, không gọi Gemini hoặc tạo chỉ mục, không đọc nguồn riêng. Ảnh `cloud-completed.jpg`, `cloud-opened-conversation.jpg`, `render-live.jpg`.

Kiểm ảnh cloud phát hiện thanh thông báo phụ bị trống ở màn hẹp: CSS mobile cũ `.topbar-chat-indicator > span` clip và đặt span tuyệt đối 1×1, trong khi bố cục mới dùng cả dòng. Sửa đúng cascade bằng quy tắc mobile có phạm vi, reset clip/position/width/height/max-width. Kiểm ứng dụng thật 390×600 tại máy cho span tiêu đề rộng 104.48px/cao 20px, clip=auto, position=static; ảnh `mobile-header-fixed.jpg`. Build lại thành công 8.64s (session 42349). Bản sửa CSS này đang chờ ảnh phát hành kế tiếp; không dùng ảnh local để chứng minh bản CSS đã lên Render.

Chưa gộp main. Chỉ hoạt động khi ứng dụng/tab vẫn mở (hoặc mở lại để lấy trạng thái); không phải thông báo đẩy khi đóng trình duyệt. Một tác vụ tại một thời điểm theo ràng buộc máy chủ hiện có, không hứa hàng đợi thông báo nhiều tác vụ. Không tự ký nghiệm thu Production.

## Tài sản/giấy phép
Không thêm dependency hoặc asset bên ngoài. Đã đọc README/types/LICENSE của page-mascot 0.1.0 đang cài: MIT, Kamran Ahmed; giữ package/license, không vẽ lại hoặc tái phát hành thư viện. Dùng sprites có sẵn dự án và Fluent icons. Không dùng skill tạo thú trong ChatGPT vì đây là linh vật của ứng dụng Veridra, không phải ChatGPT Pet.
