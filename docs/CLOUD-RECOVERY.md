# Khôi phục dữ liệu cloud sang môi trường mới

Phạm vi: điều kiện D2 / H09. Đây là hướng dẫn thao tác, **không phải bằng chứng đã khôi phục Supabase thành công**. Không thử trên project đang phục vụ người dùng. Không dùng bản sao thư mục `data/` để thay cho bản sao cloud.

Kiểm tra công cụ ngày 05/10/2026: chạy `python -m pytest backend/tests/test_state_archive.py -q` bằng môi trường Python của dự án, **5 phép thử đạt trong 5,26 giây**. Phạm vi là mã hóa/giải mã, chống ghi đè, bản hỏng và đường dẫn không an toàn trên dữ liệu thử local; chưa kiểm việc xuất PostgreSQL, tải Storage hoặc khôi phục Supabase. Các công cụ PostgreSQL chưa được tìm thấy trên PATH trong lượt kiểm này.

## 1. Chuẩn bị và dừng ghi

Ngày 05/10 đã tạo đích thử miễn phí được chủ sở hữu cho phép:
`Veridra-restore-check-20261005` (`scsxkanbmtexylgbrsla`), khác project nguồn
`ltvzdrvjmljvrnhwxade`. Chưa chuyển dữ liệu hoặc đóng điều kiện khôi phục.
Máy có `pg_dump` và `pg_restore` 17.10 trong
`C:/Program Files/PostgreSQL/17/bin`; cần gọi đường dẫn đầy đủ vì chưa có trên PATH.

- Ghi lại phiên bản mã, mã ảnh Docker, phiên bản PostgreSQL, phiên bản di trú và tên kho tệp từ cấu hình Render. Mặc định kho là `veridra-private`; xác nhận giá trị thực tế trước khi dùng.
- Chọn một khoảng bảo trì: ngừng nhận tác vụ mới, chờ tác vụ đang chạy kết thúc, dừng worker và nguồn tạo tác vụ định kỳ. Không chỉ đóng tab trình duyệt. Giữ nguyên trạng thái thao tác Google chưa rõ kết quả; không tự gửi lại sau khôi phục.
- Dùng công cụ PostgreSQL cùng phiên bản lớn với máy chủ nguồn. Đã xác nhận công cụ 17 ở đường dẫn trên; không chạy Docker nặng chỉ để có hai công cụ này.
- Tạo thư mục riêng, ngoài Git, trên ổ mã hóa và chỉ tài khoản chủ sở hữu được truy cập. Kiểm đủ dung lượng trước khi tải. Bản sao và bản giải mã không được đưa vào GitHub, nhật ký CI hay Chat.
- Kết nối bằng thông tin trong **Supabase → Connect → Direct → Session pooler**, hoặc kết nối trực tiếp nếu mạng hỗ trợ. Không dùng cổng gom kết nối theo giao dịch. Nhập mật khẩu qua lời nhắc của công cụ, không gắn vào URL hay câu lệnh.

## 2. Sao lưu cả cơ sở dữ liệu và tệp

Schema ứng dụng hiện tại là `veridra_private`, gồm cả lịch sử, khóa đã mã hóa, bộ nhớ, kết quả, tác vụ và các bảng trạng thái vận hành. Không chỉ sao lưu bảng Chat. Các kiểu vector phụ thuộc phần mở rộng trong schema `extensions`.

Kiểm tra project đang chạy ngày 05/10/2026 còn phát hiện lịch sử điều phối cũ tại năm bảng `public.adk_internal_metadata`, `public.app_states`, `public.user_states`, `public.sessions`, `public.events`. Quyền đọc qua API của các bảng này đã được khóa, nhưng dữ liệu chưa được chuyển hoặc xóa. Nếu nguồn còn các bảng này, phải xuất thêm cả năm bảng vào bản sao riêng bằng các lựa chọn `--table` tương ứng; ghi số hàng và phục hồi cùng bản schema riêng tư. Chỉ xuất `veridra_private` sẽ thiếu lịch sử điều phối cũ. Trước khi mở môi trường phục hồi, bật bảo vệ từng hàng và thu hồi toàn bộ quyền của `PUBLIC`, `anon`, `authenticated` trên các bảng cũ; không tạo chính sách cho phép đọc công khai.

Với `pg_dump`, chọn định dạng riêng `--format=custom`, chọn schema `--schema=veridra_private`, xuất vào tệp mới và yêu cầu nhập mật khẩu `--password`. Giá trị host, port, username và database lấy nguyên từ Connect; không điền tên giả rồi coi là đã chạy. Ghi nhận mã thoát và cảnh báo. Bản chọn một schema không tự chứa mọi phụ thuộc: ghi riêng phiên bản/phần mở rộng đang dùng để chuẩn bị đích tương thích.

Trong **Supabase → Storage**, mở đúng kho riêng tư, tải **mọi tệp trong mọi thư mục người dùng**, giữ nguyên đường dẫn `<người dùng>/<tác vụ>.pdf`. Không chỉ tải các PDF đang nhìn thấy ở trang đầu. Nếu số lượng vượt khả năng đối soát thủ công, dùng đường API có phân trang; không công nhận bản tải một phần.

