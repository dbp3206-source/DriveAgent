from app.agent.routing import route_request


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
