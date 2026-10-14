# Kiểm bản ứng viên — 13/10/2026

## Kết luận đúng phạm vi

**Cập nhật 14/10:** kết luận chuẩn bị bên dưới được giữ theo thời điểm chạy. 410966a sau đó đã qua CI/Live; kiểm cloud phát hiện lớp ẩn vẫn sót, bộ kiểm số học đọc nhầm số nguồn/ô bảng, và tài liệu công khai bị định tuyến sai. Không dùng lần kiểm tại máy trước để bỏ qua lỗi cloud. Ba lỗi được sửa gộp; kiểm liên quan 276/276, giao diện 192/192, lint/build đạt. Kiểm trình duyệt bản sửa: hộp xem → Chat có `rootHidden=null`, 0 hộp thoại, đúng câu nhập và Tab hoạt động; đóng thường cũng giải phóng lớp ẩn. Bằng chứng đầy đủ/trạng thái T01–T10 ở `docs/verification/internal-assistant/RESULTS-20261014.md`. Các sửa mới chưa được gọi là đã triển khai cho tới khi có CI/digest/Live tương ứng.

Phần sửa cốt lõi và giao diện bắt đầu đã có kiểm tại máy. **Chưa nghiệm thu Production:** chưa có CI PostgreSQL và ảnh triển khai cùng mã, chưa chạy đủ T01–T10/nguồn thật/khôi phục/vận hành. Không dùng số kiểm đơn vị để thay điểm chất lượng đầu ra Gemini hoặc giá trị kinh doanh.

Mã nền: `a026db6`; bản ứng viên là thay đổi đang làm sau mã nền này. Hồ sơ hiện hành: `docs/PRODUCTION-EXECUTION-20261013.md`, `docs/ASSISTANT-CONTRACT.md`, `docs/verification/internal-assistant/testcases.json` và kế hoạch ngày 13/10 ở workspace cha. Các tệp đầu vào A/B/C đều giả lập.

## Công cụ và nguồn thiết kế

- Một nguồn thiết kế: hệ thống Veridra hiện có. Không gọi Hallmark, trình tạo ảnh hoặc tạo mẫu độc lập. Mã React/Fluent UI là đầu ra chỉnh sửa được, không phải ảnh mô phỏng.
- Kiểm trình duyệt thật bằng `mcp__cua_repl.js`, Codex In-app Browser: snapshot, thao tác nút/ô nhập, file chooser, đọc DOM, kiểm viewport và chụp JPEG.
- Kiểm mã và hồi quy bằng Python của `backend/.venv`, Ruff, pytest/coverage, Node/npm/TypeScript/Vite thực. Các lệnh tiêu biểu ở `command-log.txt`.
- Những bước trước trong cùng đợt dùng Supabase MCP chỉ đọc trạng thái/schema/quyền; không sửa DB cloud. Hướng dẫn Supabase giúp giữ schema riêng và phép thử migration trong DB CI riêng, không mở quyền API để loại cảnh báo.

## Bằng chứng kỹ thuật

| Kiểm | Kết quả | Điều không được suy diễn |
|---|---|---|
| `backend-regression.xml` | 1.624 ca: 1.609 đạt, 15 bỏ qua, 0 lỗi/0 thất bại, 374,763 giây | 15 bỏ qua chưa đạt; chạy trước bổ sung ca migration PostgreSQL mới |
| Coverage | 12.448/14.268 câu lệnh, 87,24% | Không phải độ chính xác câu trả lời; tổng mã không đồng nghĩa từng lớp đều trên 85% |
| Hồi quy ngoại tuyến | 12/12 định tuyến, 12/12 bộ chấm, 16/16 hợp đồng, 160/160 biến thể đối kháng | 0 lượt mô hình, không chứng minh khả năng suy luận thật |
| Kiểm giao diện đơn vị | 190/190 đạt | Không thay kiểm dịch vụ Google thật |
| Kiểm mã/dựng cuối | ESLint, TypeScript và Vite đạt; Vite 5,01 giây sau thay đổi cuối | Không phải thời gian mở trang hoặc kiểm ảnh Docker |
| Tính toàn vẹn bộ mới | 10 ca, 4 tệp, số học/đường dẫn/độ phủ đúng; 9 lượt dự kiến + 2 dự phòng | Chưa có kết quả T01–T10 thật; chưa phê duyệt tự động mọi lượt |
| Thu hồi phiên | Cookie sao chép/cũ/đã đăng xuất bị từ chối; tài khoản khác không bị thu hồi theo, kiểm với DB SQLite thật | PostgreSQL và cookie cloud phải kiểm sau triển khai |
| Drive | Hồi quy tái hiện sắp xếp với tìm toàn văn; phân biệt truy vấn/quyền/phiên/cấu hình/hạn mức | Chưa đọc Drive thật bằng bản ứng viên |

XML và kết quả thô nằm ở `qa/validation/` tại máy, được bỏ qua khỏi Git. Các tổng có chồng lặp; không cộng thành một tỷ lệ nghiệm thu sản phẩm.

## Kiểm giao diện và luồng thật tại máy

Môi trường riêng: backend `127.0.0.1:8003`, frontend `127.0.0.1:5175`; không đọc `.env`, không OAuth/Gemini, không DB/tệp thật. Chặn phân giải mạng ngoài loopback; dữ liệu ở `tmp/production-ui-20261013`. Cơ chế tìm kiếm dự phòng tại máy không chứng minh chất lượng tìm kiếm ngữ nghĩa cloud.

