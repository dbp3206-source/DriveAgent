# Chốt phần trả lời từ web — 10/10/2026

## Phạm vi cố định và điểm dừng

Đợt này chỉ sửa năm vấn đề dưới đây. Không bổ sung tính năng, tiêu chí,
mẫu kiểm, vòng chỉnh văn phong hoặc gọi mô hình để đủ số từ. Đánh giá theo
khả năng của mô hình đang dùng: đúng dữ kiện, đúng nguồn, đúng thời gian,
trả lời rõ; không lấy khả năng của mô hình đánh giá làm chuẩn thay thế.

| Vấn đề đã xác nhận | Nguyên nhân | Sửa chung |
|---|---|---|
| Shopee không có câu trả lời | Giới hạn xử lý trong phút của Veridra chặn trước tổng hợp; không có bằng chứng Gemini hết giờ | Chờ bất đồng bộ tối đa 15 giây trong thời gian chờ hiện có, dành thời gian cho tổng hợp; hết ngân sách ngày trả ngay. Hủy yêu cầu không để luồng nền tiếp tục đặt chỗ. Không tăng hoặc đặt lại hạn mức. |
| Câu ASIAD bị mất ý, thiếu ngày cụ thể | Định dạng khối mã bị giữ lại; chỉ chọn vế đầu câu hỏi | Bỏ lớp định dạng, giữ các ý công khai; chuyển hôm qua/ngày mai thành ngày cụ thể theo đồng hồ và múi giờ. |
| Yêu cầu nguồn chính thức chưa được thực thi | Chỉ hướng dẫn/ưu tiên nguồn, chưa chặn nguồn thứ cấp; cắt đầu trang làm mất phần liên quan | Kiểm thẩm quyền và đúng chủ đề trước khi dùng dẫn nguồn; chỉ đọc thêm tối đa hai liên kết chính thức đã được nguồn phù hợp dẫn. Chọn đoạn liên quan trong giới hạn cũ; lưu và tổng hợp cùng một đoạn, không ghép trích đoạn cách xa nhau. |
| Tin FPT sai khoảng ngày và lẫn tin cũ | Chỉ xử lý từng mục có dẫn nguồn riêng, bỏ sót danh sách ngày đăng dùng chung dẫn nguồn | Sửa khung thời gian của báo cáo theo yêu cầu; tách danh sách ngày đăng rõ ràng, giữ dẫn nguồn, chuyển tin cũ sang bối cảnh. Không đổi khoảng ngày sự kiện hay phép so sánh. |
| Lời báo thiếu tin bị thay, số đếm chưa đầy đủ bị hiểu thành quy mô | Bộ kiểm số chưa phân biệt khoảng tìm kiếm với số nghiệp vụ; nguồn có nhiều bộ đếm 1+ | Giữ lời báo chưa xác minh đúng khoảng đã yêu cầu, bỏ gán sai cho website; vẫn chặn số nghiệp vụ thiếu căn cứ. Không diễn giải bộ đếm chưa đầy đủ thành quy mô. Phân biệt dữ kiện đầu vào, dữ kiện web và trạng thái chưa ghi. |

## Bằng chứng đã có

- Đọc lại tám tác vụ đã chạy ngày 09/10: bảy hoàn tất, một Shopee bị giới
  hạn trong phút. Hoàn tất tác vụ không đồng nghĩa câu trả lời đạt chất lượng.
- Vinamilk có dữ kiện tài chính đúng năm và nguồn đã đọc; Samsung không
  đổi tên khách hàng sang đơn vị vận hành website ở lượt mới; Bosch tách
  số liệu tập đoàn. Không gửi lại để cải thiện văn phong.
- Kiểm gộp trong máy: **490 phép kiểm đạt trong 130,19 giây**. Gồm hạn mức,
  hủy yêu cầu, Chat, tổng hợp, nguồn, ngày tin và các trường hợp không được
  áp dụng ngoại lệ. Kiểm quy tắc mã và khoảng trắng đạt.
- Đối soát nguyên câu FPT đã lưu, chỉ trong bộ nhớ máy, với ngày gốc
  09/10: giữ bảy ngày đăng trong khoảng 10/09–09/10, chuyển ba mục cũ
  ra ngoài, giữ dẫn nguồn. Giữ các dữ kiện năm 2025, 3.800 ý tưởng và
  32%; giải thích bộ đếm chưa đầy đủ. Chạy lại phép biến đổi không đổi thêm.
- Kiểm lại đầu vào và nguồn ASIAD đã lưu: giữ chủ đề sau bỏ định dạng;
  U02/U03 có một nguồn cơ quan phù hợp được phép dùng, nguồn báo không
  được dùng thay nguồn chính thức. U01 cũ không có nguồn đúng chủ đề:
  đây là giới hạn của lần thu nguồn cũ, không được đổi thành kết quả đạt.
- Chưa gọi Gemini hoặc Tavily thật trong đợt sửa này. Các phép kiểm trong
  máy và đối soát lại không phải câu trả lời mới trên bản triển khai.

## Bước bàn giao còn lại của riêng phần này

1. Đẩy đúng một bản sửa gộp, đợi toàn bộ kiểm GitHub và ảnh chạy đạt.
2. Triển khai đúng mã ảnh cố định. Kiểm ngắn tối đa hai yêu cầu bị ảnh
   hưởng: Shopee đã khóa và U01 đã khóa; không gửi lại tám câu, Viettel,
   PDF, bộ nhớ hoặc các bước ghi Google. Không tăng hạn mức hay đổi khóa.
3. Ghi kết quả thật, giữ rõ phần chưa kiểm được nếu dịch vụ ngoài từ chối.
   Chốt phần web; không tiếp tục vòng tối ưu câu chữ hoặc mở thêm mẫu.
   Sau đó chỉ đối soát B, tổng hợp E và bàn giao F theo phạm vi đã duyệt.

Không lấy kiểm tự động làm điểm chất lượng E. Không gọi toàn bộ sản phẩm
sẵn sàng vận hành đầy đủ khi C/D đã được loại khỏi đợt demo hoặc các bằng
chứng bắt buộc còn thiếu. Không gộp main trước điều kiện nghiệm thu đã khóa.
Không đưa mã người dùng/phiên, khóa hoặc nguyên văn nội dung riêng lên GitHub.
