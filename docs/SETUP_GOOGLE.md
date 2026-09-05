# Thiết lập Google Drive và Gemini

Đây là phần thủ công duy nhất. Bạn không cần đưa API key hoặc OAuth secret cho bất kỳ ai.

## 1. Tạo Gemini API key

1. Mở Google AI Studio: <https://aistudio.google.com/app/apikey>.
2. Tạo API key trong project của bạn.
3. Sao chép `.env.example` thành `.env` nếu script setup chưa làm.
4. Điền `DRIVE_AGENT_GEMINI_API_KEY=key_cua_ban`.

Không thêm dấu nháy. Không commit `.env`.

## 2. Bật Google Drive API

1. Mở <https://console.cloud.google.com/>.
2. Chọn hoặc tạo một Google Cloud project.
3. Vào **APIs & Services > Library**.
4. Tìm **Google Drive API** và chọn **Enable**.

## 3. Cấu hình OAuth consent screen

1. Vào **Google Auth Platform > Branding**.
2. Nhập app name, support email và developer email.
3. Chọn audience phù hợp. Tài khoản Gmail cá nhân dùng **External**.
4. Khi app còn ở Testing, thêm email Google của bạn vào **Test users**.
5. Trong **Data Access**, thêm `openid`, `email`, `profile` và `https://www.googleapis.com/auth/drive.readonly`.

`drive.readonly` là restricted scope theo phân loại Google (không chỉ là sensitive).
Giai đoạn local dùng Testing và danh sách Test users; chưa cần publish công khai.
Refresh token của External/Testing với quyền Drive hết hạn sau 7 ngày, nên cần kết nối lại.
Nguồn: https://developers.google.com/workspace/drive/api/guides/api-specific-auth
và https://developers.google.com/identity/protocols/oauth2.

## 4. Tạo OAuth client

1. Vào **Clients > Create client**.
2. Application type: **Web application**.
3. Authorized JavaScript origins: `http://localhost:5173` và `http://localhost:8000`.
4. Authorized redirect URI: `http://localhost:8000/api/auth/google/callback`.
5. Download JSON.
6. Đổi tên thành `client_secret.json` và đặt ở thư mục gốc của repo.

## 5. Chạy và xác nhận

```powershell
.\scripts\run-dev.ps1
```

Mở <http://localhost:5173>, chọn **Kết nối Google Drive**, đăng nhập đúng test user và kiểm tra màn hình consent chỉ xin quyền đọc.

## Lỗi thường gặp

- `redirect_uri_mismatch`: URI trong Google Cloud phải giống hoàn toàn URI phía trên.
- `access_denied`: email chưa nằm trong Test users hoặc người dùng từ chối scope.
- Không có refresh token: ngắt kết nối app trong Google Account rồi kết nối lại.
- Đổi `APP_SECRET`: credential cũ không giải mã được. Phải đăng nhập lại.
