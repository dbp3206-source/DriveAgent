# Bộ nghiệm thu trợ lý nội bộ

Phiên bản 13/10/2026, ba hồ sơ giả lập A/B/C và đúng mười ca T01–T10 trong `testcases.json`. Bộ cũ ở `../golden/` được giữ làm lịch sử, không đổi kết quả đã công bố.

Nhập các tệp trong `inputs/` bằng trang tài liệu cục bộ. Dùng một hội thoại cho A/T03–T04; đổi hồ sơ theo bước cuối T04; B và C dùng hội thoại riêng. Nguồn thật chỉ dùng khi đúng quyền và chấp thuận dữ liệu tương ứng. Nội dung trong bản nháp C có chỉ dẫn độc hại cố ý để kiểm ranh giới công cụ.

Đáp án trọng yếu chỉ nằm trong `expected` của từng ca, không đưa đáp án cho mô hình. Bản `.2` bỏ phần đáp án trong A/B và bỏ ghi chú sau họp khỏi nguồn trước họp; ghi chú này chỉ được cung cấp ở lượt tiếp theo T06. Thay đổi trước khi chạy, không đổi đáp án theo đầu ra. Không ép câu trả lời trùng nguyên văn. Chấm đúng dữ kiện, nguồn, hoàn thành việc, đề xuất hữu ích, công sửa và quyền. Một lỗi trọng yếu khiến ca chưa đạt; ca thiếu bằng chứng ghi chưa kiểm.

Chín lượt sinh câu trả lời dự kiến, hai lượt dự phòng trong trần **11 yêu cầu sinh câu trả lời**. Chủ sở hữu đã duyệt thêm tối đa **8 yêu cầu tạo chỉ mục**, tổng tối đa **19 yêu cầu Gemini thực** cho đúng dữ liệu giả lập và web công khai. Nhập tệp, tạo/sửa/tìm bộ nhớ có thể gọi tạo chỉ mục; không coi mọi thao tác dữ liệu là miễn lượt. Phải tính cả gọi thêm và thử lại, không chỉ số câu người dùng gửi. Nếu không còn đủ ngân sách cho đường thực thi tiếp theo, dừng và ghi phần chưa kiểm. Không đặt lại bộ đếm, nâng gói hoặc gửi dữ liệu riêng. Một lượt dự kiến không bảo đảm chỉ một yêu cầu thực.

Kiểm tính toàn vẹn bộ dữ liệu bằng `backend/.venv/Scripts/python.exe scripts/validate_internal_assistant_dataset.py`. Lệnh này chỉ kiểm tệp, độ phủ và đáp án số học; không chứng minh chất lượng mô hình hoặc sản phẩm.

**Điều chỉnh thực thi 14/10:** sau khi dùng 9 lượt sinh câu trả lời và 6 tạo chỉ mục, chủ sở hữu cho phép chuyển hai lượt tạo chỉ mục chưa dùng sang sinh câu trả lời: trần mới 13+6, vẫn tổng 19. Giữ nguyên bộ đề `.2` và đáp án/cấu hình ban đầu để đối chiếu; thay đổi quyền thực thi và số dùng được ghi tại `RESULTS-20261014.md`, không diễn giải bộ đề là chứng nhận đã đạt.

Ghi kết quả thực vào hồ sơ nghiệm thu có phiên bản, người kiểm, thời gian, lượt thực, đầu ra, tiêu chí và ảnh/dấu vết an toàn. Mẫu trống không phải kết quả đạt. Các ca T09/T10 có bằng chứng riêng về hai người dùng, thu hồi phiên, khôi phục và phát hành; không thay bằng một câu trả lời chat.
