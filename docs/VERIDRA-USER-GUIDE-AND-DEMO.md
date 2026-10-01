# Veridra: hướng dẫn sử dụng, phối hợp tính năng và kịch bản demo

Phiên bản hướng dẫn: 30/09/2026. Dành cho người dùng và tester. Các thao tác dưới đây là kịch bản để kiểm chứng; không được hiểu là mọi kịch bản đã đạt nghiệm thu. Bản chạy hiện tại là local tại http://localhost:8000.

## 1. Chuẩn bị trước khi demo

1. Mở Cài đặt. Kiểm tra key Gemini đang chọn và key hiệu lực, quota **local** và circuit. Không hiển thị API key trong màn hình chia sẻ.
2. Kết nối Google bằng tài khoản của bạn, cấp quyền đúng chức năng cần demo. Biểu tượng đã kết nối chưa chứng minh Google cho phép đọc mọi tệp.
3. Chuẩn bị hai tài liệu không nhạy cảm, một thư thử nghiệm, một thư mục Drive riêng cho QA. Ghi lại tên, ID, nội dung kỳ vọng và thời điểm gửi. Không dùng dữ liệu thật trong public demo nếu chưa được phép.
4. Đọc trước nội dung nguồn để có đáp án kiểm chứng. Dùng cùng nguồn khi hỏi tiếp. Không chấm câu trả lời chỉ vì câu chữ trôi chảy.
5. Dành riêng ngân sách request. Quota Google áp dụng theo project/model và còn có RPM/TPM/RPD; đổi key không reset quota của project. Thanh trong Veridra là ledger local, không phải số dư chính thức trên AI Studio.
6. Không demo khi ổ đĩa gần đầy. Dữ liệu SQLite, Qdrant, history và checkpoint cần dung lượng ghi.

## 2. Lộ trình demo 10 phút

| Phút | Màn hình và thao tác | Lời dẫn và điều cần chứng minh |
|---|---|---|
| 0–1 | Bắt đầu, đổi sáng/tối | “Vấn đề không chỉ là hỏi AI, mà là hợp nhất nguồn và kiểm chứng hành động.” Nền chuyển động là trang trí, không phải bằng chứng Agent đang hoạt động. |
| 1–3 | Gmail → đọc thư → Chat | Mở HTML/text, đọc nội dung gốc, hỏi phân tích. Đối chiếu từng claim với thư; click nguồn. |
| 3–5 | Drive/local → Chat → báo cáo | Chọn nguồn, phân tích số liệu, hỏi tiếp. Cho thấy nguồn và phép tính, không chỉ bản tóm tắt. |
| 5–6 | Bản xem trước Doc/Sheet hoặc nháp | Phân biệt “chuẩn bị” và “đã tạo”. Xem trước → duyệt → đọc lại. Không gửi thư trong demo. |
| 6–7 | Kết quả đã lưu | Lưu báo cáo, mở lại và export Markdown. Giải thích dữ liệu lưu local khác với Google Docs. |
| 7–8 | Skills, Bộ nhớ | Skill là quy trình tái sử dụng; bộ nhớ là thông tin/sở thích được quản lý. Chạy một Skill, mở specification. |
| 8–9 | Cách Agent hoạt động, Chat pending | Giải thích orchestrator/specialist/tool. Chỉ gọi là multi-agent khi trace có handoff thực. A2A là giao thức, không phải mọi chat đều chạy A2A. |
| 9–10 | Nhật ký, regression offline | Xem request ID, lỗi, latency, token; chạy regression bằng queue. Nêu điểm đo được và gate còn mở, không tuyên bố không thể lỗi. |

## 3. Hướng dẫn từng màn hình

### Bắt đầu

Chọn một công việc trong các điểm bắt đầu nhanh. Veridra đưa yêu cầu vào Chat để bạn đọc trước; chỉ gửi khi đã đúng nguồn, model, Skill và yêu cầu đầu ra. Nền động riêng của Veridra là nhấn sáng trên canvas caro, tham khảo chuyển động của GetLayers, không sao chép template hoặc tải video ngoài; bật giảm chuyển động hoặc nút tắt nền động để dừng.

