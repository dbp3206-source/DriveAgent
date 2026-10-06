from app.agent.routing import extract_explicit_file_id, route_request


def test_named_local_documents_are_all_required():
    route = route_request("So sánh hai tài liệu local banking.pdf và power.pdf theo nguồn.")
    assert [source.arguments["query"] for source in route.sources] == [
        "banking.pdf", "power.pdf"
    ]
    assert all(source.read_match for source in route.sources)


def test_local_report_with_short_source_prohibition_keeps_both_documents():
    route = route_request(
        "Đọc hai tài liệu local first.md và second.md, giải thích phép tính "
        "trong báo cáo 200–240 từ. Không Gmail, Drive, lịch hoặc web."
    )
    assert route.required_sources == ("local",)
    assert [source.arguments["query"] for source in route.sources] == ["first.md", "second.md"]


def test_negative_gmail_mention_does_not_trigger_inbox_read():
    route = route_request("Đọc bảng số liệu tôi cung cấp, không dùng Gmail hoặc Drive.")
    assert route.tool is None


def test_simple_routes_need_no_generation():
    assert route_request("Liệt kê file Drive.").direct
    found = route_request("Tìm file tên proposal.")
    assert found.tool == "drive_search_files"
    assert found.arguments["query"] == "proposal"


def test_complex_request_is_not_mistaken_for_a_write():
    assert not route_request("Tạo báo cáo từ RAG").direct
    assert route_request("Gửi email cho thầy").tool is None
    assert route_request("Chỉ dùng RAG đã lập chỉ mục").tool == "rag_search"


def test_find_read_and_summarize_gathers_named_file():
    route = route_request("Tìm file notes.md, đọc và tóm tắt nội dung.")
    assert route.arguments["query"] == "notes.md"
    assert route.read_match and not route.direct


def test_explicit_rag_wins_over_file_read():
    route = route_request("Chỉ dùng rag_search trên dữ liệu đã lập chỉ mục của notes.md: tóm tắt")
    assert route.tool == "rag_search" and not route.read_match
    assert route.arguments == {
        "query": "Chỉ dùng rag_search trên dữ liệu đã lập chỉ mục của notes.md: tóm tắt",
        "limit": 8,
    }


def test_explicit_rag_source_id_locks_file_and_expands_evidence_window():
    route = route_request(
        "Chỉ dùng RAG trong tệp Drive Evaluation-Harness.pdf "
        "(ID: 11mZ5EtxvMxVXoZveAiBexNhtHLvKKTjg): A/B testing là gì?"
    )

    assert route.tool == "rag_search"
    assert route.arguments == {
        "query": "Chỉ dùng RAG trong tệp Drive Evaluation-Harness.pdf "
        "(ID: 11mZ5EtxvMxVXoZveAiBexNhtHLvKKTjg): A/B testing là gì",
        "limit": 12,
        "file_ids": ["11mZ5EtxvMxVXoZveAiBexNhtHLvKKTjg"],
    }


def test_file_id_parser_rejects_incidental_short_tokens():
    assert extract_explicit_file_id("ID: 1234") is None
    assert extract_explicit_file_id(
        "ID: 11mZ5EtxvMxVXoZveAiBexNhtHLvKKTjg"
    ) == "11mZ5EtxvMxVXoZveAiBexNhtHLvKKTjg"


def test_explicit_drive_id_disambiguates_duplicate_filename():
    route = route_request(
        "Trong tệp Drive Evaluation-Harness.pdf "
        "(ID: 11mZ5EtxvMxVXoZveAiBexNhtHLvKKTjg): Golden Dataset là gì?"
    )

    assert route.tool == "drive_read_file"
    assert not route.read_match and not route.direct
    assert route.arguments == {
        "file_id": "11mZ5EtxvMxVXoZveAiBexNhtHLvKKTjg",
        "max_characters": 120_000,
    }


def test_homepage_recent_file_prompt_reads_latest_non_folder():
    route = route_request("Tóm tắt tệp mới chỉnh sửa gần đây nhất")
    assert route.tool == "drive_list_files" and route.read_match
    assert route.arguments == {"page_size": 1, "exclude_folders": True}


def test_google_doc_title_without_extension():
    route = route_request("tóm tắt nội dung trong docs Web của tôi")
    assert route.tool == "drive_search_files" and route.read_match
    assert route.arguments["query"] == "Web"


def test_homepage_memory_prompt_reads_saved_preferences():
    assert route_request("Tôi đã lưu sở thích trình bày nào?").tool == "memory_search"


def test_explicit_chat_memory_capture_maps_to_governed_memory_save():
    route = route_request("Ghi nhớ rằng tôi thích báo cáo có bảng so sánh")

    assert route.tool == "memory_save"
    assert route.direct is True
    assert route.arguments == {
        "kind": "preference",
        "content": "tôi thích báo cáo có bảng so sánh",
    }


def test_explicit_compound_calculation_uses_safe_direct_route():
    route = route_request(
        "Dùng công cụ calculate tính (125.5 + 24.5) / 3. Trả lời kết quả ngắn gọn."
    )
    assert route.direct is True
    assert route.tool == "calculate"
    assert route.arguments == {
        "operation": "expression",
        "values": ["(125.5 + 24.5) / 3"],
    }


def test_report_with_labelled_calculation_is_not_reduced_to_one_number():
    route = route_request(
        "Viết báo cáo 200–240 từ. Nêu đúng 24 người; phép tính 24 × 12 phút "
        "× 20 ngày = 5.760 phút và giữ dẫn nguồn [1][2]."
    )

    assert route.tool is None
    assert route.direct is False


