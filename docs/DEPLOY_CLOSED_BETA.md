# Triển khai closed beta Veridra trên Render + Supabase

Phạm vi: tối đa bốn email được mời, mỗi người tự kết nối Google và dùng Gemini API
key của mình. Hướng dẫn này không yêu cầu gửi secret qua Chat và không đưa dữ liệu local
lên cloud. Trạng thái chỉ được đổi từ **HOLD** sang **PASS** sau mục kiểm chứng cuối tài liệu.

## 1. Những gì được triển khai

- GitHub Actions kiểm tra mã, chạy PostgreSQL contract, test/lint/build, tạo một Docker
  image duy nhất và đẩy chính image đã kiểm tra lên GHCR theo commit SHA.
- Render Free chạy image đó trên một HTTPS origin.
- Supabase Free cung cấp PostgreSQL và bucket Storage riêng tư `veridra-private`.
- Cloud không chạy Qdrant, Langfuse, Grafana, Redis hoặc OCR. Vector RAG dùng embedding
  lưu trong PostgreSQL và cosine/RRF ở lớp dịch vụ. Đây là profile nhẹ cho closed beta,
  không phải pgvector.
- Langfuse/Grafana vẫn là bộ quan sát local của owner; lỗi exporter không làm Chat lỗi.

## 2. Supabase

1. Tạo project mới trong organization của bạn; chọn region gần Render Singapore.
2. Chờ project báo Healthy. Vào **Project Settings → Database** và lấy connection string
   trực tiếp. Dùng pooler URL nếu Supabase khuyến nghị cho IPv4, giữ `sslmode=require`.
3. Đổi driver ở đầu URL thành `postgresql+psycopg://`. Giá trị hoàn chỉnh được dùng cho
   cả `DRIVE_AGENT_DATABASE_URL` và `DRIVE_AGENT_RELATIONAL_STATE_URL`.
4. Vào **Project Settings → API** lấy Project URL và service-role key. Service-role chỉ
   được nhập vào Render; không đặt trong biến `VITE_*`, GitHub source hoặc ảnh chụp.
5. Không cần tạo bucket thủ công: backend tạo bucket private `veridra-private` nếu chưa có.
   Nếu tạo thủ công, chắc chắn **Public bucket** đang tắt.
6. Không chạy SQL để mở schema `veridra_private` cho `anon`/`authenticated`; startup sẽ
   tạo schema và thu hồi các quyền đó. Truy cập dữ liệu đi qua backend đã xác thực.

## 3. Google OAuth closed beta

1. Google Cloud Console → APIs & Services → OAuth consent screen. Chọn **Testing**.
2. Thêm đúng tối đa bốn test users đã thống nhất; owner cũng phải nằm trong danh sách.
3. Credentials → Create credentials → OAuth client ID → **Web application**.
4. Chưa có URL Render thì để bước redirect lại sau. Khi URL có dạng
   `https://veridra-closed-beta.onrender.com`, thêm:
   `https://veridra-closed-beta.onrender.com/api/auth/google/callback`.
5. Client ID và client secret được nhập thẳng vào Render. Không upload JSON OAuth vào image.
6. Giữ nguyên scopes trong `.env.example`. Closed beta Testing không được mô tả là ứng dụng
   Google đã xác minh công khai.

## 4. GitHub và GHCR

1. Push branch cần phát hành lên repository `dbp3206-source/DriveAgent`.
2. Mở **Actions → CI**. PostgreSQL contract phải xanh trước job verify.
3. Với push vào `staging/*`, workflow xuất commit SHA và `staging`; không triển khai
   production hoặc thay tag `closed-beta`. Chỉ push vào `main` mới xuất tag `closed-beta`.
   Artifact `release-image-digest.txt` chứa tham chiếu bất biến `image@sha256:...`.
4. Package có thể để private. Trong Render tạo registry credential `veridra-ghcr` bằng
   GitHub username và PAT chỉ có quyền tối thiểu đọc Packages. Không paste PAT vào source.
5. Tùy chọn sau khi có service Render: copy Deploy Hook vào GitHub repository secret
   `RENDER_DEPLOY_HOOK`. Workflow sẽ yêu cầu Render triển khai **đúng digest đã kiểm tra**.
   Không có secret này thì deploy thủ công từ dashboard và phải đối chiếu digest.

## 5. Render Blueprint

1. Render Dashboard → New → Blueprint → chọn repository.
2. Render đọc `render.yaml`; service cần dùng credential `veridra-ghcr` ở bước trên.
   Với candidate staging, chọn branch `staging/*` và thay image bằng digest SHA đã
   xanh CI. Không dùng tag `closed-beta` trước khi nghiệm thu phát hành.
3. Điền các biến `sync: false` ngay trong dashboard:

