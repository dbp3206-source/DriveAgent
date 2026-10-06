# Bắt đầu dùng Veridra trên máy local

Mục tiêu hiện tại: bạn hoặc nhóm nhỏ đăng nhập Google và dùng dữ liệu Drive thật
trên máy này. Chưa cần domain, VPS, Cloud SQL hoặc Redis. Đây chưa phải dịch vụ public.

## 1. Mở đúng thư mục

Máy mới cần Git, Python 3.11/3.12 và Node.js 22.12 trở lên (hoặc Node.js 20.19 trở lên); không dùng bản Node.js 20 cũ. Mở PowerShell tại thư mục bạn muốn lưu mã, rồi chạy:

```powershell
git clone https://github.com/dbp3206-source/DriveAgent.git
cd DriveAgent
git switch staging/veridra-closed-beta-20261001
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

Nhánh trên là bản thử, chưa thay thế bản phát hành đã nghiệm thu. Khi có phiên bản được chốt, dùng đúng mã phiên bản ghi trong biên bản thay vì tự chọn bản mới nhất. Không sao chép `.env`, cơ sở dữ liệu hoặc tài khoản Google của người khác.

### Ghi chú riêng cho máy phát triển hiện tại

Đường dẫn dưới đây chỉ dành cho máy của chủ dự án, không phải bước setup máy mới.
Trên máy đang dùng trong dự án, mở PowerShell và chạy:

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
App mặc định dùng `gemini-3.5-flash-lite` cho trò chuyện, `gemini-3.8-flash` dự phòng và
`gemini-embedding-2` (768 chiều); trang Cài đặt hiển thị đúng cấu hình đang chạy.
Phạm vi nghiệm thu chỉ dùng dịch vụ miễn phí; không tự bật thanh toán hoặc chuyển sang tuyến trả phí để vượt lỗi hạn mức.
Nguồn: https://ai.google.dev/gemini-api/docs/api-key

## 3. Bật các Google Workspace API trong Google Cloud

1. Mở https://console.cloud.google.com/ và chọn project, nên dùng cùng project ở bước 2.
2. Vào APIs & Services → Library.
3. Tìm và bật lần lượt: **Google Drive API**, **Google Docs API**,
   **Google Sheets API**, **Gmail API** và **Google Calendar API**.

Chỉ cấp OAuth scope là chưa đủ: nếu API tương ứng vẫn ở trạng thái Disabled,
Google sẽ trả 403 dù đăng nhập đã thành công. Mở trang chi tiết từng API và xác nhận
trạng thái là **Enabled** trước khi thử tạo Docs hoặc Sheets.

## 4. Thiết lập Google Auth Platform

1. Mở Google Auth Platform → Get started nếu chưa khởi tạo.
2. Branding: đặt tên Veridra Local, chọn support email và developer email của bạn.
3. Audience: chọn External khi dùng Gmail cá nhân. Giữ trạng thái Testing.
4. Test users: thêm email bạn sẽ dùng đăng nhập; thêm từng email thành viên nếu cần.
5. Data Access → Add or remove scopes: thêm `openid`, `email`, `profile`,
   `https://www.googleapis.com/auth/drive.readonly`,
   `https://www.googleapis.com/auth/drive.file`,
   `https://www.googleapis.com/auth/gmail.readonly` và
   `https://www.googleapis.com/auth/gmail.compose` (tạo nháp và chỉ gửi sau bước xác nhận),
   `https://www.googleapis.com/auth/calendar.readonly` (chỉ đọc lịch).

Không bật Publish App ở giai đoạn này. Một số scope trên thuộc nhóm sensitive/restricted;
Testing có refresh token hết hạn sau 7 ngày với quyền Drive, khi đó đăng nhập lại.
Nếu người dùng chỉ thuộc một Google Workspace và bạn có quyền cấu hình Internal,
có thể dùng Internal theo chính sách của tổ chức.
Nguồn: https://developers.google.com/identity/protocols/oauth2

## 5. Tạo OAuth client JSON

1. Clients → Create client → Web application, đặt tên Veridra Local Web.
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

