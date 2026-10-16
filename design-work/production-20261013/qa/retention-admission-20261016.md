# Kiểm soát việc ghi khi dọn dữ liệu — 16/10/2026

## Phạm vi và trạng thái

Thuộc gói 14 hiện hành, không thêm gói nghiệm thu. Nhánh `work/data-retention-20261015`.
Chưa triển khai Render, chưa gộp main; không xóa dữ liệu thật, không gọi Gemini,
không gửi/sửa Google, không đổi hạn mức hoặc gói trả phí. Đây không phải nghiệm thu
toàn bộ cơ chế lưu 30 ngày hoặc tuyên bố Production.

## Nguyên nhân cần xử lý

Xóa đúng hàng trong SQL vẫn chưa đủ nếu yêu cầu, công cụ hoặc tác vụ nền đang giữ
nội dung và ghi lại sau khi xóa. Hủy một `asyncio.to_thread` cũng không dừng luồng
hệ điều hành. Chỉ kiểm trạng thái hàng đợi hoặc chỉ khóa từng câu SQL không khép
được khoảng trống này.

## Thay đổi đã thực hiện

- Một lớp tiếp nhận dùng chung theo tài khoản: các yêu cầu thường vẫn chạy song
  song; dọn dữ liệu phải đợi những việc đã nhận kết thúc, từ chối việc mới khi đang
  đợi/dọn. Không khóa tài khoản khác. Chờ nhận quyền dọn có giới hạn hai giây.
- Kiểm sổ tiến độ bền vững trước tiếp nhận: khởi động lại không bỏ quên việc dọn
  đang mở. Chỉ cho đọc sau khi phần SQL đã hoàn tất; chưa cho ghi lại khi các bản
  vật lý còn chưa xử lý. Điều này chưa thay bộ điều phối/xác minh các kho còn thiếu.
- Nối vào yêu cầu HTTP có phiên đăng nhập đã ký, giữ quyền tới phần cuối phản hồi;
  cả ba bộ máy trợ lý và nơi gọi công cụ cũng kiểm, kể cả đường giao thức không
  đi qua phiên trình duyệt. Không giữ khóa suốt kết nối giao thức nhàn rỗi.
- Các bộ xử lý chat, PDF, lịch hẹn và bộ kiểm không lấy việc của tài khoản đang
  dọn hoặc tiêu hao số lần thử của việc đó. Đợt hẹn giờ có thể phục vụ người khác;
  người bị hoãn được báo `deferred_cleanup`, không được tính đã tạo bản tin.
  Không tự thêm lịch chạy lại cho đợt bị hoãn.
- Các luồng ghi mẫu, sổ thao tác tài liệu/thư/bảng tính, chỉ mục và tệp local giữ
  quyền riêng đến khi luồng thực sự dừng. Khi hết thời gian chờ, phản hồi có thể
  trả lỗi ngay nhưng không được dọn khi luồng nền còn ghi. Lúc tắt ứng dụng đợi
  các luồng này trước khi đóng bộ kết nối DB. Luồng bị hủy có lỗi không in nội dung
  riêng ra nhật ký.
- Tệp tạm PDF cần cách xử lý riêng: đợi ghi dừng rồi mới bỏ tệp, tránh luồng ghi
  tạo lại tệp sau khi đoạn xử lý hủy đã xóa nó.
- Thao tác Gmail qua liên kết đã ký kiểm trước khi dùng mã một lần. Đang dọn trả
  503, lời báo tiếng Việt, `Retry-After`, không lưu đệm; sau đó cùng mã vẫn dùng
  được đúng một lần. Không coi lỗi nhà cung cấp sau khi ghi là lỗi có thể phát lại.

Không thêm dịch vụ, phụ thuộc, bảng, API dọn hoặc quyền mới. Cơ chế trong bộ nhớ
chỉ dùng cho cấu hình một tiến trình đã đóng gói (`Dockerfile --workers 1`);
không gọi đây là khóa phân tán hoặc hỗ trợ nhiều bản máy chủ chạy đồng thời.

## Bằng chứng tại máy

- Đợt trước nối luồng ghi: 218 đạt, không lỗi/bỏ qua, 97,048 giây. Không dùng kết
  quả này để chứng minh các sửa đổi sau nó.
- Đợt sau nối luồng ghi và thêm đối chiếu quyền: **342 đạt, 5 bỏ qua, 0 lỗi**, 124,01
  giây; XML tại `tmp/owner-admission-regression-da807b7f193e49aba1660fa6b53f9e1d/results.xml`.
  Năm mục bỏ qua là thử liên kết tệp Windows; phải đối chiếu Linux ở CI đúng mã.
  Đợt này chạy trước bổ sung chờ ghi tệp tạm; bộ kiểm riêng/CI tiếp theo phải bao phủ nó.
- Bộ kiểm riêng sau bổ sung tệp tạm: **19 đạt, 0 lỗi/bỏ qua**, 19,74 giây;
  `tmp/owner-admission-temp-f0af11f7c86c4e4284d0c4bfb18182fd/results.xml`.
  Không cộng số này với 342 vì có ca trùng.
- Sau khi giữ nguyên dấu nội dung trong lúc bảo trì nhật ký và chốt thứ tự tắt ứng
  dụng: **44 đạt, 0 lỗi/bỏ qua**, 25,52 giây;
  `tmp/owner-admission-closed-5c36bc50c91e4cb8b00ef656debedf12/results.xml`.
  Bộ này gồm 20 ca tiếp nhận, ca nhật ký và vòng đời máy chủ, không phải toàn bộ máy chủ.
- Đã chạy `ruff check backend`, `git diff --check` và `scripts/scan_release_secrets.py`;
  kiểm bí mật cuối đạt cho 741 tệp Git thấy, sau khi thêm hồ sơ này.
- Hai ca PostgreSQL mới chỉ được tính sau CI PostgreSQL riêng `veridra_ci`.
  Không dùng DB cloud cá nhân làm DB kiểm thử, không nhận bỏ qua là đạt.
- Kiểm thực SQLite, phiên HTTP ký và luồng ghi/tệp thật trong thư mục thử riêng;
  Google/Gemini được thay bằng đối tượng giả trong những ca cần đáp ứng công cụ.
  Không gọi đây là bằng chứng thao tác Google thật.

## Giới hạn còn giữ nguyên

Vẫn cần bộ điều phối liên kho, danh sách duyệt có đủ quan hệ phụ thuộc, đặt lại
ngữ cảnh liên quan, xóa và đọc lại chỉ mục/tệp thực, API/hộp thoại và làm mới bộ
nhớ trình duyệt. Chưa bật cơ chế tự nhắc/xóa trên URL. Không khẳng định tệp mồ côi,
bản sao nhà cung cấp, bản tải về máy khác hoặc ngữ cảnh mới hơn đã được xử lý.

Các điều kiện gửi dữ liệu tới Gemini vẫn riêng biệt với mã hóa/cách ly tài khoản.
Không coi sự cho phép biện pháp bảo mật là xác nhận mọi đầu vào đã ẩn danh hoặc
được phép gửi tới dịch vụ chưa bật thanh toán. Ngân sách đợt kiểm vẫn 25/26 đã dùng;
đợt này không dùng thêm yêu cầu nhà cung cấp.