### Trò chuyện

- Tạo cuộc trò chuyện mới; dùng tìm kiếm/lịch sử để mở phiên cũ.
- Gõ `/` để chọn nguồn, agent, workflow, output hoặc Skill. Xóa control chip nếu muốn trở về tự động.
- Khi cần dữ liệu cụ thể, nêu tên tệp/người gửi/ngày và đầu ra mong muốn. Ví dụ: “Đọc thư từ [người gửi] nhận ngày [ngày] về [chủ đề], phân biệt dữ kiện và đề xuất.”
- Khi chờ, khu vực sự kiện thực thi hiển thị tool hoặc handoff mà backend thực sự phát sinh. Không có handoff không có nghĩa bị lỗi; nhiều yêu cầu dùng compiler/direct route.
- “Ngừng chờ” dừng phía trình duyệt; không được suy ra tác dụng phụ ở server đã rollback. Kiểm tra history/nhật ký trước khi thử lại thao tác có ghi.
- Hỏi tiếp trong cùng phiên: “Đối chiếu nhận định thứ hai với nguồn”, “Ghi rõ giờ nhận theo metadata Gmail”, “Tính lại với giả định …”. Nếu thiếu dữ liệu, yêu cầu Agent nói rõ thiếu gì.
- Dùng Copy, Lưu ghi chú, Xuất Google Doc hoặc Chuẩn bị thư nháp theo nhu cầu. Bản nháp chưa đạt hợp đồng định dạng phải được xem lại, không dùng như deliverable hoàn chỉnh.

### Gmail

1. Tìm theo người gửi, tiêu đề, ngày; xem các bộ lọc thư/tệp đính kèm.
2. Mở thư. Chuyển HTML và text, kiểm tra thư dài, bảng và link.
3. Ảnh CID là ảnh gắn MIME, ảnh ngoài phụ thuộc máy chủ ảnh. Không hứa xem được ảnh đã bị xóa, cần đăng nhập riêng hoặc chặn truy cập. Nội dung HTML phải qua sandbox/sanitization.
4. Chọn phân tích trong Chat. Prompt: “Tóm tắt 5 mail gần nhất; với mỗi mail ghi người gửi, giờ nhận, chủ đề, việc cần làm và nguồn. Nếu đọc thiếu thì báo số lượng thực.”
5. Daily Skill: “Tổng hợp các mail ‘Bản chi tiết’ của Đinh Bảo Phúc nhận trong ngày hôm nay tính đến lúc chạy. Không yêu cầu đủ 8h/12h/15h/21h. Gộp chủ đề trùng; giữ link nguồn, phát hiện mâu thuẫn.”
6. Nháp: chuẩn bị nội dung, kiểm tra người nhận/subject/body, duyệt đúng một lần; mở Drafts Google để đối chiếu. Tạo nháp không phải gửi thư. Không dùng nút gửi khi mục tiêu chỉ là QA nháp.

### Google Drive, RAG và đầu ra Workspace

1. Tìm theo tên và nội dung; thử phân trang khi có nhiều kết quả. Kiểm tra quyền của từng tệp.
2. Đọc Doc/Sheet/PDF và các định dạng hỗ trợ trong giao diện. Tệp không cho export phải báo lỗi quyền, không được ngầm coi là đã đọc.
3. Nếu dùng RAG, lập chỉ mục tệp đã chọn trước; hỏi có nguồn. Đổi nội dung tệp rồi kiểm tra việc refresh index. RAG không đồng nghĩa luôn đọc live phiên bản mới nhất.
4. Ví dụ: “Phân tích [Sheet A] và [Doc B], tính tổng/ngoại lệ bằng phép tính kiểm chứng được. Mỗi kết luận nêu tệp và dữ kiện. Tạo bản xem trước báo cáo, chưa ghi Google.”
5. Với thư mục đích, cung cấp ID thư mục QA và yêu cầu rõ. Kiểm tra parent ID trong bản xem trước/kết quả, rồi đọc lại trên Drive. Nếu UI không thể chỉ định/kiểm chứng parent, coi case này chưa đạt; không suy từ tên tệp rằng đã vào đúng thư mục.
6. Docs/Sheets: xem trước nội dung, bảng/công thức, duyệt, mở URL Google, đọc lại. Khi timeout sau duyệt, kiểm tra ledger/ID đã tạo trước khi tạo lại. Không chia sẻ public trong bài QA này.