1. Tạo thủ công một Google Doc thử nghiệm tên `Veridra smoke test`.
2. Nội dung: `Mã kiểm thử là DA-LOCAL-2026. Ngày họp là thứ Sáu.`
3. Kết nối Google Drive, dùng đúng email Test user, chỉ chấp thuận quyền đã dự kiến.
4. Liệt kê Drive, tìm đúng tên file, đọc và xác nhận đúng mã/ngày họp.
5. Chat yêu cầu tìm và đọc file đó; đối chiếu câu trả lời với nội dung gốc.
6. Lập chỉ mục file qua UI, hỏi lại bằng RAG, mở citation để xác nhận đúng file.
7. Lưu một preference không nhạy cảm vào Memory, khởi động lại app và kiểm tra còn lưu.
8. Dùng browser profile riêng cho user B: chat, memory, RAG của A không được xuất hiện.
9. Tạo thử một Docs và Sheets qua luồng xem trước → xác nhận → đọc lại; soạn một Gmail và chỉ gửi sau khi kiểm tra bản duyệt.
10. Kiểm tra Audit cho các thao tác vừa thực hiện.

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
- `api_disabled` hoặc Google 403 sau khi đã cấp scope: quay lại bước 3 và bật đúng
  Docs/Sheets/Gmail API trong chính Google Cloud project của OAuth client.
- `invalid_grant`: token bị thu hồi/hết hạn; kết nối Google lại.
- Port 8000 đang dùng: dừng đúng phiên Veridra cũ trước, không tắt process bất kỳ.
- Gemini 429: kiểm tra Usage/quota/billing; đợi và giảm tần suất gọi.
- Thay APP_SECRET khiến không giải mã được: khôi phục secret cũ từ backup.

## Sao lưu và khôi phục dữ liệu

Dừng Veridra bằng `Ctrl+C` trước khi sao lưu. Script từ chối chạy nếu cổng 8000
còn lắng nghe, copy toàn bộ `data/`, kiểm SHA-256 từng file và ghi `manifest.json`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/backup-local.ps1
```

Khôi phục mặc định vào `data-restored/` để bạn kiểm tra trước, không ghi đè `data/`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/restore-local.ps1 `
  -BackupPath ".local-backups\<mốc-thời-gian>"
```

Muốn khôi phục vào `data/`, vẫn phải dừng server và chỉ rõ đích. Nếu thư mục đích
đang có dữ liệu, thêm `-ReplaceExisting`; script sẽ chuyển bản cũ sang thư mục
`data.restore-previous-<mốc-thời-gian>` thay vì xóa, rồi kiểm lại toàn bộ hash:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/restore-local.ps1 `
  -BackupPath ".local-backups\<mốc-thời-gian>" `
  -Destination ".\data" -ReplaceExisting
```

Các script PowerShell trên tạo bản sao **chưa mã hóa**; mã SHA256 chỉ kiểm tra toàn vẹn,
không bảo vệ nội dung. Chỉ giữ bản sao ở thư mục riêng và mã hóa trước khi chuyển sang
thiết bị khác. `.env`, APP_SECRET và OAuth JSON không nằm trong `data/`; sao lưu riêng.

Nếu cần bản dữ liệu mã hóa ngay khi sao lưu, sau khi dừng Veridra và mọi tiến trình ghi,
chạy bằng Python của dự án; thư mục `.local-backups` phải tồn tại và chỉ bạn truy cập:

```powershell
New-Item -ItemType Directory -Path .local-backups -Force
.\backend\.venv\Scripts\python.exe scripts\state_archive.py backup `
  --source .\data --output .\.local-backups\data-private.vrd --port 8000
.\backend\.venv\Scripts\python.exe scripts\state_archive.py restore `
  --archive .\.local-backups\data-private.vrd --destination .\data-restore-check
```

Nhập cùng mật khẩu riêng khi công cụ hỏi, không đưa vào dòng lệnh. Tệp sao lưu và
thư mục khôi phục phải chưa tồn tại; chọn tên mới cho mỗi lần. Công cụ kiểm nội dung
trước khi xuất thư mục khôi phục và không ghi đè dữ liệu đang dùng. Chưa được coi là
khôi phục nghiệp vụ thành công cho đến khi chạy Veridra với bản dữ liệu khôi phục và
đọc lại dữ liệu mẫu. Cơ sở dữ liệu Supabase và bucket cloud không được bao phủ bởi
script này; xem [triển khai cloud](DEPLOY_CLOSED_BETA.md).

Mỗi lần đổi khóa, dự án Google hoặc tài khoản kiểm thử, lặp lại bước 7 và ghi rõ
bản mã đang chạy. Bằng chứng trên tài khoản cũ không chứng nhận tài khoản mới.
