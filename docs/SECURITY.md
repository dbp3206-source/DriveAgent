# Bảo mật

- Least privilege theo nghiệp vụ: `drive.readonly` để tìm/đọc; `drive.file` chỉ
  quản lý file app tạo hoặc người dùng chọn; Gmail đọc/gửi tách thành hai quyền.
- Human-in-the-loop: Docs, Sheets và Gmail đều prepare → digest → approve → execute;
  backend từ chối digest hết hạn hoặc bị thay đổi.
- OAuth CSRF: callback so sánh state bằng constant-time comparison.
- Credential at rest: Fernet encryption với key dẫn xuất từ `APP_SECRET`.
- Cookie: HttpOnly do SessionMiddleware, SameSite=Lax, Secure ở mọi môi trường
  khác local/development, kể cả staging.
- Authorization: user ID lấy từ server session, không tin user ID do client gửi.
- Audit mới: chỉ ghi metadata về số đối số, loại/kích thước kết quả, trạng thái,
  độ trễ và mã lỗi; không ghi giá trị đầu vào/đầu ra hay thông điệp lỗi thô.
  Bản ghi cũ tạo trước thay đổi này cần được kiểm kê, backup an toàn và di trú
  riêng trước closed beta.
- Download: giới hạn dung lượng khai báo và dung lượng thực tế khi stream.
- Resource exhaustion: input bounds, rate limit, timeout, max retry, max tool rounds.
- Prompt injection: system prompt không coi nội dung tài liệu là lệnh; tool vẫn bị registry kiểm soát.
- Browser hardening: CSP, frame deny, nosniff, referrer policy, COOP và Permissions-Policy.
- Secrets: `.env`, OAuth JSON, database và Qdrant data bị `.gitignore`.
- Closed beta: ở môi trường khác `local`/`development`, OAuth và mọi phiên
  hiện hữu đều bị chặn nếu email không thuộc `DRIVE_AGENT_BETA_INVITED_EMAILS`
  (danh sách email phân cách bằng dấu phẩy, so khớp không phân biệt hoa/thường).
  Danh sách rỗng nghĩa là **không ai được vào**, trùng email hoặc quá bốn email khiến
  backend từ chối khởi động; phải đặt thêm
  `DRIVE_AGENT_BETA_OWNER_EMAIL` thuộc danh sách này. Chỉ email chủ là
  `super_admin`, không phụ thuộc thứ tự đăng nhập. Phải có email chủ sản phẩm trước
  khi chuyển môi trường, và thu hồi lời mời cũng vô hiệu hóa phiên đang có.
  Backend còn từ chối **khởi động trước khi mở database** nếu danh sách mời rỗng
  hoặc sai dạng, `APP_SECRET` mặc định/ngắn, metrics token ngắn, public/frontend/OAuth URL không dùng
  HTTPS, OAuth redirect khác host ứng dụng, demo login bật hoặc quota profile
  không bảo thủ. Development chỉ chấp nhận public URL trên loopback và từ chối
  request có địa chỉ peer ngoài loopback, kể cả khi Host header trông như localhost. Đây là
  chốt cấu hình, **không thay thế** kiểm chứng TLS/reverse proxy và staging thực.
  Profile beta local yêu cầu `DRIVE_AGENT_STATE_DIR` tuyệt đối, với SQLite DB và
  Qdrant nằm bên dưới. Profile cloud bắt buộc PostgreSQL TLS, cùng một project cho
  application/state, ADK, Supabase Storage private và OAuth client ID/secret qua env.
  Các guard chỉ kiểm tra cấu hình; persistence vẫn phải được thử qua redeploy/restore thật.
  Mọi API ghi dựa trên phiên browser chỉ nhận origin/referer khớp chính xác URL
  public/frontend; header AJAX hoặc Host giả không thay thế kiểm tra nguồn gốc.
  Remote action token đã ký và MCP/A2A có cơ chế xác thực riêng; webhook Gmail
  hiện vô hiệu hóa (501). Middleware chung không được ghi đè CSP/Referrer-Policy
  chặt hơn của từng endpoint; trang xác nhận token chỉ gửi origin, không gửi
  token trong query URL qua Referer.
  Mặc định `DRIVE_AGENT_BETA_ALLOW_EXTERNAL_WRITES=false`: Tool Registry chặn
  bốn công cụ thực thi ghi ngoài (`docs_execute`, `sheets_execute`,
  `gmail_create_draft`, `gmail_send`) trước khi gọi handler, vẫn ghi audit bị
  từ chối. Chuẩn bị bản xem trước và đọc lại không bị chặn. Chỉ bật cờ sau
  quyết định riêng; phê duyệt từng thao tác và RBAC/OAuth vẫn bắt buộc.
- AgentOps: lựa chọn phát hành là metadata local 30 ngày, không exporter ngoài.
  Trace chat mới được lọc trường trước khi lưu; trace cũ đã được di trú bằng
  snapshot mã hóa. Startup và tác vụ mỗi giờ xóa riêng `messages.trace_json`
  quá 30 ngày, không xóa nội dung chat/citation hay audit nghiệp vụ. Dashboard
  chỉ tính 30 ngày. Audit tool mới chỉ lưu metadata vận hành; audit cũ đã được
  làm sạch bằng di trú có bản sao lưu mã hóa và kiểm tra phục hồi. Cần chốt
  thời hạn/xóa bản sao lưu mã hóa có chứa dữ liệu cũ trước khi công bố tuân thủ
  retention hoàn toàn; vòng đời audit nghiệp vụ cũng là chính sách riêng.

Render cung cấp HTTPS/reverse proxy và secret store cho profile closed beta; PostgreSQL có
migration ledger. Trước khi phát hành vẫn phải chạy kiểm thử rate limit nhiều user,
backup/restore trên Supabase và OAuth Testing qua URL HTTPS thật. Public verification của
Google nằm ngoài phạm vi closed beta tối đa bốn test users.
