# Nghiệm thu cuối theo phạm vi đã chốt

## Quyết định và phạm vi

Sau đợt kiểm duyệt ngày 10/10/2026, người dùng yêu cầu thực hiện phần còn
lại và nghiệm thu. Phạm vi cuối gồm đúng hai lỗi bên dưới và một lượt kiểm
gộp sau triển khai. Đây là bản dùng thật có giới hạn cho quản trị/nhóm nhỏ
đã được kiểm và bài demo dự án. Quyết định này tiếp nối
[bàn giao trước đó](DEMO-HANDOFF-20261010.md).

## Hai lỗi phải đóng

| Mục | Nguyên nhân | Cách sửa và bằng chứng trong máy |
|---|---|---|
| Liên kết nguồn chính thức | Khi chuyển HTML thành chữ, bộ đọc bỏ địa chỉ trong thẻ liên kết. Bước tìm website được nguồn chính thức dẫn tới không còn địa chỉ để đọc tiếp. | Giữ địa chỉ HTTPS cạnh nhãn và ngữ cảnh; giải đường dẫn tương đối theo trang nguồn. Kiểm qua tuyến thu thập thật với máy chủ thử: đọc trang cơ quan → lấy liên kết → đọc trang tổ chức; vẫn giữ giới hạn hai trang, xác minh địa chỉ và không chuyển khóa tìm kiếm sang website. |
| Tỷ lệ thành công của Nhật ký | Ô tổng hợp chỉ đếm lượt có thời gian đo; biểu đồ đếm mọi lượt đã kết thúc. Cùng dữ liệu hiện 82/96 = 85% và 84/98 = 86%. | Dùng chung cách tính trên mọi lượt đã kết thúc; lượt đang chạy không tính thành lỗi. Tốc độ chỉ dùng thời gian đo hợp lệ, thiếu dữ liệu không coi là 0. Tái hiện bộ 100 sự kiện: cả hai nơi phải là 84/98 = 86%. |

Kiểm trong máy: 129 phép kiểm máy chủ liên quan đạt trong 29,01 giây;
190 phép kiểm giao diện đạt. Đây là kiểm hành vi mã, không phải điểm
chất lượng câu trả lời của Gemini.

## Điều kiện bàn giao

1. Kiểm mã, dựng giao diện và toàn bộ kiểm GitHub của bản sửa thành công.
2. Render chạy đúng ảnh bất biến được kiểm; địa chỉ sản phẩm và kiểm sức khỏe phản hồi tốt.
3. Mở Nhật ký, đối soát tỷ lệ giữa ô tổng hợp và biểu đồ; kiểm các màn hình nguồn/kết quả đã lưu/trò chuyện và ảnh đã yêu cầu. Ghi biên nhận bản, số đo và ảnh chụp thực tế.
4. Ghi quyết định nghiệm thu có giới hạn, cập nhật main và khóa đợt sửa.

Trạng thái: **ĐÃ NGHIỆM THU THEO PHẠM VI ĐÃ CHỐT**, lúc 22:50 ngày
10/10/2026 (GMT+7). Hai lỗi đã đóng; bốn điều kiện bàn giao bên trên đạt.
Kết thúc đợt sửa ứng dụng. Đây là quyết định dùng thật có giới hạn và demo,
không đổi kết quả bộ nghiệm thu đầy đủ thành đạt.

## Biên nhận bản cuối