1. Trang chủ: cả năm gợi ý đi vào cùng ô soạn, không tự gửi; không có lịch sử câu trả lời được tạo giả. Giữ đường tự nhập.
2. Bố cục: desktop, 390×844 và 820×900; chiều rộng nội dung không vượt viewport ở màn đã kiểm, ảnh quan sát không vỡ. Đóng menu bằng Escape và trả tiêu điểm về nút mở.
3. Tệp: nhập `A-bao-gia.md` bằng file chooser; API lưu thành công, UI hiện 1.678 ký tự; xem nhanh có đủ ba báo giá/Tre/Sen/Trúc và điều kiện giả lập. Chuyển sang trò chuyện giữ `/local A-bao-gia.md`, không tự gửi.
4. Bộ nhớ: tạo riêng `IA-QA-20261013`, sửa nội dung, cất (0 mục đang dùng), khôi phục; bản sửa được giữ. Chưa xóa vĩnh viễn qua UI và chưa chấm truy xuất/quên trong hội thoại cloud mới.
5. Mẫu: lưu `ia_qa_project_meeting` v1, nạp “Mộc An — bộ hướng dẫn thử”; sửa mục tiêu/lưu v2; nạp “An Bình — đợt thử mới”. Kết quả hiển thị đúng mục tiêu v2 và hồ sơ mới, không còn tên Mộc An. Đây là nạp quy trình xác định, chưa chạy tác vụ mô hình.
6. Cài đặt: mô tả đăng xuất mọi phiên cùng tài khoản và cấu hình Google chưa có đúng môi trường; đã kiểm đăng xuất ở bước trước. Không quảng bá tài khoản demo là đăng nhập Google thật.

Ảnh an toàn: `screenshots/home-desktop.jpg`, `home-mobile.jpg`, `home-tablet.jpg`, `logout-description.jpg`, `import-readback.jpg`, `import-chat-handoff.jpg`, `memory-edited.jpg`, `template-new-input.jpg`. Toàn bộ là tài khoản/dữ liệu kiểm cục bộ, không chụp thư/khóa của người dùng.

## Phát hiện và xử lý

- Chuyển khỏi hộp xem tệp đang mở làm `#root` giữ `aria-hidden=true`; không còn dialog nhưng trang trò chuyện mất tên/quan hệ truy cập. Đã tái hiện bằng snapshot và DOM, kể cả sau nhấn Tab. Sửa ở vòng đời hộp xem: đóng, chờ kết thúc chuyển động và một frame dọn dẹp, rồi mới chuyển trang. Kiểm lại: `dialogs=0`, `rootHidden=null`, ô soạn giữ đúng nguồn, tên nút điều hướng có lại. Không xóa thuộc tính ARIA thủ công hoặc vô hiệu hóa hộp thoại.
- TypeScript từ chối `onMotionCancel` ở kiểu `PresenceMotionSlotProps<ScaleParams>` của Dialog. Loại callback không được slot hỗ trợ, chỉ dùng `onMotionFinish`; không sửa thư viện hoặc ép kiểu để bỏ kiểm.
- Lần đầu chạy hồi quy riêng thiếu `sys.path`, sau đó thiếu thư mục cha của `--basetemp`; đã sửa wrapper, không sửa ứng dụng để làm xanh kiểm. Giữ XML lần lỗi ở `validation/backend-regression-initial-fixture-error.xml`.
- Đường `npm.cmd` của runtime bundled không tồn tại; dùng `C:/Program Files/nodejs/npm.cmd` thực có. Chụp toàn trang không được trình duyệt hỗ trợ ở lần thử; dùng ảnh viewport thật. Bản chụp mobile ban đầu bị khung cũ đã được thay bằng viewport đúng.
- Một số thư mục QA lịch sử bị từ chối quyền đọc khi Git/Ruff duyệt. Không đổi quyền/xóa dữ liệu; không tuyên bố đã kiểm các thư mục bị từ chối. Thêm quy tắc bỏ qua đúng thư mục trạng thái QA sinh tự động và bằng chứng thô trong backend để tránh đưa dữ liệu riêng vào Git; tệp đã được quản lý bởi Git không bị loại khỏi kiểm.

## Giới hạn còn lại

- Giảm chuyển động chưa kiểm đầy đủ bằng giả lập thiết bị; chưa đo đủ 20 lượt cloud hoặc triển khai/quay lui.
- Chưa kiểm phần giải thích agent theo yêu cầu làm cuối; phải trình người dùng trước sửa.
- Mới quan sát một tài khoản thật. Không lấy kiểm giả lập hai người để tuyên bố bốn người thật đã đạt.
- Quan sát Supabase trước đó: DB nguồn schema 5, chưa có cột thu hồi mới; đích khôi phục không hoạt động. Cần kiểm lại và thực hiện ở bước vận hành, không tự lấy trạng thái cũ làm bằng chứng đóng.
- Không dùng ảnh/giao diện mới ở máy để tuyên bố URL Render đã cập nhật. Chưa gọi Gemini hoặc thay hạn mức trong đợt chuẩn bị này.

## Chấm phần giao diện đã thay đổi

Chỉ chấm trang bắt đầu/điều hướng và bàn giao tệp đã kiểm, không chấm toàn sản phẩm: đúng nội dung 19/20, đúng ngữ cảnh 17/20, tổ chức thông tin 12/15, chữ dễ đọc 12/15, bố cục 12/15, hoàn thiện/kiểm 13/15 = **85/100**. Đây là nhận định thiết kế của người triển khai, không phải số đo người dùng hoặc điểm suy luận mô hình. Chưa áp điểm này cho trang giải thích, nguồn thật hoặc điều kiện phát hành.

## Tài sản và quyền

Không thêm hình/logo bên ngoài. Ảnh là chụp sản phẩm của dự án với đầu vào giả lập tự soạn; giữ nguyên bộ biểu tượng/phông có sẵn. Không thay giấy phép dự án hoặc sao chép bản thiết kế bên thứ ba vào hồ sơ công khai.
