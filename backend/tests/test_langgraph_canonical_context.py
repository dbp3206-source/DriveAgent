"""Real isolated SQL + LangGraph checkpoints, with an offline deterministic model."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agent import orchestrator as module
from app.agent.controls import ChatControls
from app.agent.orchestrator import AgentOrchestrator
from app.agent.state import AgentState
from app.core.config import Settings
from app.db.models import Base, ChatSession, Message, User
from app.tools.registry import ToolRegistry

HISTORY_LABEL = "Lịch sử hội thoại đã lưu"
NOW = datetime(2026, 10, 16, 9, tzinfo=UTC)


class OfflineModel:
    def __init__(self):
        self.prompts = []
        self.bound_tools = []

    def bind_tools(self, tools):
        self.bound_tools.append({tool.name for tool in tools})
        return self

    def with_fallbacks(self, _fallbacks):
        return self

    def with_structured_output(self, _schema):
        return self

    async def ainvoke(self, messages):
        if str(messages[0].content).startswith("Lập kế hoạch 1-5"):
            return SimpleNamespace(steps=["Phân tích yêu cầu"])
        self.prompts.append(messages)
        return AIMessage(content="Đã xem xét yêu cầu hiện tại.", tool_calls=[])


@pytest.fixture
async def context_runtime(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None, state_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'canonical.db'}",
        qdrant_path=str(tmp_path / "qdrant"), relational_state_url=None,
        storage_backend="local", supabase_url="", supabase_service_role_key=None,
        gemini_api_key="synthetic-not-a-real-key",
        gemini_chat_model="gemini-3.5-flash-lite",
        gemini_fallback_model="gemini-3.5-flash-lite",
    )
    assert settings.data_dir.resolve() == tmp_path.resolve()
    assert settings.resolved_qdrant_path.resolve() == (tmp_path / "qdrant").resolve()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'canonical.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    owner = User(id="owner-a", email="a@example.invalid", display_name="Synthetic A")
    other = User(id="owner-b", email="b@example.invalid", display_name="Synthetic B")
    async with factory() as db:
        db.add_all([owner, other])
        await db.flush()
        db.add_all([
            ChatSession(id="session-a", user_id=owner.id),
            ChatSession(id="session-other", user_id=owner.id),
        ])
        await db.commit()
    runtime = AgentOrchestrator(settings, ToolRegistry())
    model = OfflineModel()
    monkeypatch.setattr(module, "SessionFactory", factory)
    monkeypatch.setattr(
        "langchain_google_genai.ChatGoogleGenerativeAI", lambda **_kwargs: model,
    )
    monkeypatch.setattr(
        "app.agent.compiler.genai.Client",
        lambda **_kwargs: pytest.fail("This fixture must not construct a provider client"),
    )
    try:
        await runtime.initialize()
        async with runtime._checkpointer.conn.execute("PRAGMA database_list") as cursor:
            databases = await cursor.fetchall()
        assert Path(databases[0][2]).resolve() == (tmp_path / "langgraph_checkpoints.db").resolve()
        yield SimpleNamespace(
            factory=factory, owner=owner, runtime=runtime, model=model,
        )
    finally:
        await runtime.close()
        await engine.dispose()


async def add_messages(context, rows):
    """Rows are chronological, exactly as the canonical API stores them."""
    async with context.factory() as db:
        for index, row in enumerate(rows):
            role, content, *scope = row
            owner, session = scope or ("owner-a", "session-a")
            db.add(Message(
                user_id=owner, session_id=session, role=role, content=content,
                created_at=NOW + timedelta(seconds=index),
            ))
        await db.commit()


async def run(context, request="Tiếp tục phân tích.", *, request_id="request-a", controls=None):
    return await context.runtime.run(
        user=context.owner, session_id="session-a", request_id=request_id,
        user_message=request, controls=controls,
    )


def history(model):
    prompt = model.prompts[-1]
    rows = [message for message in prompt if str(message.content).startswith(HISTORY_LABEL)]
    return json.loads(str(rows[0].content).split("\n", 1)[1]) if rows else []


async def seed_legacy_checkpoint(context):
    builder = StateGraph(AgentState)
    builder.add_node("hold", lambda _state: {})
    builder.add_edge(START, "hold")
    builder.add_edge("hold", END)
    graph = builder.compile(checkpointer=context.runtime._checkpointer)
    await graph.ainvoke({"messages": [
        HumanMessage(content="Nguồn riêng cũ đã bị xóa khỏi SQL."),
        AIMessage(content="", tool_calls=[{
            "name": "gmail_read_thread", "args": {"thread_id": "private"}, "id": "old",
        }]),
        ToolMessage(content="STALE_PRIVATE_TOOL_SENTINEL", tool_call_id="old"),
        AIMessage(content="STALE_CHECKPOINT_ANSWER_SENTINEL"),
    ]}, config={"configurable": {"thread_id": "owner-a:session-a"}})


async def test_followup_uses_owner_session_sql_history_not_stale_checkpoint(context_runtime):
    context = context_runtime
    request = "Tiếp tục phân tích."
    await add_messages(context, [
        ("user", "Nhóm Mộc An có tám người; chỉ cần hỏi rõ nhu cầu."),
        ("assistant", "Cần hỏi nhu cầu tìm tài liệu."),
        ("user", "Đính chính: nhóm có chín người."),
        ("user", "OTHER_OWNER_SENTINEL", "owner-b", "session-a"),
        ("user", "OTHER_SESSION_SENTINEL", "owner-a", "session-other"),
        ("user", request),
    ])
    await seed_legacy_checkpoint(context)
    result = await run(context, request)

    assert history(context.model) == [
        {"role": "user", "text": "Nhóm Mộc An có tám người; chỉ cần hỏi rõ nhu cầu."},
        {"role": "assistant", "text": "Cần hỏi nhu cầu tìm tài liệu."},
        {"role": "user", "text": "Đính chính: nhóm có chín người."},
    ]
    prompt = context.model.prompts[-1]
    assert sum(message.content == request for message in prompt) == 1
    assert all(isinstance(message, (SystemMessage, HumanMessage)) for message in prompt)
    serialized = json.dumps([message.content for message in prompt], ensure_ascii=False)
    for sentinel in ("OTHER_OWNER_SENTINEL", "OTHER_SESSION_SENTINEL",
                     "STALE_PRIVATE_TOOL_SENTINEL", "STALE_CHECKPOINT_ANSWER_SENTINEL"):
        assert sentinel not in serialized
    assert any(row.get("restored_messages") == 3 for row in result.trace)
    assert result.citations == []


async def test_execution_is_unique_even_when_request_id_is_retried(context_runtime):
    context = context_runtime
    await add_messages(context, [("user", "Thông tin còn hiệu lực trong SQL.")])
    await run(context)
    await run(context)
    checkpointer = context.runtime._checkpointer
    async with checkpointer.conn.execute("SELECT DISTINCT thread_id FROM checkpoints") as cursor:
        threads = [row[0] for row in await cursor.fetchall()]
    assert len(threads) == 2
    assert all(thread.startswith("owner-a:session-a:request-a:") for thread in threads)
    assert all(len(thread.rsplit(":", 1)[-1]) == 32 for thread in threads)
    assert history(context.model) == [
        {"role": "user", "text": "Thông tin còn hiệu lực trong SQL."},
    ]


async def test_checkpoint_reset_keeps_canonical_followup_context(context_runtime):
    context = context_runtime
    await add_messages(context, [("user", "Ghi chú gần đây: ưu tiên phương án ít thao tác.")])
    await run(context)
    checkpointer = context.runtime._checkpointer
    async with checkpointer.conn.execute("SELECT DISTINCT thread_id FROM checkpoints") as cursor:
        threads = [row[0] for row in await cursor.fetchall()]
    assert all(thread.startswith("owner-a:session-a:request-a:") for thread in threads)
    for thread in threads:
        await checkpointer.adelete_thread(thread)
    await run(context, request_id="request-b")
    assert history(context.model) == [
        {"role": "user", "text": "Ghi chú gần đây: ưu tiên phương án ít thao tác."},
    ]


async def test_explicit_current_input_reset_drops_previous_customer_facts(context_runtime):
    context = context_runtime
    await add_messages(context, [
        ("user", "OLD_CUSTOMER_SENTINEL có hai mươi bốn người."),
        ("assistant", "OLD_ASSISTANT_FACT_SENTINEL"),
    ])
    request = "Chỉ dùng nội dung tin nhắn này: nhóm An Bình có tám người; hỏi rõ nhu cầu."
    await run(context, request)
    assert history(context.model) == []
    assert "OLD_CUSTOMER_SENTINEL" not in str(context.model.prompts[-1])
    assert "OLD_ASSISTANT_FACT_SENTINEL" not in str(context.model.prompts[-1])
    assert context.model.prompts[-1][-1].content == request


async def test_reset_boundary_survives_later_followup(context_runtime):
    context = context_runtime
    reset = "Chỉ dùng nội dung tin nhắn này: nhóm An Bình có tám người."
    await add_messages(context, [
        ("user", "OLD_CUSTOMER_SENTINEL"),
        ("assistant", "OLD_ASSISTANT_FACT_SENTINEL"),
        ("user", reset),
        ("assistant", "Cần hỏi rõ nhu cầu của nhóm An Bình."),
    ])
    await run(context)
    assert history(context.model) == [
        {"role": "user", "text": reset},
        {"role": "assistant", "text": "Cần hỏi rõ nhu cầu của nhóm An Bình."},
    ]


@pytest.mark.parametrize("controls,user_message,expected", [
    (ChatControls(source="general"), "Tiếp tục phân tích.", set()),
    (ChatControls(source="local"), "Tiếp tục phân tích.", {"local_source_search"}),
    (ChatControls(), "Tiếp tục phân tích. Không đọc Gmail.", {
        "drive_list_files", "rag_search", "local_source_search", "memory_search",
        "calendar_list_upcoming", "web_research", "calculate",
    }),
    (ChatControls(excluded_sources=frozenset({
        "gmail", "drive", "local", "memory", "calendar", "web",
    })), "Tiếp tục phân tích.", {"calculate"}),
])
async def test_source_controls_still_bound_real_graph_tools(
    context_runtime, monkeypatch, controls, user_message, expected,
):
    context = context_runtime
    await add_messages(context, [("user", "USER_PROVIDED_FACT_SENTINEL: nhóm có tám người.")])

    async def unused_tool() -> str:
        pytest.fail("No provider or source may be accessed by this offline model")

    tools = [StructuredTool.from_function(
        coroutine=unused_tool, name=name, description="Synthetic offline tool",
    ) for name in (
        "gmail_read_thread", "drive_list_files", "rag_search", "local_source_search",
        "memory_search", "calendar_list_upcoming", "web_research", "calculate",
    )]
    monkeypatch.setattr(context.runtime, "_build_tools", lambda *_args: tools)
    await run(context, user_message, controls=controls)
    assert context.model.bound_tools == [expected, expected]
    assert history(context.model) == [{
        "role": "user", "text": "USER_PROVIDED_FACT_SENTINEL: nhóm có tám người.",
    }]
    if controls.excluded_sources or "Gmail" in user_message:
        assert "Nguồn bị cấm" in context.model.prompts[-1][0].content


async def test_bridge_is_bounded_and_preserves_newest_correction(context_runtime):
    context = context_runtime
    rows = [("user", f"Turn {index}: " + "x" * 17000) for index in range(40)]
    correction = "Đính chính mới nhất: không tự suy đoán ngân sách."
    rows[-1] = ("user", correction)
    await add_messages(context, rows)
    await run(context)
    restored = history(context.model)
    assert restored[-1] == {"role": "user", "text": correction}
    assert restored[0]["role"] == "system"
    assert "hỏi lại" in restored[0]["text"]
    assert sum(len(row["text"]) for row in restored[1:]) <= 64000
    assert all(len(row["text"]) <= 16000 for row in restored)
    assert "Turn 0:" not in json.dumps(restored)
