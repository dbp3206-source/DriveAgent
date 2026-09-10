from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.orchestrator import AgentOrchestrator


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
