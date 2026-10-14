# Theo dõi triển khai — 13/10/2026

Phạm vi hiện hành: trợ lý công việc nội bộ, năm nhóm việc, ba hành trình A/B/C, đúng 16 gói và 10 ca T01–T10 trong kế hoạch ngày 13/10. Không mở thêm tính năng. Phần trình bày “Cách Agent hoạt động” để cuối và phải trình người dùng góp ý trước khi chốt.

**Trạng thái: đang nghiệm thu bản đã triển khai, chưa nghiệm thu Production.** Bản sửa gộp `a284b7b` đã qua CI #137 và Live đúng ảnh. Đã kiểm lại web, hộp xem → Chat, một Doc có duyệt/đọc lại, hai lượt họp và 20 lượt mở Home; các giới hạn còn lại được ghi riêng. Bằng chứng mới ở `verification/internal-assistant/RESULTS-20261014.md`; bản triển khai ở `RELEASE-CANDIDATE-a284b7b.md`. Không đổi kết quả lịch sử hoặc tự tính mọi ca đạt.

## Đã thực hiện và có bằng chứng

- Khóa hợp đồng N1–N5, bốn tệp giả lập A/B/C và 10 ca có đáp án riêng. Bộ `.2` bỏ đáp án khỏi tệp đầu vào trước khi chạy. Chủ sở hữu duyệt 11 yêu cầu sinh câu trả lời + 8 tạo chỉ mục, tổng 19; sổ đợt ghi 8 + 6 tại thời điểm đóng kiểm bộ nhớ ngày 14/10. Xem hồ sơ kết quả cho số thực và giới hạn.
- Thống nhất nhận diện nguồn bị cấm và yêu cầu tạo tài liệu. “Không có lịch”/“không tạo lịch” không bị hiểu thành cấm đọc lịch; chủ đề tài liệu không tự thành lệnh ghi. Có hồi quy chung, không vá theo tên doanh nghiệp.
- Sửa tìm toàn văn Drive: bỏ sắp xếp không tương thích chỉ ở tìm toàn văn; giữ thứ tự gần đây ở đường duyệt. Phân biệt truy vấn, quyền, phiên, cấu hình và hạn mức; không trả thông báo Google chứa mã tài liệu riêng.
- Thêm thu hồi mọi phiên của cùng tài khoản ở máy chủ. Kiểm cookie sao chép, tài khoản khác, cookie cũ và đăng xuất lại bằng phiên cũ. Migration SQLite 7 / PostgreSQL 6 giữ dữ liệu; PostgreSQL thật qua CI, cloud đã lên schema 6 và người dùng đã đăng nhập lại. Kiểm phiên cloud và hai tài khoản thật chưa đóng.
- Trang chủ dùng năm gợi ý công việc, cùng ô trò chuyện, không tự gửi. Giữ hệ thống thiết kế hiện có; đổi tên điều hướng và mô tả cài đặt cho đúng hành vi. Không sửa trang giải thích đang chờ góp ý.
- Kiểm giao diện cục bộ ở ba kích thước, bàn phím và các gợi ý. Nhập báo giá giả lập, mở đọc lại và chuyển nguồn sang ô trò chuyện mà không gọi mô hình. Sửa thứ tự đóng hộp xem trước khi chuyển trang; kiểm lại xác nhận trang mới không còn bị `aria-hidden` che khỏi công cụ đọc màn hình.

## Số đo kiểm tại máy

| Bộ kiểm | Kết quả | Giới hạn bằng chứng |
|---|---|---|
| Toàn bộ kiểm phía máy chủ | 1.609 đạt, 15 bỏ qua; 0 lỗi | XML có 1.624 ca; bỏ qua không tính đạt. Bản chạy này trước bổ sung ca nâng cấp PostgreSQL riêng |
| Độ phủ mã phía máy chủ | 87,24% | Vượt ngưỡng CI 85%; không phải điểm chất lượng câu trả lời |
| Hồi quy ngoại tuyến có phiên bản | 200/200 đạt | Định tuyến 12, bộ chấm 12, hợp đồng đầu ra 16, biến thể đối kháng 160; 0 lượt mô hình |
| Kiểm đơn vị giao diện | 190/190 đạt | Không thay kiểm Google/Gemini thật |
| Kiểm mã và dựng giao diện | Đạt sau sửa đóng hộp xem và nội dung mẫu/bộ nhớ | TypeScript, ESLint và Vite thực; chưa thay CI/ảnh triển khai |
| Bộ dữ liệu mới | 10 ca / 4 tệp, toàn vẹn đạt | Chưa chạy đủ T01–T10 trên bản triển khai |
| Giao diện thật | Máy tính, điện thoại 390×844, trung gian 820×900; không tràn ngang ở màn đã kiểm | Không phải đo 20 lượt tải cloud; chưa giả lập đầy đủ giảm chuyển động |

