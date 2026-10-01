from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.orchestrator import AgentOrchestrator, _drive_citation_excerpt, _pdf_page_citations
from app.core.config import Settings
from app.tools.registry import ToolRegistry


def test_refresh_in_a_new_turn_is_not_a_loop() -> None:
    call = {"name": "drive_list_files", "args": {}, "id": "old"}
    messages = [
        HumanMessage(content="list"),
        AIMessage(content="", tool_calls=[call]),
        ToolMessage(content='{"files": []}', tool_call_id="old"),
        AIMessage(content="done"),
        HumanMessage(content="refresh"),
        AIMessage(content="", tool_calls=[{**call, "id": "new"}]),
    ]
    assert not AgentOrchestrator._should_synthesize({"messages": messages, "tool_rounds": 1})


def test_sheet_citation_excerpt_includes_real_row_after_dossier_preamble() -> None:
    row = "| " + " | ".join(str(value) for value in range(1, 15)) + " |"
    text = "# Hồ sơ\n" + "Giới thiệu dài " * 50 + "\n## 📑 Cấu trúc\n" + row
    payload = {
        "file": {
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        },
        "text": text,
    }

    assert row in _drive_citation_excerpt(payload)
    assert _drive_citation_excerpt({"file": {"mime_type": "application/pdf"}, "text": text}) == (
        text[:500]
    )


def test_pdf_citations_bind_recovered_text_to_original_page() -> None:
    payload = {
        "file": {"id": "pdf-1", "name": "Evaluation-Harness.pdf", "mime_type": "application/pdf"},
        "text": (
            "<!-- page:1 -->\nGiới thiệu\n"
            "<!-- page:2 -->\nTóm tắt đ y đủ\n"
            "<!-- page:2 -->\nTóm tắt đầy đủ\n"
        ),
    }
    citations = _pdf_page_citations(payload)

    assert len(citations) == 2
    assert citations[1]["page_number"] == 2
    assert citations[1]["chunk_index"] == 1
    assert "Tóm tắt đầy đủ" in citations[1]["snippet"]


def test_new_answer_does_not_inherit_old_citations() -> None:
    evidence = ToolMessage(
        content='{"citations":[{"file_id":"f1","chunk_index":0}]}',
        tool_call_id="old",
        name="rag_search",
    )
    messages = [HumanMessage(content="search"), evidence, AIMessage(content="answer")]
    assert len(AgentOrchestrator._collect_citations(messages)) == 1
    messages.extend([HumanMessage(content="Only say OK"), AIMessage(content="OK")])
    assert AgentOrchestrator._collect_citations(messages) == []


def test_current_turn_keeps_evidence_and_empty_guard_is_safe() -> None:
    assert AgentOrchestrator._current_turn([]) == []
    assert not AgentOrchestrator._should_synthesize({"messages": []})
    question = HumanMessage(content="read")
    evidence = ToolMessage(content="text", tool_call_id="current")
    assert AgentOrchestrator._current_turn([AIMessage(content="old"), question, evidence]) == [
        question,
        evidence,
    ]


def test_gmail_messages_become_stable_clickable_source_references() -> None:
    evidence = ToolMessage(
        content=(
            '{"messages":[{"id":"m1","thread_id":"t1","subject":"Lịch học",'
            '"snippet":"Học thứ Sáu"}]}'
        ),
        tool_call_id="mail-call",
        name="gmail_list_messages",
    )
    citations = AgentOrchestrator._collect_citations([HumanMessage(content="mail"), evidence])
    assert citations == [
        {
            "file_id": "m1",
            "file_name": "Lịch học",
            "chunk_index": 0,
            "snippet": "Học thứ Sáu",
            "web_view_link": "https://mail.google.com/mail/u/0/#all/t1",
            "score": 1.0,
        }
    ]


def test_multi_email_full_body_creates_one_citation_per_read_message() -> None:
    evidence = ToolMessage(
        content=(
            '{"messages":['
            '{"id":"m1","thread_id":"t1","subject":"Bản 8h","body":"Toàn văn sáng"},'
            '{"id":"m2","thread_id":"t2","subject":"Bản 12h","body":"Toàn văn trưa"}'
            ']}'
        ),
        tool_call_id="multi-mail-call",
        name="gmail_read_matching_messages",
    )
    citations = AgentOrchestrator._collect_citations([HumanMessage(content="mail"), evidence])
    assert [citation["file_id"] for citation in citations] == ["m1", "m2"]
    assert [citation["snippet"] for citation in citations] == ["Toàn văn sáng", "Toàn văn trưa"]
    assert citations[1]["web_view_link"] == "https://mail.google.com/mail/u/0/#all/t2"


def test_local_search_sources_become_clickable_citations() -> None:
    evidence = ToolMessage(
        content=(
            '{"data":{"sources":[{"id":"source-1","name":"study.md",'
            '"snippet":"LOCAL-STUDY-2026",'
            '"web_view_link":"http://localhost:8000/api/local-sources/source-1/text"}]}}'
        ),
        tool_call_id="local-call",
        name="local_source_search",
    )
    citations = AgentOrchestrator._collect_citations([HumanMessage(content="local"), evidence])
    assert citations == [
        {
            "file_id": "local:source-1",
            "file_name": "study.md",
            "chunk_index": 0,
            "snippet": "LOCAL-STUDY-2026",
            "web_view_link": "http://localhost:8000/api/local-sources/source-1/text",
            "score": 1.0,
        }
    ]