### Tài liệu local

Upload hai tệp nhỏ theo định dạng/giới hạn hiển thị. Kiểm tra text trích xuất và registry. Prompt: “Chỉ dùng [A] và [B] local; lập bảng phần giống/khác, giải thích mâu thuẫn, tổng hợp báo cáo kiến thức chung có nguồn cho từng phần. Không dùng Gmail/Drive.”

Hỏi tiếp về một đoạn cụ thể và yêu cầu chỉ ra nguồn. Thử tệp rỗng, sai định dạng, vượt giới hạn và xóa/lưu trữ nguồn. Tên “local” không đảm bảo nội dung không gửi model: khi hỏi Gemini trên tài liệu, nội dung liên quan có thể được gửi tới API để suy luận; chỉ nạp tài liệu bạn cho phép xử lý.

### Kết quả đã lưu

Lưu note/report từ Chat, tìm và mở lại, export Markdown. Đối chiếu heading, bảng, Unicode tiếng Việt, citation và code block với nội dung ban đầu. Thử báo cáo dài. Artifacts local không tự trở thành Google Doc; cần quy trình xuất/xem trước/duyệt riêng. Nếu thiếu định dạng nghiệp vụ mong muốn, ghi thành gap thay vì giả định đã có PDF/DOCX export ở trang này.

### Skills của tôi

Tạo Skill với tên kỹ thuật ổn định, mục tiêu, quy trình, constraints, capability và output format. Lưu/phiên bản hóa, chạy trên dữ liệu ngày mới; archive Skill rồi xác nhận không còn chạy được.

| Mức | Skill gợi ý | Quy trình và điều kiện đạt |
|---|---|---|
| Dễ | `source_summary` | Đọc nguồn → tóm tắt có citation → nêu phần chưa biết. Không dùng snippet thay toàn văn. |
| Trung bình | `daily_news_brief` | Đọc toàn bộ các thư phù hợp trong ngày → gộp thông tin → report có nguồn/cutoff. Số thư thay đổi theo ngày. |
| Khó | `research_knowledge_brief` | Đọc nhiều nguồn → phát hiện mâu thuẫn → tính toán nếu cần → báo cáo dữ kiện/suy luận/hành động. |
| Chuỗi | Skill đọc nguồn + Skill lập báo cáo | Trong Chat, chọn lần lượt Skill hoặc nhập `/skill:a /skill:b [yêu cầu]`. Tối đa 4 Skill, gọi từng tên; không truyền `a+b` như tên của một Skill. Cần trace chứng minh các bước đã chạy. |

Đây là mẫu specification để bạn tạo bằng các capability có trong form, không phải khẳng định mọi tên mẫu đã lưu sẵn. Union capability không được dùng để vượt OAuth/RBAC. Một bước thất bại phải báo rõ, không tuyên bố toàn chuỗi hoàn tất.

### Bộ nhớ

Thêm thủ công trong Bộ nhớ hoặc dùng “Ghi nhớ rằng tôi muốn câu trả lời có bảng đối chiếu”. Mở Bộ nhớ kiểm tra record đã lưu; hỏi lại ở phiên khác; sửa/archive và xác nhận không tiếp tục áp dụng thông tin đã archive. Không lưu mật khẩu/API key. Không giả định hệ thống tự nhớ mọi câu chat.

### Cách Agent hoạt động và A2A/MCP