| Biến | Giá trị lấy từ đâu |
|---|---|
| `DRIVE_AGENT_APP_SECRET` | Chuỗi ngẫu nhiên ≥32 ký tự, chỉ cho môi trường này |
| `DRIVE_AGENT_DATABASE_URL` | Supabase PostgreSQL URL với `postgresql+psycopg` + `sslmode=require` |
| `DRIVE_AGENT_RELATIONAL_STATE_URL` | Cùng project/database như biến trên |
| `DRIVE_AGENT_SUPABASE_URL` | Project URL Supabase |
| `DRIVE_AGENT_SUPABASE_SERVICE_ROLE_KEY` | service-role key, backend-only |
| `DRIVE_AGENT_GOOGLE_OAUTH_CLIENT_ID` | OAuth Web client ID |
| `DRIVE_AGENT_GOOGLE_OAUTH_CLIENT_SECRET` | OAuth Web client secret |
| `DRIVE_AGENT_GOOGLE_REDIRECT_URI` | URL Render + `/api/auth/google/callback` |
| `DRIVE_AGENT_FRONTEND_ORIGIN` | URL Render, không có slash cuối |
| `DRIVE_AGENT_PUBLIC_BASE_URL` | URL Render, không có slash cuối |
| `DRIVE_AGENT_BETA_INVITED_EMAILS` | 1–4 email, phân tách bằng dấu phẩy |
| `DRIVE_AGENT_BETA_OWNER_EMAIL` | Một email trong invite list |
| `DRIVE_AGENT_METRICS_BEARER_TOKEN` | Token ngẫu nhiên ≥32 ký tự |
| `DRIVE_AGENT_SCHEDULER_BEARER_TOKEN` | Token ngẫu nhiên khác metrics token, ≥32 ký tự |

4. `DRIVE_AGENT_BETA_ALLOW_EXTERNAL_WRITES=false` là mặc định an toàn. Chỉ đổi `true`
   sau khi owner chủ động cho phép; từng lần Gmail/Drive ghi vẫn phải preview → approval.
5. Deploy. Backend cố ý từ chối khởi động nếu URL không HTTPS, secret yếu, invite >4,
   cấu hình OAuth cloud thiếu, storage không private hoặc database không phải PostgreSQL TLS.

## 6. Supabase Cron

Sau khi smoke test URL Render đạt, tạo hai HTTP cron job trong Supabase Dashboard. Cả hai
gọi `POST https://<render-host>/api/internal/scheduler/enqueue`, header
`Authorization: Bearer <DRIVE_AGENT_SCHEDULER_BEARER_TOKEN>` và `Content-Type:
application/json`.

- Buổi sáng: body `{"kind":"morning"}`, chạy một lần mỗi sáng theo giờ Việt Nam.
- Trước cuộc họp: body `{"kind":"pre_meeting"}`, chạy mỗi giờ trong giờ làm việc.

Token phải lưu trong Supabase Vault/secret của Cron, không viết vào repository hoặc báo cáo.
Endpoint chỉ enqueue tối đa bốn user đã mời, đang hoạt động và đã kết nối Google. Dedupe theo
ngày/giờ nên gọi lại không tạo bản trùng. Worker có lease 5 phút, tối đa ba attempt; kết quả
read-only được lưu thành phiên Chat. Tác vụ trước cuộc họp đọc Calendar, header Gmail liên
quan và nguồn web mới có citation; lỗi một nguồn được ghi cảnh báo trong bản xem trước.

## 7. Smoke test ngoài máy owner

Ghi commit SHA, digest image, URL và thời điểm vào biên bản trước khi test.

1. Mở `/api/health`; database, storage profile và application phải healthy. Cold start của
   Render Free được đo riêng, không trộn vào latency warm.
2. Email ngoài invite list phải bị từ chối. Owner và một invite user đăng nhập bằng hai
   browser profile riêng; role owner không phụ thuộc người đăng nhập đầu tiên.
3. Mỗi user thêm một Gemini key riêng. User B không xem/đổi được key, Chat, Skill,
   Memory, Gmail, Drive, PDF hoặc evaluation job của A.
4. Upload PDF có text, chờ xử lý nền, hỏi có citation trang. PDF scan-only phải báo rõ
   không có lớp text; OCR đã loại khỏi scope và không được báo thành công rỗng.
5. Chạy Chat/Gmail/Drive read-only. Nếu bật writes, thực hiện đúng một Doc và một Draft
   qua preview → approval → execute → readback; retry không được tạo bản thứ hai.
6. Tạo một evaluation job và một ingestion job, redeploy/restart giữa chừng, xác nhận
   lease/checkpoint tiếp tục và owner isolation còn giữ.
7. Redeploy cùng digest, kiểm tra Chat/Skill/Memory/job/PDF còn tồn tại. Đây mới là test
   persistence; restart không có dữ liệu chưa đủ để kết luận.
8. Dùng bốn browser profile cho bốn user, chạy một lượt Chat nhẹ đồng thời. Ghi tỷ lệ hoàn
   thành, p50/p95, 429/503/timeout và peak memory. Không biến lỗi provider thành PASS.

## 8. Rollback và backup

- Rollback application: chọn digest SHA đã PASS trong GHCR/Render, không rebuild mã cũ.
- Trước migration: backup database theo công cụ Supabase và tải manifest/object test từ
  private Storage. Giữ bản mã hóa, owner-only, tối đa 30 ngày.
- Restore gate: phục hồi vào project staging mới, cấu hình service staging, đăng nhập bằng
  test user và đọc lại tối thiểu một Skill, Memory, evaluation job và PDF object.
- Không coi việc volume/database vẫn còn sau restart là một restore test.

## 9. Điều kiện đổi trạng thái phát hành

Chỉ đổi README/Audit từ HOLD khi: CI của đúng commit xanh; digest triển khai khớp;
PostgreSQL contract chạy thật; OAuth/BYOK chạy qua HTTPS; owner isolation và bốn-user test
đạt; redeploy + restore đạt; benchmark live đủ mẫu số và không còn P0/P1. Render/Supabase
Free có cold-start, quota và khả năng pause; đây là giới hạn công bố của closed beta, không
phải cam kết uptime thương mại.