def test_loop_guard_stops_an_identical_executed_tool_call() -> None:
    first = AIMessage(
        content="",
        tool_calls=[{"name": "rag_search", "args": {"query": "state"}, "id": "call-1"}],
    )
    result = ToolMessage(
        content='{"citations": [{"file_id": "f1"}]}',
        tool_call_id="call-1",
        name="rag_search",
    )
    repeated = AIMessage(
        content="",
        tool_calls=[{"name": "rag_search", "args": {"query": "state"}, "id": "call-2"}],
    )

    assert AgentOrchestrator._should_synthesize(
        {"messages": [first, result, repeated], "tool_rounds": 2}
    )


def test_loop_guard_allows_a_normal_tool_sequence() -> None:
    search = AIMessage(
        content="",
        tool_calls=[{"name": "drive_search_files", "args": {"query": "x"}, "id": "call-1"}],
    )
    result = ToolMessage(content='{"files": []}', tool_call_id="call-1", name="drive_search_files")
    read = AIMessage(
        content="",
        tool_calls=[{"name": "drive_read_file", "args": {"file_id": "f1"}, "id": "call-2"}],
    )

    assert not AgentOrchestrator._should_synthesize(
        {"messages": [search, result, read], "tool_rounds": 2}
    )


async def test_langgraph_rejects_unapproved_user_or_configured_model_before_provider_call():
    settings = Settings(
        _env_file=None,
        gemini_api_key="test-key",
        gemini_chat_model="gemini-3.5-flash-lite",
        gemini_fallback_model="gemini-3.5-flash-lite",
    )
    orchestrator = AgentOrchestrator(settings, ToolRegistry())
    orchestrator._checkpointer = object()
    user = type("User", (), {"id": "u", "role": "editor"})()
    with pytest.raises(ValueError, match="danh sách đã duyệt"):
        await orchestrator.run(
            user=user,
            session_id="s",
            request_id="r",
            user_message="Hãy phân tích tài liệu này",
            model_name="gemini-unreviewed-experimental",
        )

    invalid_settings = Settings(
        _env_file=None,
        gemini_api_key="test-key",
        gemini_chat_model="gemini-unreviewed-experimental",
        gemini_fallback_model="gemini-3.5-flash-lite",
    )
    invalid = AgentOrchestrator(invalid_settings, ToolRegistry())
    invalid._checkpointer = object()
    with pytest.raises(ValueError, match="Model cấu hình"):
        await invalid.run(
            user=user,
            session_id="s",
            request_id="r",
            user_message="Hãy phân tích tài liệu này",
        )


async def test_langgraph_run_builds_plan_and_final_response_through_real_nodes():
    class FakeModel:
        def bind_tools(self, _tools):
            return self

        def with_fallbacks(self, _fallbacks):
            return self

        def with_structured_output(self, _model):
            return self

        async def ainvoke(self, messages):
            if any(str(message.content).startswith("Lập kế hoạch 1-5") for message in messages):
                return type("Plan", (), {"steps": ["Tìm bằng chứng", "Tổng hợp"]})()
            return AIMessage(content="Câu trả lời đã kiểm chứng.", tool_calls=[])

    class FakeGraph:
        def __init__(self, nodes):
            self.nodes = nodes

        async def ainvoke(self, state, config):
            assert config["configurable"]["thread_id"] == "u:s"
            planned = await self.nodes["planner"](state)
            state = {**state, **planned}
            agent = await self.nodes["agent"](state)
            return {
                **state,
                **agent,
                "messages": [*state["messages"], *agent["messages"]],
                "trace": [*planned["trace"], *agent["trace"]],
            }

    class FakeStateGraph:
        def __init__(self, _state_type):
            self.nodes = {}

        def add_node(self, name, node):
            self.nodes[name] = node

        def add_edge(self, *_args):
            pass

        def add_conditional_edges(self, *_args):
            pass

        def compile(self, **_kwargs):
            return FakeGraph(self.nodes)

    settings = Settings(
        _env_file=None,
        gemini_api_key="test-key",
        gemini_chat_model="gemini-3.5-flash-lite",
        gemini_fallback_model="gemini-3.5-flash-lite",
    )
    orchestrator = AgentOrchestrator(settings, ToolRegistry())
    orchestrator._checkpointer = object()
    model = FakeModel()
    user = type("User", (), {"id": "u", "role": "editor"})()
    with (
        patch("app.agent.orchestrator.ChatGoogleGenerativeAI", return_value=model),
        patch("app.agent.orchestrator.StateGraph", FakeStateGraph),
        patch("app.agent.orchestrator.ToolNode", lambda *_args, **_kwargs: object()),
    ):
        result = await orchestrator.run(
            user=user,
            session_id="s",
            request_id="r",
            user_message="Hãy giải thích kế hoạch học tập",
        )

    assert result.answer == "Câu trả lời đã kiểm chứng."
    assert result.plan == ["Tìm bằng chứng", "Tổng hợp"]
    assert result.trace[0]["stage"] == "planning"