Đọc theo hành trình: pain point → nguồn → hiểu → tool/hành động → kiểm chứng. Phần mô phỏng là giải thích, không phải trace của yêu cầu bạn vừa chạy. Đối chiếu với trace Chat hoặc Nhật ký.

Multi-agent của ADK gồm orchestrator và các specialist theo nguồn/capability. Trace `from → to` chứng minh handoff thực. A2A là trao đổi theo agent card/message protocol; MCP là protocol cung cấp tools/resources. Các endpoint `/api/a2a` và `/api/mcp` cần authentication tương ứng; không paste API key vào URL. Dùng bài protocol QA hiện có để xác nhận thực; đừng đánh đồng icon/diagram với kết nối A2A đã chạy.

### Nhật ký / AgentOps

- Tìm request ID từ lỗi Chat, đối chiếu tool events, status và latency. Tool success không phải business success.
- Xem benchmark từng dòng: metric, mẫu số và phạm vi. N/A không tự trở thành đạt.
- Bấm **Chạy regression offline**: job được lưu SQLite ở local hoặc PostgreSQL ở cloud, worker thực thi, checkpoint mỗi suite và poll trạng thái. Refresh trang sẽ nạp lượt gần nhất. Quota model không bị tiêu thụ.
- Cố ý restart backend trong lúc một job đang running: chờ lease 120 giây hết, worker lấy lại job và bỏ qua suite đã checkpoint. Tối đa 3 attempt. Chỉ thực hiện trên môi trường QA; không dừng lúc đang ghi Google.
- Queue hiện áp dụng cho evaluation offline, **không** phải durable chat/A2A tổng quát. Chat vẫn có thời hạn request và lịch sử/approval ledger riêng.
- OpenTelemetry local: `data/otel/trace-YYYYMMDD.jsonl`, request/agent/tool span có trace ID, span ID, parent ID và request ID. Không có prompt/body/key; giữ 30 ngày. Không gửi Langfuse Cloud mặc định.
- Grafana hiện xem metrics qua Prometheus. Trace-file OpenTelemetry chưa tự xuất hiện thành waterfall trong Grafana; cần tuyến OTLP/trace backend đã kiểm chứng.

### Phân quyền và Cài đặt

Phân quyền hiển thị RBAC và OAuth độc lập: có một quyền không thay thế quyền còn lại. Chỉ sửa role khi có bài QA rõ ràng; không dùng admin để che lỗi role thường. Trong Cài đặt, quản lý kết nối, model/key, quota, theme và trạng thái hệ thống theo nhóm. Mascot cho biết trạng thái/quota local; key hiệu lực có thể khác key bạn chọn khi fallback đang hoạt động.

## 4. Ma trận tester liên tính năng

| Case | Chuỗi thao tác | Cách đối chiếu để PASS |
|---|---|---|
| E1 | Gmail → Chat → hỏi tiếp giờ | Count và metadata từng thư khớp Gmail, không dùng nhãn giờ subject làm giờ nhận. |
| E2 | Drive hai nguồn → phép tính → Doc → thư mục | Đúng inputs, số học, citation; preview đúng; readback ID/content/parent; retry không tạo bản thứ hai. |
| E3 | Hai local sources → mâu thuẫn → report → artifact | Không dùng nguồn ngoài; đúng source binding; export giữ cấu trúc. |
| E4 | Skill ngày → Skill report → artifact | Từng Skill thật được gọi; chạy ngày khác dùng dữ liệu mới, không tái dùng nội dung cũ. |
| E5 | Chat ghi nhớ → phiên khác → sửa/archive | Thông tin đúng user, thực sự hiện trong Memory, không dùng record archive. |
| E6 | Key A → B trong lúc chat | Request đang chạy dùng key đã pin; lượt mới dùng B; mascot không hiển thị ledger A là B. |
| E7 | Hai user, nhiều phiên | User B không thấy thư/Drive/Skill/Memory/key/job của A. Dùng hai profile trình duyệt độc lập. |
| E8 | Offline evaluation → restart → resume | Job checkpoint giữ nguyên; không lặp suite đã xong; retry hữu hạn; không gọi Gemini/Google. |
| E9 | Chat lỗi/chậm → trace → metrics | Cùng request ID; thấy tool/agent thật; latency/token có mẫu số; không suy 503 là hết quota. |
| E10 | CI → image → boot/health → restore | Cùng commit/lockfiles, image khởi động, volume bền sau redeploy, restore đọc lại dữ liệu. |

