# Theo dõi triển khai — 13/10/2026

Phạm vi hiện hành: trợ lý công việc nội bộ, năm nhóm việc, ba hành trình A/B/C, đúng 16 gói và 10 ca T01–T10 trong kế hoạch ngày 13/10. Không mở thêm tính năng. Phần trình bày “Cách Agent hoạt động” để cuối và phải trình người dùng góp ý trước khi chốt.

**Trạng thái: đang nghiệm thu bản đã triển khai, chưa nghiệm thu Production.** Ứng viên `410966a` đã qua CI #136 và Live đúng ảnh; ba lỗi phát hiện trong đợt kiểm đang được sửa gộp. Bằng chứng mới và phần chưa đạt ở `verification/internal-assistant/RESULTS-20261014.md`; phiên bản triển khai ở `RELEASE-CANDIDATE-410966a.md`. Kết quả cũ không tự chuyển thành kết quả của bản sửa tiếp theo.

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
| 05 | Drive thật phản hồi, lọc thư mục/tệp/gắn sao đã quan sát; bốn tệp giả lập có chỉ mục | Đóng phân trang/tìm toàn văn; xác minh bản sửa định tuyến web công khai |
| 06 | Đã cập nhật hợp đồng và chỉ dẫn | Chạy gộp đầu ra N1–N5, chấm đúng/rõ/dùng được; không tối ưu văn phong ngoài tiêu chí |
| 07 | Nhập tệp và bộ nhớ tạo/sửa/cất/khôi phục trên cloud đã quan sát; mẫu v1/v2 với dữ kiện mới đạt tại máy | Quên/truy xuất hội thoại mới và chuỗi một Doc sau duyệt trên cloud |
| 08 | Giao diện bắt đầu đạt kiểm cục bộ; còn phần để cuối | Trình bản nháp giải thích ngắn, nhận góp ý; rà nội dung khi chức năng ổn định |
| 09 | CI #136, PostgreSQL và ảnh 410966a đạt; đã bắt đầu đợt tích hợp và tìm ba lỗi cụ thể | Một bản sửa gộp qua CI/triển khai, kiểm lại đúng chỗ lỗi trong ngân sách còn lại |
| 10 | Chưa có số đo giá trị | Năm cặp công việc, gồm công kiểm/sửa; báo riêng quyết định đầu tư |
| 11 | Thu hồi phiên/cách ly đạt kiểm cục bộ và CI PostgreSQL; nâng cấp cloud thành công | Phiên thật và hai tài khoản; hiện mới một tài khoản hoạt động |
| 12 | Đích thử riêng đã hoạt động lại, còn trống; chưa khôi phục dữ liệu | Khôi phục DB+tệp bằng kết nối an toàn, đối soát và đo thời gian, không ghi đè nguồn |
| 13 | Có hồi quy giới hạn chờ/khôi phục tác vụ, chưa đủ vận hành | Đo 20 lượt cloud, gián đoạn và quay lui với bản vẫn giữ thu hồi phiên; không tự nâng gói |
| 14 | Chưa đóng điều kiện dữ liệu | Xác nhận dữ liệu/nhà cung cấp/quyền riêng tư/người phụ trách; không gửi dữ liệu nhạy cảm khi chưa phù hợp |
| 15 | Chưa có bằng chứng dùng lặp lại | Ba người/10 ngày theo kế hoạch; kết luận đúng hạn, tách khỏi nghiệm thu kỹ thuật |
| 16 | Hồ sơ đang cập nhật, chưa phát hành | Bản giải thích được duyệt, main/CI/digest/URL khớp, vận hành và biên bản ký duyệt |

## Thứ tự tiếp theo — không thêm phạm vi

1. Đóng kiểm bản sửa gộp ba nguyên nhân đã xác định; đưa lên cùng nhánh riêng chạy CI PostgreSQL/ảnh, chưa gọi là bản đã nghiệm thu.
2. Triển khai đúng ảnh CI đạt. Kiểm lại web và Doc trong ngân sách còn lại; các ca thiếu lượt ghi chưa kiểm, không đặt lại bộ đếm hoặc tự cộng ngân sách khi đổi ngày.
3. Đóng khôi phục, đo vận hành, điều kiện dữ liệu và cách ly thật. Phần cần chủ sở hữu/tài khoản bổ sung ghi chờ điều kiện, không đánh dấu đạt giả.
4. Làm phần giải thích cuối, trình người dùng; sau duyệt mới đóng main/phát hành và biên bản. Giá trị đầu tư ở gói 10/15 báo riêng.

Không quay về ảnh trước thu hồi phiên rồi tuyên bố vẫn có bảo đảm thu hồi. Không dùng một quản trị viên chứng minh bốn người dùng riêng. Không biến giả lập hoặc kiểm mô phỏng thành thành tích sử dụng thật.