def test_direct_calculation_requires_two_operands_and_operator():
    route = route_request("Tính 24")

    assert route.tool is None
    assert route.direct is False


def test_gmail_summary_routes_to_a_fresh_bounded_read():
    route = route_request("Tổng hợp 5 email chưa đọc gần đây nhất thành ba nhóm")

    assert route.tool == "gmail_read_matching_messages"
    assert route.arguments == {"query": "is:unread", "max_results": 5}
    assert route.read_match is False


def test_five_recent_mail_reads_five_full_messages_without_unread_filter():
    route = route_request("tóm tắt 5 mail gần nhất trong gmail của tôi")

    assert route.tool == "gmail_read_matching_messages"
    assert route.arguments == {"query": "in:inbox", "max_results": 5}


def test_expanding_mail_scope_does_not_reapply_negated_sender_or_today():
    route = route_request(
        "Bây giờ đổi phạm vi: tóm tắt 5 email gần nhất trong Gmail của tôi, "
        "không giới hạn người gửi hay ngày hôm nay và không chỉ lấy ba thư Bản chi tiết trước đó. "
        "Nêu số thư thực đọc, tóm tắt từng thư với nguồn riêng. Không thay đổi Gmail."
    )
    assert route.tool == "gmail_read_matching_messages"
    assert route.arguments["max_results"] == 5
    assert "sender_name" not in route.arguments
    assert "day_scope" not in route.arguments
    assert 'from:' not in route.arguments["query"]
    assert 'subject:' not in route.arguments["query"]


def test_daily_sender_mail_summary_uses_today_and_sender_scope():
    route = route_request("tóm tắt các mail của Bảo Phúc Đinh trong ngày hôm nay")

    assert route.tool == "gmail_read_matching_messages"
    assert route.arguments == {
        "query": "after:0",
        "max_results": 20,
        "sender_name": "Bảo Phúc Đinh",
        "day_scope": "today",
    }


def test_latest_gmail_summary_reads_the_latest_inbox_thread_regardless_of_read_state():
    route = route_request("Đọc hiểu và tóm tắt nội dung Gmail gần nhất, tóm gọn bằng 3 ý")

    assert route.tool == "gmail_list_messages"
    assert route.arguments == {"query": "in:inbox", "max_results": 1}
    assert route.read_match is True


def test_latest_gmail_lookup_is_not_limited_to_the_last_month():
    route = route_request("Tìm email gần nhất")

    assert route.tool == "gmail_list_messages"
    assert route.arguments == {"query": "in:inbox", "max_results": 1}


def test_gmail_sender_subject_and_exact_date_search_are_preserved():
    route = route_request(
        "Tìm email của ProtonX về chủ đề Security Harness ngày 18/9/2026"
    )

    assert route.tool == "gmail_list_messages"
    assert route.arguments == {
        "query": 'from:"ProtonX" subject:"Security Harness" '
        "after:1789664400 before:1789750800",
        "max_results": 10,
    }
    assert route.read_match is False


def test_gmail_filtered_summary_reads_the_matching_thread():
    route = route_request(
        "Tìm và tóm tắt email của ProtonX về Security Harness ngày 18/9/2026"
    )

    assert route.tool == "gmail_read_matching_messages"
    assert route.arguments["query"] == (
        'from:"ProtonX" subject:"Security Harness" '
        "after:1789664400 before:1789750800"
    )
    assert route.read_match is False


def test_daily_sender_and_quoted_subject_mail_summary_keeps_both_filters():
    route = route_request(
        'Tóm tắt các mail "Bản chi tiết" của Đinh Bảo Phúc hôm nay'
    )

    assert route.tool == "gmail_read_matching_messages"
    assert route.arguments == {
        "query": 'subject:"Bản chi tiết"',
        "max_results": 20,
        "sender_name": "Đinh Bảo Phúc",
        "day_scope": "today",
    }


def test_sender_and_subject_label_are_preserved():
    route = route_request(
        'Tóm tắt email có tiêu đề "Bản chi tiết" người gửi là Đinh Bảo Phúc hôm nay'
    )

    assert route.tool == "gmail_read_matching_messages"
    assert route.arguments["query"] == 'subject:"Bản chi tiết"'
    assert route.arguments["sender_name"] == "Đinh Bảo Phúc"


def test_cross_source_compare_collects_gmail_and_named_drive_document():
    route = route_request(
        "Đối chiếu email gần nhất với file report.pdf trong Drive, nêu điểm giống và khác."
    )

    assert route.tool is None
    assert len(route.sources) == 2
    assert route.sources[0].tool == "gmail_list_messages"
    assert route.sources[0].read_match is True
    assert route.sources[1].tool == "drive_search_files"
    assert route.sources[1].arguments == {"query": "report.pdf", "page_size": 10}
    assert route.sources[1].read_match is True


def test_cross_source_compare_uses_latest_drive_file_only_when_explicit():
    route = route_request(
        "So sánh email gần nhất với tài liệu mới nhất trong Drive."
    )

    assert [source.tool for source in route.sources] == [
        "gmail_list_messages",
        "drive_list_files",
    ]


def test_cross_source_compare_asks_for_a_drive_file_instead_of_silently_using_email():
    route = route_request("Đối chiếu email gần nhất với tài liệu trong Drive.")

    assert route.direct is True
    assert route.sources == ()
    assert "chưa kết luận chỉ dựa trên email" in route.clarification


def test_generic_local_fixture_question_lists_sources_instead_of_searching_sentence():
    route = route_request(
        "Nếu hỏi nội dung fixture local, Agent có cần gọi drive_file_metadata không?"
    )
    assert route.tool == "local_source_search"
    assert route.arguments == {"query": ""}
    assert route.read_match is True
