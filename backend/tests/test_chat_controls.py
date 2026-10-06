import pytest
from pydantic import ValidationError

from app.agent.compiler import CompilerOrchestrator
from app.agent.controls import ChatControls
from app.agent.routing import Route, route_request
from app.api.schemas import ChatRequest
from app.services.local_sources import LocalSearchInput

TOOLS = [
    "drive_list_files",
    "drive_search_files",
    "drive_read_file",
    "rag_search",
    "gmail_list_messages",
    "memory_search",
    "local_source_search",
    "calculate",
    "skill_run",
]


def test_context_only_followup_cannot_read_memory_named_in_save_prohibition():
    request = (
        "Chỉ dùng ngữ cảnh đã có, không đọc thêm nguồn. "
        "Gọi công cụ calculate để tính giờ còn lại. Không lưu bộ nhớ."
    )
    controls = ChatControls().enforce_explicit_source_exclusions(request)
    assert controls.excluded_sources == frozenset({"drive", "gmail", "local", "memory"})
    assert controls.allowed_tool_names(TOOLS) == {"calculate", "skill_run"}
    assert controls.filter_excluded_route(route_request(request)).tool is None


def test_not_saving_memory_does_not_prohibit_explicit_memory_read():
    controls = ChatControls().enforce_explicit_source_exclusions(
        "Tìm sở thích trong bộ nhớ của tôi, không lưu bộ nhớ mới."
    )
    assert "memory_search" in controls.allowed_tool_names(TOOLS)


def test_local_command_keeps_both_explicit_files_after_negative_drive_scope():
    message = (
        "/local Đọc cả hai tài liệu giả lập 01-yeu-cau-khach-hang.md và "
        "02-dieu-chinh-pham-vi.md đã tải lên. "
        + "Chuẩn bị báo cáo và tính bằng công cụ. " * 12
        + "Không đọc Gmail, Drive, lịch, web hoặc bộ nhớ dài hạn."
    )
    controls, clean = ChatControls().parse_leading_commands(message)
    actual = CompilerOrchestrator._apply_controls(route_request(clean), clean, controls)
    assert actual.required_sources == ("local",)
    assert [item.arguments["query"] for item in actual.sources] == [
        "01-yeu-cau-khach-hang.md", "02-dieu-chinh-pham-vi.md"
    ]
    for item in actual.sources:
        assert item.tool == "local_source_search"
        assert item.read_match
        LocalSearchInput.model_validate(item.arguments)


def test_local_generic_long_request_obeys_search_schema():
    message = "Đọc tài liệu và phân tích yêu cầu. " * 30
    actual = CompilerOrchestrator._apply_controls(Route(), message, ChatControls(source="local"))
    assert actual.tool == "local_source_search"
    assert len(actual.arguments["query"]) == 200
    LocalSearchInput.model_validate(actual.arguments)


def test_chat_request_defaults_to_automatic_controls():
    request = ChatRequest(message="Xin chào")
    assert request.controls == ChatControls()


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("drive", {"drive_list_files", "drive_search_files", "drive_read_file"}),
        ("rag", {"rag_search"}),
        ("gmail", {"gmail_list_messages"}),
        ("local", {"local_source_search"}),
        ("memory", {"memory_search", "calculate"}),
        ("general", set()),
    ],
)
def test_source_choice_is_a_real_tool_allow_list(source, expected):
    controls = ChatControls(source=source)
    assert controls.allowed_tool_names(TOOLS) == expected


def test_rag_control_overrides_drive_heuristic_route():
    controls = ChatControls(source="rag")
    route = CompilerOrchestrator._apply_controls(
        Route("drive_search_files", {"query": "report.pdf"}),
        "Trong tệp Drive Evaluation-Harness.pdf (ID: 11mZ5EtxvMxVXoZveAiBexNhtHLvKKTjg): Tóm tắt",
        controls,
    )
    assert route.tool == "rag_search"
    assert route.arguments == {
        "query": (
            "Trong tệp Drive Evaluation-Harness.pdf "
            "(ID: 11mZ5EtxvMxVXoZveAiBexNhtHLvKKTjg): Tóm tắt"
        ),
        "limit": 12,
        "file_ids": ["11mZ5EtxvMxVXoZveAiBexNhtHLvKKTjg"],
    }


def test_conflicting_source_and_agent_is_rejected():
    with pytest.raises(ValidationError):
        ChatControls(source="gmail", agent="research")


def test_explicit_rag_only_message_becomes_tool_boundary():
    controls = ChatControls().enforce_explicit_message_source(
        "Chỉ dùng RAG đã lập chỉ mục: mục tiêu hiện tại là gì?"
    )

    assert controls.source == "rag"
    assert controls.effective_agent() == "research"
    assert controls.allowed_tool_names(TOOLS) == {"rag_search"}


def test_explicit_message_does_not_override_slash_source():
    controls = ChatControls(source="drive").enforce_explicit_message_source(
        "Chỉ dùng RAG đã lập chỉ mục"
    )

    assert controls.source == "drive"


