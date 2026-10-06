# Đợt nghiệm thu cuối — chốt phạm vi 06/10/2026

## Đối soát mới nhất

Bản 239317f đã qua CI 37485692007, triển khai Live trên Render bằng ảnh
`sha256:c540782728f23f2a533af148781e93943e5fc41cf79a86b50a5424c1845471c3`,
đợt `dep-db2h888m7kps73ervvn0`, 15:32:37 UTC ngày 06/10/2026. Phép kiểm
Bosch sau sửa hoàn tất 29,8 giây: phần thân, bảng nguồn và thẻ liên kết khớp
mã. Không coi cả hồ sơ đạt: tin chưa chứng minh liên quan Việt Nam, chưa tách
ngày sự kiện và chưa có số liệu riêng của đơn vị Việt Nam.

Vault đã được xác nhận tồn tại đúng tên, không đọc giá trị. Bật pg_cron 1.6.4
và pg_net 0.20.4. Lịch thử tự tắt bằng cron.alter_job sau lần chạy thành công
lúc 15:36 UTC; không có lịch lặp đang bật. Lần đầu dùng UPDATE cron.job bị
chặn quyền, chưa phát sinh yêu cầu HTTP. Lần sau gọi HTTP nhưng nhận 403:
“Yêu cầu ghi phải bắt nguồn từ giao diện Veridra.” Chưa đọc Gmail/Drive,
chưa có tác vụ ứng dụng được tạo. Nguyên nhân: lớp kiểm nguồn trình duyệt
áp nhầm vào điểm gọi máy chủ đã có xác thực bearer riêng. Sửa đúng một đường
dẫn hẹn giờ; vẫn bắt buộc bearer, không miễn toàn bộ tiền tố API nội bộ.
Chưa đóng mục hẹn giờ trước khi kiểm lại trên bản triển khai có sửa này.

Bản `c27862b` đã qua CI `37482088860` và chạy Live trên Render. Lượt web
`e4250a0b-245e-4db1-accb-5ce54611500e` hoàn tất 26,5 giây, tin đúng FPT;
không còn dừng tất cả nguồn khi website bị chặn. Website chính vẫn chưa đọc
được nên hồ sơ đầy đủ chưa đạt. Hỏi tiếp sau mở lại hội thoại, lượt
`a62f6689-21bb-4fe5-bee1-9129e4f7ee12`, giữ đúng ngày 14/10/2026, 09:00,
ngân sách chưa xác nhận và ba câu hỏi; 16,8 giây, không tìm web.

Ca đối chứng Bosch `d4cc10b8-5a17-4303-abbe-fddb1b13ab9d` đã đọc website,
28,6 giây, nhưng bảng nguồn có mã `[S#]` không khớp phần thân `[n]` sau đánh
lại số. Nguyên nhân chung: bộ đánh lại số chỉ nhận `[n]`, không nhận `[S#]`
do công cụ web cung cấp. Sửa chung để hai dạng dùng cùng ánh xạ; không đổi
nội dung nguồn, không gắn ngoại lệ theo công ty. 77 phép kiểm nguồn, trích
dẫn theo trang và điều phối đạt; kiểm mã và khoảng trắng đạt. Bản sửa này
chưa được xác nhận trên URL thật, không coi Bosch đã đạt toàn bộ nghiệp vụ.

Hẹn giờ: project đang chạy chưa có pg_cron/pg_net hoặc cron.job; kiểm lại
Vault vẫn chưa có tên `veridra_scheduler_bearer_token`. Chỉ kiểm sự tồn tại,
không đọc giá trị bí mật. Chưa tạo lịch thử khi thiếu bí mật; chưa coi hẹn
giờ đạt. P06 tiếp tục hoãn; E chưa đủ mẫu; F chưa gộp main.

Danh sách điều hành được người dùng yêu cầu tinh gọn. Đợt demo chỉ còn bốn nhóm
bắt buộc A, B, E và F. Nhóm C và D được chủ sở hữu loại khỏi đợt nghiệm thu này
ngày 06/10/2026 để tránh kéo dài tiến độ. Không thêm tính năng hoặc thiết kế lại.
Tiêu chí chưa có bằng chứng giữ chưa đạt.

## Chốt thứ tự theo yêu cầu mới ngày 06/10/2026

Không tiếp tục vòng sửa hoặc gọi mô hình để kiểm PDF trong đợt này. Ca P06
được **để bản sau**, không đổi thành đạt và không xóa kết quả trước đó.
Không mở thêm hạng mục; ưu tiên web, đối soát A/B rồi E/F. Một mục để sau
không đồng nghĩa cả nhóm hoặc toàn sản phẩm đã đạt nghiệm thu.

