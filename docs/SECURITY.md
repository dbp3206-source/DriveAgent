# Bảo mật

- Least privilege theo nghiệp vụ: `drive.readonly` để tìm/đọc; `drive.file` chỉ
  quản lý file app tạo hoặc người dùng chọn; Gmail đọc/gửi tách thành hai quyền.
- Human-in-the-loop: Docs, Slides, Sheets và Gmail đều prepare → digest → approve → execute;
  backend từ chối digest hết hạn hoặc bị thay đổi.
- OAuth CSRF: callback so sánh state bằng constant-time comparison.
- Credential at rest: Fernet encryption với key dẫn xuất từ `APP_SECRET`.
- Cookie: HttpOnly do SessionMiddleware, SameSite=Lax, Secure ở production.
- Authorization: user ID lấy từ server session, không tin user ID do client gửi.
- Audit: redaction đệ quy các khóa API key, token, secret, password, authorization.
- Download: giới hạn dung lượng khai báo và dung lượng thực tế khi stream.
- Resource exhaustion: input bounds, rate limit, timeout, max retry, max tool rounds.
- Prompt injection: system prompt không coi nội dung tài liệu là lệnh; tool vẫn bị registry kiểm soát.
- Browser hardening: CSP, frame deny, nosniff, referrer policy, COOP và Permissions-Policy.
- Secrets: `.env`, OAuth JSON, database và Qdrant data bị `.gitignore`.

Trước khi expose ra Internet cần thêm HTTPS, reverse proxy, distributed rate limit,
managed secret store, backup, database migration và quy trình OAuth verification của Google.
