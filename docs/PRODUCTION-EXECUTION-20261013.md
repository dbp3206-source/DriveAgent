# Theo dõi triển khai — 13/10/2026

## Cập nhật 15/10 — không thay phạm vi nghiệm thu

Linh vật đã triển khai ở mã `2dbaac5`, CI#139 và Render đã xác nhận, hồ sơ ở `design-work/mascot-notifications-20261014/qa/`. Bản đặt tên Doc trước khóa/phục hồi bản duyệt `ed3fa6a` đã qua CI#140, gồm PostgreSQL thật; ảnh `7727c538…cacb0bd` đã **Live** qua thanh bên Render ngày15/10,deploy `dep-db8cmkjncjis73fe9m2g`,1m50s,nhật ký19:49:09 GMT+7.219/219 frontend,34/34 backend liên quan đã đạt tại máy. Kiểm URL thật: tên rỗng bị khóa,Hủy không kẹt,đúng tên chọn, tải lại phục hồi bản cũ; nhật ký tập đã tải có đúng1lượt chuẩn bị mới,không có lượt thực hiện Google mới.0Gemini/0chỉ mục/0Doc Google mới. [Bản đang chạy và bằng chứng](RELEASE-CANDIDATE-ed3fa6a.md). Đóng phần tên/phục hồi, không đóng trọn T07 hoặc Production. Các giới hạn khôi phục/tài khoản/dữ liệu/quota/phát hành vẫn còn; không gộp main khi chưa đủ bằng chứng.

Ngày15/10 đã trình [bản nháp giải thích ngắn](AGENT-EXPLANATION-DRAFT-20261015.md), chưa nhận góp ý/duyệt và chưa sửa trang đó. Chủ sở hữu đã duyệt tối đa 7 yêu cầu bổ sung (5 sinh câu trả lời + 2 tạo chỉ mục), nâng trần đợt lên 26, chỉ đúng dữ liệu giả lập/công khai đã duyệt và không thêm Doc. Trước bổ sung dùng 18; ghi riêng các lượt mới, tính cả lỗi/thử lại. Đồng thời chủ sở hữu yêu cầu bỏ qua khôi phục vì không nhớ mật khẩu: loại mục này khỏi đợt, ghi chưa kiểm chứng, không yêu cầu đổi mật khẩu và không tính đạt. [Điều kiện và sổ quyền dùng dữ liệu](DATA-USE.md). Lần kiểm sức khỏe công khai sau một lần hết giờ nhận HTTP200/DB/kho tệp tốt; không dùng nó chứng minh gói không ngủ hoặc AI/Google của người dùng hoạt động.

Phạm vi hiện hành: trợ lý công việc nội bộ, năm nhóm việc, ba hành trình A/B/C, đúng 16 gói và 10 ca T01–T10 trong kế hoạch ngày 13/10. Không mở thêm tính năng. Phần trình bày “Cách Agent hoạt động” để cuối và phải trình người dùng góp ý trước khi chốt.