| Nhóm | Trạng thái đối soát | Bước còn lại, không mở rộng |
|---|---|---|
| A | Ca đổi đầu vào An Bình đã đạt; PDF P06 để sau; báo cáo/dẫn nguồn/bản xem trước chưa đủ bằng chứng đóng toàn nhóm | Không chạy lại PDF; giữ các mục chưa đạt trong biên bản |
| B | Có đọc đầu ngày, lưu/đọc lại, quy trình đã lưu và kiểm nhớ/sửa/xóa; lịch trống; chưa có lần hẹn giờ thật | Kiểm đúng một bản tin đã được cho phép; không coi bấm tạo thủ công là hẹn giờ đạt |
| E | Chưa đủ 24 tác vụ và chưa có điểm tổng hợp hợp lệ | Chỉ tổng hợp bộ đã khóa; kết quả lỗi/thiếu dữ liệu không được chấm đạt |
| F | Bản 947d8ae đã qua CI và chạy Live; hướng dẫn và mẫu có sẵn; main chưa gộp | Chốt tài liệu đúng phạm vi; chỉ gộp bản đã đủ điều kiện, không gọi bản demo hạn chế là production-ready |

Web trên 947d8ae: yêu cầu `1c5cfadf-82d3-4cd7-895f-83ac592697c1`
bị chặn `unavailable_tool`: công cụ `web_research` không nằm trong tập công
cụ được cung cấp. Đã tái hiện độc lập với URL khác: thêm câu phủ định
“không đọc tài liệu riêng” làm bộ phân loại chọn trợ lý bộ nhớ thay vì
nghiên cứu web. Nguyên nhân là bộ lọc bảo vệ nguồn riêng chưa nhận diện
đúng cụm phủ định này, không phải đã chứng minh website nguồn mất kết nối.
Sửa chung chỉ nhận diện các cụm phủ định hoàn chỉnh; dữ liệu riêng được
nêu khẳng định vẫn chặn tìm web. 230 phép kiểm định tuyến, quyền công cụ,
hội thoại và xử lý câu trả lời đạt; kiểm mã đạt. Chưa kiểm live sau sửa,
không gửi lại cùng câu hỏi trên bản chưa đổi.

Ảnh Live 947d8ae: `sha256:6c9b6e6177d08f760a7911a717da32ed4c1bfe10cb6743fc29560aab5a06f5b5`;
CI `37459390271` thành công; Render `dep-db2e5t3ncjis73ed0jt0` Live lúc
12:02:49 UTC. Đây là bằng chứng triển khai, không thay thế điểm nghiệp vụ.

| Nhóm | Việc còn lại | Điều kiện đóng |
|---|---|---|
| A | Độ dài báo cáo, bảo toàn dẫn nguồn, phạm vi số liệu PDF, bản xem trước Doc hết hạn | Ca lỗi đã tái hiện đạt trên URL thật; duyệt và đọc lại đúng, không trùng |
| B | Ba quy trình đầu ngày, trước hẹn, hoàn thiện/lưu; ghép kiểm nguồn, hỏi tiếp, quy trình đã lưu, nhớ/sửa/quên | Hoàn thành xuyên suốt, bảy vai trò và kiểm soát công cụ có dấu vết; hẹn giờ có lần chạy thật |
| C | **LOẠI KHỎI ĐỢT DEMO** — tốc độ mở/sau ngủ, đăng nhập, đổi khóa, lỗi mạng và kiểm lại toàn bộ giao diện | Không tính điểm và không dùng để chứng nhận; giữ giới hạn Render Free đã công bố |
| D | **LOẠI KHỎI ĐỢT DEMO** — khôi phục độc lập, quan sát mở rộng và bộ kiểm an toàn nâng cao | Không tính điểm và không dùng để chứng nhận; lỗi nghiêm trọng về quyền, mất dữ liệu hoặc ghi thiếu duyệt nếu phát hiện vẫn chặn phát hành |
| E | Hoàn thành 24 tác vụ đã khóa, ca bộ nhớ, đối chứng và lỗi giả lập hiện có | Tổng >=8,7/10; nguồn/nghiệp vụ/tin cậy >=9; đủ mẫu, không lỗi nghiêm trọng hoặc quy trình chính thất bại |
| F | Máy sạch, hướng dẫn, demo 10 phút, tài liệu đúng khả năng, CI, main, Render, quay lui | Cùng bản đã nghiệm thu; URL và hướng dẫn dùng được |