- [Sản phẩm đang chạy](https://veridra-closed-beta.onrender.com).
- [Mã ứng dụng trên main](https://github.com/dbp3206-source/DriveAgent/commit/f1c91eac98f29d7decc7023a57bb04dff62399c9).
- [Kiểm phát hành GitHub 38064377009](https://github.com/dbp3206-source/DriveAgent/actions/runs/38064377009): thành công. PostgreSQL 12 phép kiểm đạt; máy chủ 1.575 đạt, 13 bỏ qua, độ phủ 88,02%; giao diện 190 đạt. Kiểm mã, phụ thuộc, kiểm ngoại tuyến, đóng gói và xuất PDF tiếng Việt đều đạt. Các số này không phải điểm chất lượng câu trả lời.
- Ảnh đã kiểm: `ghcr.io/dbp3206-source/veridra@sha256:ff67916a457dc46fa4521972e011f7a9d7a15194223282326815d1706d4a079c`.
- [Render dep-db55ql0473hc73a03sc0](https://dashboard.render.com/web/srv-dav5v560tbcc73dpjlc0/deploys/dep-db55ql0473hc73a03sc0): đúng ảnh trên, Live lúc 22:46:04. Máy chủ khởi động lúc 22:46:00, lắng nghe tại `0.0.0.0:10000`.
- `/api/health`: HTTP 200, `status=ok`, cơ sở dữ liệu và kho tệp tốt. Không gọi thử Gemini/Google từ kiểm sức khỏe.
- Không có bản ghi mức lỗi từ 22:44:20 đến 22:50:39 trong nhật ký Render được đọc. Không suy rộng thành cam kết không bao giờ có lỗi.
- Bản ghi bàn giao tiếp theo chỉ cập nhật tài liệu và sổ nghiệm thu; không thay mã ứng dụng hoặc ảnh đang chạy.

## Một lượt kiểm gộp trên bản thật

| Kiểm | Kết quả quan sát |
|---|---|
| Nhật ký | 100 sự kiện đã tải: 98 đã kết thúc, 84 thành công, 14 lỗi/từ chối, 2 đang chạy. Ô tổng hợp và biểu đồ đều 86%. Hai lượt nhập nguồn thành công không có thời gian vẫn được tính vào tỷ lệ; bảng công cụ không bịa thời gian cho chúng. |
| Giao diện Nhật ký | Mở thật tại 1440×1000, 542×676 và 390×844; không tràn ngang. Ảnh màn hình rộng và điện thoại đã được đọc lại. Trả kích thước thanh bên về mặc định sau kiểm. |
| Drive | Mặc định gần đây, danh sách thật tải được. Lọc thư mục chỉ trả thư mục; lọc tệp không trả thư mục; gắn sao có 25 mục. Không lập chỉ mục hoặc sửa tệp. |
| Kết quả và bộ nhớ | 5 kết quả còn đọc được; Mộc An phiên bản 2 đúng bốn câu hỏi, ngân sách chưa xác nhận. Bộ nhớ còn 2 mục, 1 đang dùng và 1 đã cất; ghi chú thử đã xóa không xuất hiện lại. Không lưu/sửa/xóa thêm. |
| Trò chuyện và ảnh | Phiên đăng nhập còn hiệu lực; lịch sử và nguồn đã lưu mở được. Ảnh người dùng tại `/harness/veridra-verified-workflow.png` tải đủ 1672×941. Trang bắt đầu mở được. Không thấy lỗi bảng điều khiển trong lượt quan sát. |

Lượt bàn giao này dùng **0 lượt Gemini**, **0 lần ghi Google**, không đổi
khóa, bộ đếm hoặc gói dịch vụ. Sửa liên kết nguồn được chứng minh qua tuyến
thu thập tự động và đúng ảnh triển khai; không giả là đã tìm lại ASIAD trên cloud.
Ảnh tài khoản và biên nhận thô được giữ riêng trong
`design-work/qa/private/final-bounded-20261010/`, không đăng lên GitHub.

Nếu cần quay lui ứng dụng, giữ ảnh trước lượt này:
`ghcr.io/dbp3206-source/veridra@sha256:3523552af5ba648ce8c857556d781f848503b208ccf97e08911aaa12c004c2dd`.
Chỉ dùng khi người vận hành quyết định quay lui; không đổi dữ liệu hoặc bí mật.

## Cách dùng bằng chứng A/B/E/F

- A: hai lỗi cuối được kiểm đúng phần bị ảnh hưởng; giữ biên nhận câu trả lời và nguồn đã đối soát trước đó.
- B: giữ biên nhận hỏi tiếp/đổi dữ kiện, tính toán, quy trình đã lưu, bộ nhớ và kết quả xuất; mở lại dữ liệu hiện có trên bản mới để kiểm tính liên tục. Không tạo lại ghi chú đã xóa hoặc tài liệu Google.
- E: giữ kết quả và giới hạn thật. Không cấp điểm tổng 8,7/10 từ số phép kiểm mã, không đổi ca thiếu bằng chứng thành đạt. Dùng quyết định nghiệm thu có giới hạn đã được người dùng chấp nhận.
- F: bản ứng dụng đã kiểm trên main, đúng ảnh Render, URL dùng được, biên nhận và hướng dẫn demo được bàn giao.

Các giới hạn đã chấp nhận ở biên bản trước vẫn áp dụng: một quản trị thật;
PDF hoãn; C/D loại khỏi đợt demo; lịch thật trống; chưa có tổng điểm của bộ
24 tác vụ, chuỗi đầy đủ bảy vai trò và kiểm hình thức Word. Không suy từ
sửa mất liên kết rằng ASIAD đã tìm được nguồn. Đây không phải chứng nhận
vận hành nhiều người dùng ở quy mô lớn.

Sau khi bốn điều kiện bàn giao đạt, đợt sửa kết thúc. Các yêu cầu mới được
xử lý như một đợt riêng khi người dùng yêu cầu.