Kiểm bổ sung ngày15/10: T02 trả lời đúng người duyệt18triệu/bản nháp chưa thay bản hiệu lực, thiếu nhắc duyệt dữ liệu; T04 hai lượt còn lại đã chạy, đúng60/42giờ và chuyển Mộc An không lẫn hồ sơ, thiếu dòng18giờ tiết kiệm. Linh vật báo xong khi đang xem Bộ nhớ và mở lại đúng hội thoại. T08 tìm thật đúng ghi chú v2; sau xác nhận riêng của chủ sở hữu đã xóa đúng mục, giữ ba ghi chú khác và truy xuất mới trả0kết quả. Chưa kiểm câu trả lời bộ nhớ trong hội thoại mới. Dùng đủ5+2=7yêu cầu bổ sung; cả đợt17+8=25/26, giữ một dự phòng cũ. [Kết quả và giới hạn cụ thể](verification/internal-assistant/RESULTS-20261015.md). Chưa ký Production, không mở đợt sửa văn phong lẻ tẻ hoặc gọi thêm ngoài ngân sách.

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
| 07 | Nhập tệp/bộ nhớ quản lý đã quan sát; truy xuất UI v2 rồi xóa/quên đúng mục sau xác nhận, tìm mới trả0; ghi chú v2 xuất thật; đúng một Doc sau duyệt/đọc lại. Tên xuất/phục hồi đã sửa,CI#140/Render/kiểm URL đạt | Câu trả lời bộ nhớ trong hội thoại mới, đổi bản/đích sau duyệt và mục bản nháp vẫn cần bằng chứng tương ứng |
| 08 | Giao diện bắt đầu đạt kiểm cục bộ; bản nháp giải thích đã trình, chưa sửa UI | Chờ góp ý/duyệt bản nháp rồi hoàn thiện đúng phần đó |
| 09 | CI #140/PostgreSQL của ed3fa6a đạt; T02 và hai lượt T04 còn thiếu đã có đầu ra, T08 truy xuất v2/xóa đúng mục/tìm mới không có; web/bàn giao/T06 có bằng chứng cloud lịch sử a284b7b | Giữ thiếu sót mức đầy đủ T02/T04; câu trả lời bộ nhớ trong hội thoại mới và phần còn lại T07 chưa đóng. Không dùng CI thay đầu ra thật |
| 10 | Chưa có số đo giá trị | Năm cặp công việc, gồm công kiểm/sửa; báo riêng quyết định đầu tư |
| 11 | Thu hồi phiên/cách ly đạt kiểm cục bộ và CI PostgreSQL; nâng cấp cloud thành công | Phiên thật và hai tài khoản; hiện mới một tài khoản hoạt động |
| 12 | Chưa khôi phục dữ liệu; chủ sở hữu yêu cầu bỏ qua ngày15/10 | Loại khỏi đợt theo quyết định chủ sở hữu; không tính đạt, công bố giới hạn chưa kiểm khôi phục khi bàn giao |
| 13 | Có hồi quy giới hạn chờ; Home đang chạy 20/20 lượt dưới 3 giây, trong cùng điều kiện thanh bên | Sau ngủ, gián đoạn và quay lui với bản vẫn giữ thu hồi phiên; không tự nâng gói |
| 14 | Chưa đóng điều kiện dữ liệu | Xác nhận dữ liệu/nhà cung cấp/quyền riêng tư/người phụ trách; không gửi dữ liệu nhạy cảm khi chưa phù hợp |
| 15 | Chưa có bằng chứng dùng lặp lại | Ba người/10 ngày theo kế hoạch; kết luận đúng hạn, tách khỏi nghiệm thu kỹ thuật |
| 16 | Hồ sơ đang cập nhật, chưa phát hành | Bản giải thích được duyệt, main/CI/digest/URL khớp, vận hành và biên bản ký duyệt |

## Thứ tự tiếp theo — không thêm phạm vi

1. Đã đưa bản sửa gộp qua CI và Live đúng ảnh; web/Doc/bàn giao/họp đã có kết quả, xem hồ sơ ngày 14/10.
2. Trước bổ sung đã dùng 12 sinh câu trả lời + 6 tạo chỉ mục. Chủ sở hữu ngày15/10 duyệt thêm tối đa 5+2, tổng bảy yêu cầu mới, trần đợt26; kiểm gộp T02/T04/T08, giữ nguyên đáp án và tính cả lỗi/thử lại.
3. Đo vận hành, điều kiện dữ liệu và cách ly thật. Khôi phục được chủ sở hữu loại khỏi đợt ngày15/10: không tiếp tục yêu cầu kết nối/mật khẩu, không đánh dấu đạt. Phần cần chủ sở hữu/tài khoản bổ sung khác ghi chờ điều kiện.
4. Làm phần giải thích cuối, trình người dùng; sau duyệt mới đóng main/phát hành và biên bản. Giá trị đầu tư ở gói 10/15 báo riêng.

Không quay về ảnh trước thu hồi phiên rồi tuyên bố vẫn có bảo đảm thu hồi. Không dùng một quản trị viên chứng minh bốn người dùng riêng. Không biến giả lập hoặc kiểm mô phỏng thành thành tích sử dụng thật.
