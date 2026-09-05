# Bắt đầu dùng DriveAgent thật trên máy local

Mục tiêu hiện tại: bạn hoặc nhóm nhỏ đăng nhập Google và dùng dữ liệu Drive thật
trên máy này. Chưa cần domain, VPS, Cloud SQL hoặc Redis. Đây chưa phải dịch vụ public.

## 1. Mở đúng thư mục

Mở PowerShell và chạy:

```powershell
cd "C:\Users\Bao Phuc\Documents\DriveAgent\drive-agent"
```

Trên máy hiện tại đã có backend venv, thư viện frontend và `.env` với APP_SECRET ngẫu nhiên.
Không cần chạy lại setup. Máy mới chạy `powershell -ExecutionPolicy Bypass -File scripts/setup.ps1`.
Script giữ nguyên `.env` đã tồn tại; không đổi APP_SECRET sau khi đã đăng nhập.

## 2. Tạo Gemini key

1. Mở https://aistudio.google.com/app/apikey và đăng nhập tài khoản của bạn.
2. Chọn project hoặc tạo project, rồi Create API key.
3. Mở `.env` trong editor trên máy, điền duy nhất dòng sau bằng key của bạn:

```dotenv
DRIVE_AGENT_GEMINI_API_KEY=dan_key_cua_ban_vao_day
```

Đây là placeholder, phải thay bằng key thật. Không gửi key vào chat và không commit `.env`.
Nếu đã có key thì dùng key hiện có còn hiệu lực. Quyền dùng model và quota phải được
kiểm tra bằng lần gọi thật; key có mặt không chứng minh gọi API thành công.
Nếu cần paid tier, bạn tự bật billing và theo dõi Usage trong AI Studio.
Nguồn: https://ai.google.dev/gemini-api/docs/api-key

## 3. Bật Drive API trong Google Cloud

1. Mở https://console.cloud.google.com/ và chọn project, nên dùng cùng project ở bước 2.
2. Vào APIs & Services → Library.
3. Tìm Google Drive API → Enable.

## 4. Thiết lập Google Auth Platform

1. Mở Google Auth Platform → Get started nếu chưa khởi tạo.
2. Branding: đặt tên DriveAgent Local, chọn support email và developer email của bạn.
3. Audience: chọn External khi dùng Gmail cá nhân. Giữ trạng thái Testing.
4. Test users: thêm email bạn sẽ dùng đăng nhập; thêm từng email thành viên nếu cần.
5. Data Access → Add or remove scopes: thêm `openid`, `email`, `profile` và
   `https://www.googleapis.com/auth/drive.readonly`.

Không bật Publish App ở giai đoạn này. `drive.readonly` thuộc nhóm restricted;
Testing có refresh token hết hạn sau 7 ngày với quyền Drive, khi đó đăng nhập lại.
Nếu người dùng chỉ thuộc một Google Workspace và bạn có quyền cấu hình Internal,
có thể dùng Internal theo chính sách của tổ chức.
Nguồn: https://developers.google.com/identity/protocols/oauth2

## 5. Tạo OAuth client JSON

1. Clients → Create client → Web application, đặt tên DriveAgent Local Web.
2. Authorized JavaScript origins: `http://localhost:8000`.
3. Authorized redirect URIs: **chính xác** `http://localhost:8000/api/auth/google/callback`.
4. Create → Download JSON.
5. Đổi tên file tải về thành `client_secret.json`, đặt cạnh `.env` và README.md,
   không đặt trong backend hoặc frontend. Không đổi thành file `.json.txt`.

Runner local sử dụng UI và API cùng cổng 8000. Nếu đã tạo client cho dev cổng 5173,
bổ sung origin 8000 vào client đó; callback vẫn là 8000.

## 6. Kiểm tra rồi chạy

```powershell
.\backend\.venv\Scripts\python.exe scripts\local_config.py
powershell -ExecutionPolicy Bypass -File scripts\run-local.ps1
```