Thứ tự A, B, E rồi F; mục A còn lỗi được giữ chờ để tiếp tục B/E/F,
không lặp vô hạn và không đổi nhãn thành đạt. Mỗi mục đạt được
đóng; chỉ kiểm lại khi thay đổi ảnh hưởng trực tiếp. Sửa lỗi theo ca liên quan;
chạy toàn bộ kiểm máy ở bản chốt. Không gọi mô hình lặp để chọn câu trả lời đẹp.
Chỉnh thẩm mỹ nhỏ và tiện ích phụ được để bản sau, không chặn phát hành.

### Cách kiểm gộp đã chốt

- Gom các sửa chữa liên quan vào một bản; kiểm tự động đầy đủ một lần trước triển khai.
- Trên URL thật, kiểm một lần mỗi ca bị ảnh hưởng. Giữ kết quả không đạt để xử lý
  theo nguyên nhân; không gửi lại cùng câu hỏi để chọn một câu trả lời đẹp.
- Dùng một chuỗi nghiệp vụ để đồng thời kiểm chọn nguồn, tính toán, hỏi tiếp,
  nhớ điều đã sửa và lưu/đọc lại. Không chạy lại các thao tác đã có bằng chứng
  khi phần mã tương ứng không thay đổi.
- Chỉ đóng phát hành sau khi các lỗi còn chờ được giải quyết; tiến sang nhóm sau
  không có nghĩa là A đã đạt hoặc sản phẩm đã sẵn sàng phát hành.

Bốn người thật hiện thiếu ba người: giữ CHƯA KIỂM CHỨNG, không chứng nhận từ
tài khoản quản trị. Render miễn phí ngủ khi không hoạt động; không hứa luôn bật.
OCR/PDF ảnh, dịch vụ trả phí, ghi Calendar và hạ tầng nặng vẫn ngoài phạm vi.
PDF có văn bản vẫn trong phạm vi.

## Điểm bắt đầu có bằng chứng

- Staging `3b3afbc`: CI `37333982226` thành công; ảnh
  `sha256:13546369e918ebba41fb621aad27c77b8c2e2d9da279b301684e8f6ca8ccb0c7`
  đang chạy Live trên Render. Bản sửa phục hồi bản xem trước có 187 phép kiểm
  giao diện đạt; sửa bảo toàn dẫn nguồn có 104 phép kiểm đạt. Vẫn cần nghiệm thu
  hai ca này trên URL thật để đóng A.
- Cloud d319f1d là bằng chứng lịch sử: còn báo cáo ngắn, bản sửa định dạng bị từ
  chối và chưa tạo Doc. Không đổi nhãn kết quả cũ thành bằng chứng bản chốt.
- Hồ sơ lịch sử: design-work/qa/LIVE-ACCEPTANCE-20261005.md. Không đổi nhãn các
  phép đo cũ thành bằng chứng bản mới.

Kết thúc khi bốn nhóm A, B, E và F có đủ bằng chứng. C và D giữ nhãn `EXCLUDED`
trong báo cáo cuối, không được đổi thành `PASS`. Khi đó đóng phiên bản và dừng
chỉnh sửa; không mở thêm vòng hoàn thiện chung chung.

## Đối soát cuối ngày 06/10 — chưa đóng phát hành

- Render đã phục vụ `89f9c82`, ảnh `sha256:a970c8dbef2300d1a0167269655ce76e10870649ff76484554ff95d3d960e1c3`;
  CI `37449967840` đạt. Đây không phải xác nhận đủ A/B/E/F.
- B: đọc gộp tối đa năm thư và lịch 24 giờ hoàn tất trong 25,2 giây,
  một lần gọi mô hình; lưu và mở lại giữ dẫn nguồn. Lịch trống nên chưa
  chứng nhận chuẩn bị cho một cuộc hẹn thực tế có dữ liệu.
- Quy trình Minh Phát đọc hai tệp và tính toán hoàn tất 41,7 giây.
  Bước đổi sang An Bình bị chặn khi mô hình gọi công cụ không được cung cấp;
  giữ chưa đạt, không nới quyền để lấy kết quả đẹp.
- Nguồn web không truy cập được đã gọi công cụ thật nhưng chưa có câu trả
  lời hữu ích. Số học PDF đúng nhưng phạm vi dự báo ngân hàng vẫn diễn giải
  sai; A còn chờ. E chưa đủ bộ 24 tác vụ và chưa có điểm tổng hợp lệ.
