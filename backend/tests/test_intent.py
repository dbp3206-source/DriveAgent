import pytest

from app.agent.controls import ChatControls
from app.agent.intent import explicit_source_exclusions, workspace_creation_requested
from app.agent.routing import Route, route_request


@pytest.mark.parametrize("message", [
    "Tìm trên web cách giảm thời gian tìm tài liệu cho nhóm vận hành.",
    "Tìm web và đề xuất cách làm rõ nhu cầu tìm tài liệu.",
    "Tra cứu nguồn công khai về quản lý tài liệu, đưa vài phương án phù hợp.",
])
def test_document_topic_still_gets_requested_public_evidence(message):
    assert not workspace_creation_requested(message)
    assert route_request(message).tool == "web_research"


@pytest.mark.parametrize("message", [
    "Đề xuất cho tôi cách tìm tài liệu nhanh hơn.",
    "Làm rõ nhu cầu quản lý tài liệu của nhóm.",
    "Đưa ra vài hướng cải thiện việc tìm tài liệu.",
    "Sửa cách phân loại tài liệu trong quy trình hiện tại.",
])
def test_advice_about_documents_is_not_an_output_write(message):
    assert not workspace_creation_requested(message)


@pytest.mark.parametrize("message", [
    "Tạo Google Doc từ bản nháp đã chọn.",
    "Soạn một tài liệu trình bày các phương án.",
    "Xuất thành bảng tính.",
    "Không đọc Gmail, nhưng tạo Google Doc bằng dữ liệu giả lập.",
])
def test_concrete_output_action_can_enter_governed_compiler(message):
    assert workspace_creation_requested(message)


def test_read_denials_apply_to_router_and_tool_allowlist():
    message = "Không mở Gmail, Drive, local, lịch hoặc web. Chỉ phân tích đầu vào này."
    expected = {"gmail", "drive", "local", "calendar", "web"}
    assert explicit_source_exclusions(message) == expected
    controls = ChatControls().enforce_explicit_source_exclusions(message)
    tools = ["gmail_read_thread", "drive_read_file", "local_source_search",
             "calendar_list_upcoming", "web_research", "calculate"]
    assert controls.allowed_tool_names(tools) == {"calculate"}
    for tool in tools[:-1]:
        assert controls.filter_excluded_route(Route(tool)) == Route()


def test_read_denial_stops_at_a_new_action_not_at_a_later_source_name():
    assert explicit_source_exclusions(
        "Không dùng Gmail, hãy đọc Drive. Nếu không có lịch thì báo rõ."
    ) == {"gmail"}
    assert explicit_source_exclusions("Không tạo lịch hoặc gửi thư.") == set()


def test_public_search_does_not_transmit_private_document_details():
    message = "Tìm web để đối chiếu tài liệu nội bộ với tin mới nhất."
    assert route_request(message).tool != "web_research"
    assert route_request("Tin mới nhất về quản lý tài liệu. Không tìm web.").tool is None