Các bộ kiểm có phần chồng lặp; không cộng mẫu số thành “tổng điểm sản phẩm”. Ảnh và hồ sơ ở `design-work/production-20261013/qa/`. XML thô giữ tại máy, không đưa vào Git.

## Sổ 16 gói việc

| Gói | Trạng thái đúng bằng chứng | Việc còn lại để đóng |
|---|---|---|
| 01 | Chưa xác nhận công việc thật | Người dùng xác nhận hồ sơ và cách làm đối chứng; không chặn kiểm kỹ thuật bằng giả lập |
| 02 | Đã có đặc tả triển khai | Đối chiếu đầu ra thật N1–N5 trong đợt kiểm gộp |
| 03 | Đạt chuẩn bị bộ dữ liệu | Dùng đúng bộ đã khóa, ghi lượt thực và đáp án khi chạy |
| 04 | Đạt hồi quy tại máy | Xác nhận dấu vết nguồn/hành động trong T02/T04/T05 trên ứng viên |
| 05 | Drive lọc/phân trang 50→100/tìm “Veridra” 3 dòng/bỏ tìm đã xác nhận; bốn tệp có chỉ mục; web công khai chạy đúng | Nội dung tệp riêng/loại tệp chưa kiểm không tự tính đạt; nguồn web còn dư |
| 06 | Đã cập nhật hợp đồng và chỉ dẫn | Chạy gộp đầu ra N1–N5, chấm đúng/rõ/dùng được; không tối ưu văn phong ngoài tiêu chí |
| 07 | Nhập tệp/bộ nhớ quản lý đã quan sát; ghi chú v2 xuất thật; đúng một Doc sau duyệt và đọc lại độc lập thành công | Quên/truy xuất hội thoại mới; đổi bản/đích sau duyệt; tên xuất và mục bản nháp còn chưa đúng mong muốn |
| 08 | Giao diện bắt đầu đạt kiểm cục bộ; còn phần để cuối | Trình bản nháp giải thích ngắn, nhận góp ý; rà nội dung khi chức năng ổn định |
| 09 | CI #137/PostgreSQL/ảnh a284b7b đạt; web và bàn giao cloud đã kiểm lại, T06 hai lượt thành công | T02/T04/T08 và phần còn lại T07 chưa đủ bằng chứng; không tự tăng ngân sách |
| 10 | Chưa có số đo giá trị | Năm cặp công việc, gồm công kiểm/sửa; báo riêng quyết định đầu tư |
| 11 | Thu hồi phiên/cách ly đạt kiểm cục bộ và CI PostgreSQL; nâng cấp cloud thành công | Phiên thật và hai tài khoản; hiện mới một tài khoản hoạt động |
| 12 | Đích thử riêng đã hoạt động lại, còn trống; chưa khôi phục dữ liệu | Khôi phục DB+tệp bằng kết nối an toàn, đối soát và đo thời gian, không ghi đè nguồn |
| 13 | Có hồi quy giới hạn chờ; Home đang chạy 20/20 lượt dưới 3 giây, trong cùng điều kiện thanh bên | Sau ngủ, gián đoạn và quay lui với bản vẫn giữ thu hồi phiên; không tự nâng gói |
| 14 | Chưa đóng điều kiện dữ liệu | Xác nhận dữ liệu/nhà cung cấp/quyền riêng tư/người phụ trách; không gửi dữ liệu nhạy cảm khi chưa phù hợp |
| 15 | Chưa có bằng chứng dùng lặp lại | Ba người/10 ngày theo kế hoạch; kết luận đúng hạn, tách khỏi nghiệm thu kỹ thuật |
| 16 | Hồ sơ đang cập nhật, chưa phát hành | Bản giải thích được duyệt, main/CI/digest/URL khớp, vận hành và biên bản ký duyệt |

## Thứ tự tiếp theo — không thêm phạm vi

1. Đã đưa bản sửa gộp qua CI và Live đúng ảnh; web/Doc/bàn giao/họp đã có kết quả, xem hồ sơ ngày 14/10.
2. Chủ sở hữu đổi phân bổ thành 13 sinh câu trả lời + 6 tạo chỉ mục, giữ tổng 19; đã dùng 12+6. Giữ một lượt dự phòng vì không đủ bảo đảm đường tự thử lại; không tự chạy thêm hoặc đổi đáp án.
3. Đóng khôi phục, đo vận hành, điều kiện dữ liệu và cách ly thật. Phần cần chủ sở hữu/tài khoản bổ sung ghi chờ điều kiện, không đánh dấu đạt giả.
4. Làm phần giải thích cuối, trình người dùng; sau duyệt mới đóng main/phát hành và biên bản. Giá trị đầu tư ở gói 10/15 báo riêng.

Không quay về ảnh trước thu hồi phiên rồi tuyên bố vẫn có bảo đảm thu hồi. Không dùng một quản trị viên chứng minh bốn người dùng riêng. Không biến giả lập hoặc kiểm mô phỏng thành thành tích sử dụng thật.
