from langchain_core.messages import AIMessage, ToolMessage

from app.agent.orchestrator import AgentOrchestrator


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