Lập danh sách riêng tư gồm: đường dẫn, số byte và SHA256 của từng tệp; số hàng của từng bảng ứng dụng; số vector; số tác vụ theo trạng thái. Tệp được tham chiếu từ tác vụ phải tồn tại, hoặc có lý do xóa/giữ lại đã đối soát. Không chép nội dung thư, prompt hoặc khóa vào báo cáo công khai.

Mã hóa thư mục chứa bản cơ sở dữ liệu, tệp và danh sách đối soát bằng công cụ sẵn có:

```powershell
.\backend\.venv\Scripts\python.exe scripts\state_archive.py backup `
  --source "<thu-muc-ban-sao-moi>" `
  --output "<tep-ma-hoa-moi>.vrd" --port 8000
```

Các giá trị trong dấu `<...>` là chỗ cần thay bằng đường dẫn đã kiểm tra, không phải lệnh chạy nguyên trạng. Công cụ yêu cầu mật khẩu riêng ít nhất 16 ký tự và từ chối ghi đè. Kiểm cổng 8000 chỉ bảo vệ tiến trình local; **không chứng minh Render đã dừng ghi**. Bản rõ trung gian phải nằm trên ổ mã hóa; sau khi kiểm bản mã hóa thành công, chủ sở hữu xử lý bản rõ theo chính sách lưu trữ. Giữ bản sao tối đa 30 ngày.

Lưu riêng bí mật ứng dụng cũ trong nơi quản lý bí mật. Không đổi `APP_SECRET` của bản khôi phục: dữ liệu khóa/OAuth đã mã hóa cần đúng bí mật này. Mật khẩu mã hóa bản sao là bí mật khác.

## 3. Khôi phục vào project thử mới

1. Tạo project Supabase riêng, không dùng project nguồn. Xác nhận mã project đích khác mã nguồn trước mọi thao tác ghi. Chuẩn bị PostgreSQL/phần mở rộng vector tương thích.
2. Giải mã vào thư mục **chưa tồn tại** bằng `scripts/state_archive.py restore --archive "<ban-ma-hoa>" --destination "<thu-muc-moi>"`. Công cụ đối chiếu SHA256 trước khi xuất kết quả; không đè thư mục đang dùng.
3. Xem danh mục bản dump bằng `pg_restore --list`. Đích chưa có schema ứng dụng; không khởi động app để tạo bảng trước khi phục hồi. Chạy phục hồi với `--exit-on-error --single-transaction --no-owner --no-acl`, nhập mật khẩu đích khi được hỏi. Không dùng `--clean`, không bỏ qua lỗi để tiếp tục nghiệm thu.
4. Khôi phục quyền riêng tư bằng cùng cơ chế khởi tạo của phiên bản ứng dụng: `veridra_private` không cho `PUBLIC`, `anon` hay `authenticated` truy cập. Không bật schema này trong Data API. Bỏ quyền của nguồn khi phục hồi không đồng nghĩa đã kiểm quyền đích.
5. Tạo kho tệp **private**, cùng tên và giới hạn cấu hình; tải lại mọi tệp theo đúng đường dẫn. Không ghi đè tệp sẵn có. Đối chiếu số lượng, tổng byte và SHA256 từng tệp đã tải lại.
6. Tạo dịch vụ Render thử riêng với đúng ảnh đã ghi, cơ sở dữ liệu/kho đích và bí mật ứng dụng cũ; giữ tác vụ định kỳ và quyền ghi Google tắt. Không đổi cấu hình dịch vụ đang hoạt động.
7. Đăng nhập tài khoản được mời. Đối chiếu số hàng **từng bảng**, vector, chủ sở hữu, trạng thái tác vụ; đọc lại một kết quả, một quy trình, một bộ nhớ và một PDF có văn bản. Kiểm nguồn/trang trích dẫn, không chỉ xem tên tệp.
8. Thử truy cập bằng người dùng khác và đường không đăng nhập: phải bị từ chối. Tác vụ đã hoàn thành không chạy lại; tác vụ chưa rõ thao tác Google phải đối soát trước khi cho tiếp tục. Chưa bật gửi thư/tạo tài liệu tự động trong lần thử này.

## 4. Bằng chứng để đóng H09

Ghi thời điểm, phiên bản nguồn/đích, mã yêu cầu đã khử dữ liệu riêng, số hàng từng bảng trước/sau, danh sách checksum đã đối soát, kết quả đọc lại và kiểm quyền. Ghi cả lỗi, tệp thiếu, phụ thuộc thiếu và tác vụ chưa đối soát. Chỉ đánh dấu ĐẠT khi toàn bộ đối chiếu thành công trên môi trường mới; mã hóa/giải mã local hoặc redeploy giữ dữ liệu không thay thế phép thử này.

Nguồn hướng dẫn chính thức: [sao lưu và phục hồi Supabase](https://supabase.com/docs/guides/platform/migrating-within-supabase/backup-restore), [pg_dump và giới hạn chọn schema](https://www.postgresql.org/docs/current/app-pgdump.html), [pg_restore](https://www.postgresql.org/docs/current/app-pgrestore.html). Nội dung tệp Storage phải chuyển riêng, không nằm trong bản sao cơ sở dữ liệu.