- Sửa tiếp: lịch sử gọi công cụ được tách theo trợ lý và tập công cụ hiện tại;
  lịch sử hội thoại chính vẫn được nạp đúng người và đúng cuộc trò chuyện.
  Khi công cụ web không trả bằng chứng đủ, trả rõ chưa xác minh và ghi cảnh
  báo, không tính thành công nghiệp vụ. Lỗi quyền, nguồn không an toàn và
  hết hạn mức vẫn bị chặn. 204 phép kiểm liên quan đạt; chưa kiểm live bản sửa.
- `main` chưa gộp. Không công bố sẵn sàng phát hành khi các mục trên chưa đạt.

### Chẩn đoán nguyên nhân trước khi sửa tiếp

- Mã lỗi web thật được đọc từ Nhật ký: `web_source_transport_error`;
  không suy ra hết hạn mức hoặc công cụ chưa được gọi.
- Quy trình đổi đầu vào nạp thành công rồi bị chặn với `unavailable_tool`.
  Nhật ký cũ không giữ tên công cụ bị chặn nên chưa đủ bằng chứng xác định
  nguyên nhân dẫn đến lệnh sai. Không thêm ngoại lệ theo khách hàng kiểm thử.
- Bổ sung chẩn đoán chỉ gồm tên công cụ khớp danh mục máy chủ và danh sách
  công cụ được cấp; tên tự dựng thành `unknown`, không lưu đối số riêng.
  Không nới quyền, không gọi lại, không đổi lỗi thành thành công.
  72 phép kiểm ADK/hội thoại đạt; kiểm mã và khoảng trắng đạt.
  Vẫn cần đọc bằng chứng của lần chạy trên bản triển khai trước khi đóng lỗi.

- Tái hiện độc lập bằng hàm ngữ cảnh: yêu cầu chỉ dùng lượt hiện tại vẫn nạp
  hai lượt cũ và số liệu cũ. Nguyên nhân nằm ở việc giới hạn độ dài lịch sử
  nhưng không giới hạn lịch sử theo phạm vi bằng chứng người dùng yêu cầu.
  Sửa cơ chế chung: mỗi yêu cầu có phiên công cụ riêng; hội thoại chuẩn vẫn
  giữ ngữ cảnh ngắn hạn. Khi có chỉ dẫn rõ chỉ dùng đầu vào hiện tại, loại
  dữ kiện và dẫn nguồn trước mốc đó khỏi ngữ cảnh thực thi, kể cả hỏi tiếp.
  Không xóa lịch sử hiển thị hoặc bộ nhớ dài hạn. Câu phủ định/trích dẫn
  không tự trở thành lệnh bỏ ngữ cảnh. 169 phép kiểm liên quan đạt; kiểm
  riêng các ranh giới ngữ cảnh đạt. Chưa chứng nhận ca live đã hết lỗi.

### Bằng chứng mới và nguyên nhân phạm vi PDF — 06/10/2026

- Bản `37fb6d3` chạy đúng ảnh `sha256:40b4ab7341844a82482bfa553a3749b67d31f28399966f325f2a868fde979b27`,
  CI `37457008642` đạt, Render `dep-db2dqqrncjis73ebrm0g` Live.
- Đổi An Bình trong chính hội thoại Minh Phát: lượt
  `6f88a691-2ceb-4dbb-ad6a-2d29fc6e584e`, 25,8 giây, giữ 8 người và ba câu
  hỏi làm rõ, có `skill_run`; không mang số liệu, dẫn nguồn hoặc phép tính cũ
  vào câu trả lời, không gọi công cụ nguồn bị cấm. Đạt ca đổi đầu vào đã tái hiện.
- Web không truy cập được: `a0916d11-571a-46e5-9dda-70684e529234`, 11,2 giây,
  có `web_research` lỗi và trả rõ chưa xác minh, không bịa lịch hoặc dẫn nguồn.
  Đạt cách xử lý thiếu bằng chứng, không phải đã tìm được thông tin.
- Bản kết quả giả lập Mộc An `5cbbce8b-70de-4fe6-8078-2ea3a474ce5d` mở lại
  trên bản này vẫn v2, bốn câu hỏi, 62 từ/260 ký tự. Không gọi lại mô hình hoặc
  ghi lại kết quả để tạo bằng chứng mới.