Lệnh đầu chỉ in OK/MISSING, không in secret. Khi tất cả OK, lệnh thứ hai build UI
và chạy server một tiến trình, không auto-reload. Mở http://localhost:8000.
Giữ cửa sổ terminal mở; Ctrl+C dừng server. Không chạy đồng thời với run-dev.ps1.

Nếu bạn có `.env` từ trước, giữ nguyên key/secret và đặt FRONTEND_ORIGIN,
PUBLIC_BASE_URL thành `http://localhost:8000`. Runner cần môi trường local/development
để cookie hoạt động qua HTTP localhost; không đặt ENVIRONMENT=production ở đây.
Demo login phải false. Runner cho phép HTTP OAuth trong tiến trình loopback này;
không dùng runner để mở cổng LAN, public tunnel hoặc Internet.

## 7. Đăng nhập và nghiệm thu bằng Drive thật

Bạn đăng nhập đầu tiên bằng tài khoản quản trị dự định sử dụng. Hiện app cấp
super_admin cho user đầu tiên và editor cho user mới tiếp theo.
Nếu đã có dữ liệu QA thì không tự xóa database; kiểm tra vai trò trong trang quyền.

1. Tạo thủ công một Google Doc thử nghiệm tên `DriveAgent smoke test`.
2. Nội dung: `Mã kiểm thử là DA-LOCAL-2026. Ngày họp là thứ Sáu.`
3. Kết nối Google Drive, dùng đúng email Test user, chỉ chấp thuận quyền đã dự kiến.
4. Liệt kê Drive, tìm đúng tên file, đọc và xác nhận đúng mã/ngày họp.
5. Chat yêu cầu tìm và đọc file đó; đối chiếu câu trả lời với nội dung gốc.
6. Lập chỉ mục file qua UI, hỏi lại bằng RAG, mở citation để xác nhận đúng file.
7. Lưu một preference không nhạy cảm vào Memory, khởi động lại app và kiểm tra còn lưu.
8. Dùng browser profile riêng cho user B: chat, memory, RAG của A không được xuất hiện.
9. Kiểm tra Audit cho các thao tác vừa thực hiện.

Các bước này cần credential và người dùng chấp thuận OAuth thật, không thể được
thay bằng unit tests. Khi Gemini báo quota/model unavailable, ghi lại mã lỗi và
request ID, không sao chép request header hoặc token vào chat.

## 8. Vận hành và sao lưu

Sau mỗi buổi làm việc, dừng server trước khi sao lưu toàn bộ `data/` để SQLite,
checkpoint và Qdrant không thay đổi trong lúc copy. Sao lưu `.env` và OAuth JSON
riêng vào nơi mã hóa chỉ bạn truy cập; mất APP_SECRET thì credential cũ không giải mã được.
Không đưa các file đó lên GitHub hoặc thư mục chia sẻ công khai.

Nhiều user dùng trên máy này qua browser profile riêng. Máy khác không truy cập được
localhost của máy bạn. Mỗi thành viên muốn chạy riêng phải setup local trên máy mình;
truy cập chung qua LAN/web cần cấu hình triển khai riêng.

## Lỗi thường gặp

- `redirect_uri_mismatch`: kiểm tra URI trong Cloud Console, `.env`, JSON và cổng 8000.
- `access_denied`: thêm đúng email vào Test users, kiểm tra chính sách Workspace.
- `invalid_grant`: token bị thu hồi/hết hạn; kết nối Google lại.
- Port 8000 đang dùng: dừng đúng phiên DriveAgent cũ trước, không tắt process bất kỳ.
- Gemini 429: kiểm tra Usage/quota/billing; đợi và giảm tần suất gọi.
- Thay APP_SECRET khiến không giải mã được: khôi phục secret cũ từ backup.

Tài liệu này hướng dẫn dùng thật local. Chưa xác nhận Google Drive hoặc Gemini live
cho đến khi hoàn thành bước 7 bằng tài khoản của bạn.