def test_saved_skill_explicit_local_sources_use_local_boundary():
    controls = ChatControls(skill_name="qa_final_tu_van").enforce_explicit_message_source(
        "Chỉ dùng hai tài liệu local giả lập 01-yeu-cau.md và 02-dieu-chinh.md."
    )
    assert controls.source == "local"
    assert controls.allowed_tool_names(TOOLS, skill_capabilities=frozenset()) == {
        "local_source_search", "skill_run",
    }


@pytest.mark.parametrize("message", [
    "Không chỉ dùng hai tài liệu local, hãy hỏi lại phạm vi.",
    "Tài liệu local có sẵn nhưng chỉ dùng đầu vào trong câu này.",
    "Không đọc tài liệu local; chỉ dùng đầu vào mới này.",
])
def test_mentioning_local_does_not_enable_saved_skill_sources(message):
    controls = ChatControls(skill_name="qa_final_tu_van").enforce_explicit_message_source(message)
    assert controls.source == "auto"
    assert controls.allowed_tool_names(TOOLS, skill_capabilities=frozenset()) == {"skill_run"}


def test_explicit_negative_sources_remove_tools_and_routes():
    message = (
        "Kiểm thử bằng dữ liệu giả; không truy cập Gmail/Drive và không ghi dữ liệu. "
        "Cửa hàng X có 1.000 đơn tuần trước và 1.200 tuần này."
    )
    controls = ChatControls().enforce_explicit_source_exclusions(message)

    assert controls.excluded_sources == {"gmail", "drive"}
    assert controls.allowed_tool_names(TOOLS) == {
        "memory_search",
        "local_source_search",
        "calculate",
        "skill_run",
    }
    assert controls.filter_excluded_route(
        Route("gmail_list_messages", {"query": "in:inbox"})
    ) == Route()
    assert controls.filter_excluded_route(
        Route("rag_search", {"query": "latest"})
    ) == Route()


def test_negative_source_policy_overrides_slash_source_and_route_override():
    message = "Không đọc Gmail; hãy phân tích các số liệu tôi dán bên dưới."
    controls = ChatControls(source="gmail").enforce_explicit_source_exclusions(message)

    assert controls.excluded_sources == {"gmail"}
    assert controls.allowed_tool_names(TOOLS) == set()
    assert controls.filter_excluded_route(Route("gmail_list_messages")) == Route()
    assert CompilerOrchestrator._apply_controls(
        Route("gmail_list_messages", {"query": "in:inbox"}), message, controls
    ) == Route()


def test_source_exclusion_does_not_trigger_for_neutral_source_mentions():
    controls = ChatControls().enforce_explicit_source_exclusions(
        "Gmail và Drive đang gặp lỗi; hãy phân tích bộ số liệu giả này."
    )

    assert controls.excluded_sources == frozenset()
    assert controls.allowed_tool_names(TOOLS) == set(TOOLS)


def test_source_exclusion_stops_at_a_contrast_or_positive_source_action():
    controls = ChatControls().enforce_explicit_source_exclusions(
        "Không dùng Gmail, nhưng dùng Drive để tìm một tệp."
    )

    assert controls.excluded_sources == {"gmail"}
    assert controls.allowed_tool_names(TOOLS) == {
        "drive_list_files",
        "drive_search_files",
        "drive_read_file",
        "rag_search",
        "memory_search",
        "local_source_search",
        "calculate",
        "skill_run",
    }


def test_source_prohibition_does_not_include_sources_named_before_it():
    controls = ChatControls().enforce_explicit_source_exclusions(
        "Chỉ đọc hai tài liệu local và trả lời, không Gmail, Drive, lịch, web."
    )
    assert controls.excluded_sources == {"gmail", "drive"}
    assert "local_source_search" in controls.allowed_tool_names(TOOLS)


def test_short_source_prohibition_preserves_positive_request_after_contrast():
    controls = ChatControls().enforce_explicit_source_exclusions(
        "Không Gmail, nhưng đọc tài liệu local."
    )
    assert controls.excluded_sources == {"gmail"}


def test_typed_slash_commands_set_controls_and_strip_only_leading_prefix():
    controls, message = ChatControls().parse_leading_commands(
        "/drive /research Liệt kê 3 tệp gần đây; giữ 1/2 trong nội dung."
    )

    assert message == "Liệt kê 3 tệp gần đây; giữ 1/2 trong nội dung."
    assert controls.source == "drive"
    assert controls.effective_agent() == "research"
    assert controls.allowed_tool_names(TOOLS) == {
        "drive_list_files",
        "drive_search_files",
        "drive_read_file",
    }


def test_typed_output_command_preserves_selected_read_source():
    controls, message = ChatControls().parse_leading_commands(
        "/rag /doc Tạo báo cáo từ nguồn đã lập chỉ mục"
    )

    assert message == "Tạo báo cáo từ nguồn đã lập chỉ mục"
    assert controls.source == "rag"
    assert controls.agent == "workspace"
    assert controls.output == "document"
    assert controls.allowed_tool_names(TOOLS) == {"rag_search"}