- Đối chiếu trực tiếp chữ nguồn ngân hàng trang 1: tiêu đề và phần giải thích
  dùng phạm vi không đồng nhất. Nhãn phạm vi hẹp ở vị trí 539, chi tiết ở 1689;
  đoạn trích 500 ký tự mất cả hai, trong khi phần văn bản đầy đủ vẫn có.
  Đây là lỗi bảo toàn bằng chứng có thể tái hiện, không phải căn cứ khẳng định
  mọi câu dùng nhãn rộng đều do mô hình tự bịa.
- Sửa chung giữ phần thân trang tới 3.000 ký tự trong trích dẫn trang cụ thể,
  giữ chữ cỡ lớn khi có trong giới hạn 4.000 ký tự; không lấy trang kế tiếp.
  Yêu cầu đối chiếu tiêu đề với phần giải thích, công bố phạm vi không thống
  nhất thay vì âm thầm chọn một nhãn. Không đổi oracle hoặc gắn ngoại lệ theo tệp.
  181 phép kiểm liên quan đạt; sau bổ sung kiểm qua công cụ đọc thật với nguồn
  giả lập, 19 phép kiểm nguồn/trích dẫn đạt. Chưa coi P06 đã đạt live sau sửa này.
- A/B/E/F chưa đóng: còn phạm vi PDF trên URL sau sửa, các chuỗi nghiệp vụ đủ
  bước, hẹn giờ chạy thật, bộ 24 tác vụ đủ bằng chứng và bàn giao cùng bản.
  Giữ main chưa gộp; không dùng CI xanh làm chứng nhận chất lượng trả lời.

### Ưu tiên web, tạm gác PDF — 06/10/2026

- Theo quyết định mới, không tiếp tục dùng lượt mô hình để sửa/kiểm P06; mục này
  được hoãn, không ghi đạt. Không mở thêm phạm vi nghiệm thu.
- Bản `d514dc9`: CI `37461715990` đạt, ảnh
  `sha256:bf34cacbd523a69795c91cc276327556c2a25e7f91439a2dee37053752d6ff3a`
  chạy trên Render `dep-db2eeurbc2fs738b5hl0`. Câu hỏi web U04
  `ddc79210-a062-4b19-a0b2-c18eacac5263` đạt: đọc đúng trang Google,
  trả lời hạn mức theo dự án và dẫn nguồn; 32,7 giây. Bước tìm lại ghi chú đã
  quên W03 `1f0b2787-cb91-420a-97af-6adbfe9b0d76` đạt, 30,5 giây.
- Ca FPT `d6ba9fe9-85af-4a9c-8aed-16fb06a8f432` chưa đạt. Nhật ký Render
  xác nhận website trả HTTP 403 ba lần lúc 12:27:32–12:27:33 UTC. Không phải
  lỗi DNS hay hết hạn mức đã được chứng minh: cơ chế bắt mọi HTTPError thành
  lỗi truyền tải, thử lại lỗi bị từ chối và để một website làm dừng toàn bộ
  việc thu thập nguồn. Không tuyên bố đã đọc trang bị chặn.
- Sửa cơ chế chung: 403/404 không thử lại; 408/429/5xx vẫn thử lại có giới hạn.
  Thu thập website và tin công khai độc lập, đồng thời. Chỉ tạo dẫn nguồn cho
  dữ liệu thực sự đã đọc; nguồn tin còn dùng được giữ lại cùng cảnh báo chưa
  đọc được website. Tiêu đề tin không được biến thành dữ kiện toàn văn.
  Chặn địa chỉ mạng nội bộ vẫn giữ nguyên; không vượt bảo vệ website.
- Chưa đóng A/B/E/F hoặc gộp main từ các kết quả riêng này. Cần kiểm bản sửa
  web trên URL sau triển khai và hoàn tất các mục còn lại đã khóa.
- Bản `ab08afa` đã qua CI `37464793196`, Render
  `dep-db2er2p42hec73a9p4b0` Live với ảnh
  `sha256:6d20ac2fd14cbfe949230af385a45cd1de3de4946ec2740c8d03dcac9eedf6b8`.
  Lượt `f2880409-2753-4a77-97ee-00d2e3e3d24f` hoàn tất 25,9 giây, web thành
  công 6,97 giây; đã nói chưa đọc website, không bịa quy mô. Tin không liên
  quan đủ tới công ty nên vẫn chưa đạt nghiệp vụ. Bộ định tuyến hồ sơ tạo
  câu hỏi tổng quan chung, không có tên công ty; bộ tải nguồn lấy câu hỏi
  chung này làm truy vấn tin. Sửa truy vấn mặc định bám tên miền công khai
  đã chọn, không dùng nội dung liên hệ riêng. Không coi công cụ thành công
  là câu trả lời đạt chất lượng.