Ghi biên bản mỗi case: ngày/build, user role, model, source hash/ID, inputs, output, expected/actual, request ID, screenshot, PASS/FAIL và giới hạn. Không đưa nội dung riêng tư vào Git hoặc báo cáo public.

## 5. Các bước cần người dùng khi máy chưa có Docker/host

1. Với máy local, Docker chỉ cần khi tự kiểm tra image; không cần chạy stack quan sát nặng để dùng sản phẩm. Cloud dùng image do CI tạo, PostgreSQL và private Storage theo [hướng dẫn deploy](DEPLOY_CLOSED_BETA.md).
2. Cài Docker Desktop từ nguồn chính thức và bật WSL2/virtualization nếu máy yêu cầu; reboot khi installer yêu cầu. Không tắt security policy để ép cài.
3. Xác nhận `docker version` có cả Client và Server. Tắt backend local trước khi dùng cùng port 8000.
4. Tại repository, chạy `docker compose build`, rồi `docker compose up -d`, `docker compose ps`, `docker compose logs --tail 50 app`.
5. `.env` và Google OAuth client JSON không nằm trong image/Git. Cloud nhập OAuth client ID/secret trực tiếp vào secret của Render; URL redirect phải khớp URL HTTPS thật.
6. Kiểm tra http://localhost:8000/api/health và đăng nhập, rồi chạy E1–E10. Không gắn container vào public internet bằng development config.
7. CI chỉ được chứng nhận khi GitHub Actions của đúng commit thực sự xanh. Artifact image được lưu theo SHA; không auto-deploy production chưa có host/secret/restore gate.
8. Langfuse local đã triển khai và có OTLP HTTP/JSON exporter metadata-only thật. Mở `http://localhost:3035`; thông tin đăng nhập riêng ở `ops/secrets/langfuse-owner-login.txt`. Xem **Tracing** trong project Veridra metadata-only: request → agent → tool, cùng trace ID. Không có prompt/body/key. Khởi động app với `scripts/run-local.ps1 -WithLocalLangfuse`; hướng dẫn chi tiết ở `ops/README.md`.

### Kết quả Docker thực ngày 30/09

Docker đã hoạt động. Image `veridra:qa-20260930` build thành công; môi trường QA
riêng chạy ở `http://127.0.0.1:8010`, không có key/OAuth người dùng. Đã kiểm tra
đăng nhập bắt buộc, owner isolation của job, worker đủ bốn suite, volume giữ job
sau tạo lại container, UID non-root 10001, PDF/DOCX tiếng Việt và bí mật không nằm
trong image. Đây không phải việc di chuyển tài khoản Google thật vào container.
Ứng dụng với tài khoản đang dùng vẫn ở cổng 8000. Các bước “Docker chưa cài” phía
trên là hướng dẫn cho máy mới, không còn là trạng thái máy hiện tại.

Trong demo observability: mở Nhật ký → chạy regression offline → thấy bốn suite
hoàn tất → reload vẫn thấy đúng job; mở Langfuse để truy trace; mở Grafana để xem
metrics. Không gọi những số này là điểm chất lượng toàn sản phẩm. Long-running
Chat hiện chưa có durable resume như job evaluation.

Nguồn tham khảo: [GetLayers, chính sách sử dụng](https://www.getlayers.ai/), [Langfuse self-host Docker Compose](https://langfuse.com/self-hosting/deployment/docker-compose), [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/). Hướng dẫn này không cam kết quyền sử dụng commercial template của GetLayers; nền Veridra là implementation riêng.