def test_unknown_or_mid_sentence_slash_text_is_not_consumed():
    unknown, unknown_message = ChatControls().parse_leading_commands("/unknown giữ nguyên")
    mid, mid_message = ChatControls().parse_leading_commands("Giữ tỷ lệ 1/2 và /drive")

    assert unknown == ChatControls()
    assert unknown_message == "/unknown giữ nguyên"
    assert mid == ChatControls()
    assert mid_message == "Giữ tỷ lệ 1/2 và /drive"


def test_workspace_output_can_compile_content_from_a_specialist_source():
    controls = ChatControls(source="rag", output="document", agent="research")
    assert controls.output == "document"
    assert controls.effective_agent() == "research"


def test_workspace_writer_can_preserve_selected_source_tools():
    controls = ChatControls(source="gmail", output="document", agent="workspace")
    assert controls.allowed_tool_names(TOOLS) == {"gmail_list_messages"}


def test_saved_gmail_skill_gets_only_its_declared_read_capability():
    available = TOOLS + ["gmail_read_thread", "docs_create"]
    controls = ChatControls(skill_name="daily_news_brief")

    assert controls.allowed_tool_names(available, {"gmail"}) == {
        "skill_run",
        "gmail_list_messages",
        "gmail_read_thread",
    }


def test_multiple_saved_skills_compose_in_order_and_union_capabilities():
    controls, message = ChatControls().parse_leading_commands(
        "/skill:daily_news_brief /skill:research_knowledge_brief tổng hợp và viết báo cáo"
    )

    assert controls.selected_skill_names() == (
        "daily_news_brief",
        "research_knowledge_brief",
    )
    assert message == "tổng hợp và viết báo cáo"
    assert "daily_news_brief → research_knowledge_brief" in controls.instruction()
    assert controls.allowed_tool_names(
        TOOLS + ["gmail_read_thread", "rag_search", "docs_create"],
        {"gmail", "rag", "docs"},
    ) == {
        "skill_run",
        "gmail_list_messages",
        "gmail_read_thread",
        "rag_search",
        "docs_create",
    }


def test_saved_skill_cannot_override_explicit_source_or_source_exclusion():
    available = TOOLS + ["gmail_read_thread", "drive_read_file"]
    gmail_skill = ChatControls(skill_name="daily_news_brief", source="gmail")
    blocked_skill = ChatControls(skill_name="daily_news_brief").model_copy(
        update={"excluded_sources": frozenset({"gmail"})}
    )

    assert gmail_skill.allowed_tool_names(available, {"gmail", "drive"}) == {
        "skill_run",
        "gmail_list_messages",
        "gmail_read_thread",
    }
    assert blocked_skill.allowed_tool_names(available, {"gmail"}) == {"skill_run"}


@pytest.mark.parametrize(
    ("selected_agent", "tool", "expected_agent"),
    [
        ("study", "drive_list_files", "research"),
        ("study", "gmail_list_messages", "communication"),
        ("communication", "drive_search_files", "research"),
    ],
)
def test_auto_source_route_aligns_incompatible_agent_instead_of_dropping_source(
    selected_agent, tool, expected_agent
):
    controls = ChatControls(agent=selected_agent)
    aligned, event = controls.align_with_route(Route(tool=tool))

    assert aligned.agent == expected_agent
    assert aligned.source == "auto"
    assert tool in aligned.allowed_tool_names(TOOLS)
    assert event == {
        "from_agent": selected_agent,
        "to_agent": expected_agent,
        "source": "gmail" if tool.startswith("gmail_") else "drive",
        "reason": "explicit_source_route",
    }


def test_workspace_route_keeps_role_but_adds_matching_read_source():
    controls = ChatControls(agent="workspace", output="document")
    aligned, event = controls.align_with_route(Route(tool="gmail_list_messages"))

    assert aligned.agent == "workspace"
    assert aligned.source == "gmail"
    assert "gmail_list_messages" in aligned.allowed_tool_names(TOOLS)
    assert event["from_agent"] == event["to_agent"] == "workspace"


def test_explicit_general_source_is_not_overridden_by_route_alignment():
    controls = ChatControls(source="general", agent="study")
    aligned, event = controls.align_with_route(Route(tool="gmail_list_messages"))

    assert aligned == controls
    assert event is None


def test_email_digest_compiler_uses_valid_gmail_query_not_natural_language():
    controls = ChatControls(source="gmail", workflow="email_digest", output="document")
    route = CompilerOrchestrator._apply_controls(Route(), "Tổng hợp hộp thư hôm nay", controls)
    assert route.tool == "gmail_list_messages"
    assert route.arguments == {"query": "is:unread newer_than:7d", "max_results": 20}


def test_explicit_gmail_source_preserves_a_specific_deterministic_search():
    controls = ChatControls(source="gmail")
    specific = Route(
        "gmail_list_messages",
        {"query": 'from:"ProtonX" subject:"Security Harness"', "max_results": 10},
        read_match=True,
    )

    assert CompilerOrchestrator._apply_controls(specific, "Tóm tắt email", controls) == specific


def test_unknown_control_field_is_rejected():
    with pytest.raises(ValidationError):
        ChatControls.model_validate({"source": "auto", "hidden_override": True})
