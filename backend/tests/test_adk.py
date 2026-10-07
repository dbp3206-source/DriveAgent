import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from google import genai
from google.adk.sessions import DatabaseSessionService
from google.genai import types
from langchain_core.messages import ToolMessage

from app.agent.adk_orchestrator import (
    AdkOrchestrator,
    GovernedAdkTool,
    RecoverableGemini,
    scoped_execution_session,
)
from app.agent.compiler import deterministic_static_answer
from app.agent.controls import ChatControls
from app.agent.orchestrator import AgentNotConfiguredError
from app.agent.routing import route_request
from app.core.config import Settings
from app.tools.calculator import calculator_tool_definitions
from app.tools.registry import ToolRegistry


def test_execution_history_scope_changes_without_changing_canonical_conversation():
    broad = scoped_execution_session("conversation-a", "skill", {
        "skill_run", "local_source_search", "local_source_read", "calculate",
    })
    narrow = scoped_execution_session("conversation-a", "skill", {"skill_run"})
    assert broad != narrow
    assert narrow == scoped_execution_session("conversation-a", "skill", {"skill_run"})
    assert narrow != scoped_execution_session("conversation-b", "skill", {"skill_run"})
    assert narrow != scoped_execution_session("conversation-a", "research", {"skill_run"})
    assert broad.startswith("conversation-a--")
    assert scoped_execution_session("conversation-a", "skill", {"skill_run"}, "turn-1") != (
        scoped_execution_session("conversation-a", "skill", {"skill_run"}, "turn-2")
    )
    assert scoped_execution_session("conversation-a", "skill", {"skill_run"}, "turn-1") == (
        scoped_execution_session("conversation-a", "skill", {"skill_run"}, "turn-1")
    )
    assert broad == scoped_execution_session("conversation-a", "skill", {
        "calculate", "local_source_read", "skill_run", "local_source_search",
    })


def test_official_web_question_routes_to_specialist_with_actual_web_tool():
    import asyncio

    from app.tools.web_research import web_research_tool_definitions

    question = (
        "Thông tin hiện tại: hãy đọc nguồn chính thức "
        "https://ai.google.dev/gemini-api/docs/rate-limits và cho biết hạn mức Gemini "
        "tính theo API key hay project, hạn mức ngày đặt lại theo múi giờ nào, ngày "
        "cập nhật trang là ngày nào. Chỉ dùng web, không đọc Gmail, Drive, tài liệu "
        "local hoặc bộ nhớ; dẫn nguồn cho từng ý. Nếu không đọc được thì nói "
        "chưa xác minh, không đoán."
    )
    controls = ChatControls().enforce_explicit_source_exclusions(question)
    assert controls.excluded_sources == frozenset({'gmail', 'drive', 'local', 'memory'})
    selected = AdkOrchestrator._auto_agent_for_request(
        question, excluded_sources=controls.excluded_sources,
    )
    assert selected == 'research'
    registry = ToolRegistry()
    for definition in [*web_research_tool_definitions(), *calculator_tool_definitions()]:
        registry.register(definition)
    names = controls.allowed_tool_names([item.name for item in registry.definitions()])
    tools = [GovernedAdkTool(
        definition, registry, Settings(_env_file=None), 'owner', 'request', [], [],
        asyncio.Semaphore(2), set(), {},
    ) for definition in registry.definitions() if definition.name in names]
    agent = AdkOrchestrator._build_agent_tree(
        RecoverableGemini(model='gemini-primary', fallback_model='gemini-fallback'),
        tools, [], selected_agent=selected,
    )
    assert agent.name == 'web_research_agent'
    assert [tool.name for tool in agent.tools] == ['web_research']


def test_every_specialist_inherits_customer_fact_provenance_policy():
    agent = AdkOrchestrator._build_agent_tree(
        RecoverableGemini(model='gemini-primary', fallback_model='gemini-fallback'),
        [], [],
    )
    for specialist in [agent, *agent.sub_agents]:
        assert 'Nhu cầu hay mục tiêu không chứng minh hiện trạng hoặc nguyên nhân' in (
            specialist.instruction
        )
        assert 'Câu trả lời trước của trợ lý không phải nguồn xác nhận độc lập' in (
            specialist.instruction
        )


@pytest.mark.parametrize('fallback', [False, True])
async def test_invented_tool_is_blocked_before_adk_dispatch(monkeypatch, fallback):
    from google.adk.models import Gemini
    from google.adk.models.llm_request import LlmRequest
    from google.adk.models.llm_response import LlmResponse
    from google.genai.errors import ServerError

    from app.tools.contracts import ToolError

    async def generate(self, request, stream=False):
        if fallback and self.model == 'gemini-primary':
            raise ServerError(503, {'error': {'message': 'down'}})
        yield LlmResponse(content=types.Content(parts=[types.Part(
            function_call=types.FunctionCall(name='web_research', args={'question': 'x'}),
        )]))

    monkeypatch.setattr(Gemini, 'generate_content_async', generate)
    model = RecoverableGemini(model='gemini-primary', fallback_model='gemini-fallback')
    request = LlmRequest(model='gemini-primary')
    request.tools_dict['calculate'] = object()
    with pytest.raises(ToolError) as caught:
        _ = [reply async for reply in model.generate_content_async(request)]
    assert caught.value.code == 'unavailable_tool'
    assert model.records[-1]['rule'] == 'unavailable_tool'
    assert model.records[-1]['tool'] == 'unknown'


@pytest.mark.parametrize('tool_name', ['web_research', 'transfer_to_agent'])
async def test_registered_tools_and_agent_transfer_are_not_blocked(monkeypatch, tool_name):
    from google.adk.models import Gemini
    from google.adk.models.llm_request import LlmRequest
    from google.adk.models.llm_response import LlmResponse

    response = LlmResponse(content=types.Content(parts=[types.Part(
        function_call=types.FunctionCall(name=tool_name, args={}),
    )]))

    async def generate(self, request, stream=False):
        yield response

    monkeypatch.setattr(Gemini, 'generate_content_async', generate)
    model = RecoverableGemini(model='gemini-primary', fallback_model='gemini-fallback')
    request = LlmRequest(model='gemini-primary')
    request.tools_dict[tool_name] = object()
    replies = [reply async for reply in model.generate_content_async(request)]
    assert replies == [response]
    assert model.records[-1]['status'] == 'success'


async def test_fallback_does_not_deepcopy_tool_locks(monkeypatch):
    import threading

    from google.adk.models import Gemini
    from google.adk.models.llm_request import LlmRequest
    from google.adk.models.llm_response import LlmResponse
    from google.genai.errors import ClientError

    from app.agent.adk_orchestrator import RecoverableGemini

    requests = []

    async def generate(self, request, stream=False):
        requests.append(request.model)
        if self.model == "gemini-primary":
            raise ClientError(429, {"error": {"message": "quota"}})
        yield LlmResponse(content=types.Content(parts=[types.Part(text="OK")]))

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    request = LlmRequest(model="gemini-primary")
    # ADK keeps runtime objects in an excluded dictionary; deepcopy cannot copy locks.
    request.tools_dict["runtime_lock"] = threading.Lock()
    model = RecoverableGemini(model="gemini-primary", fallback_model="gemini-fallback")
    replies = [response async for response in model.generate_content_async(request)]
    assert replies[0].content.parts[0].text == "OK"
    assert request.model == "gemini-primary"
    assert requests == ["gemini-primary", "gemini-fallback"]
    assert model.records[-1] == {
        "stage": "model",
        "status": "fallback",
        "model": "gemini-fallback",
        "requested_model": "gemini-primary",
        "actual_model": "gemini-fallback",
        "fallback_model": "gemini-fallback",
        "fallback_reason": "provider_429",
        "provider_code": 429,
    }


async def test_recoverable_gemini_records_all_intermediate_fallback_failures(monkeypatch):
    from google.adk.models import Gemini
    from google.adk.models.llm_request import LlmRequest
    from google.adk.models.llm_response import LlmResponse
    from google.genai.errors import ServerError

    attempts = []

    async def generate(self, request, stream=False):
        attempts.append(self.model)
        if self.model in {"gemini-3.5-flash-lite", "gemini-3.8-flash"}:
            raise ServerError(503, {"error": {"message": f"{self.model} overloaded"}})
        yield LlmResponse(content=types.Content(parts=[types.Part(text="OK from 3.6")]))

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    model = RecoverableGemini(
        model="gemini-3.5-flash-lite",
        fallback_model="gemini-3.8-flash",
    )
    replies = [
        response
        async for response in model.generate_content_async(
            LlmRequest(model="gemini-3.5-flash-lite")
        )
    ]

    assert replies[0].content.parts[0].text == "OK from 3.6"
    assert attempts == ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash"]
    failed_records = [r for r in model.records if r.get("status") == "failed"]
    assert len(failed_records) == 1
    assert failed_records[0]["model"] == "gemini-3.8-flash"
    assert failed_records[0]["fallback_error_code"] == 503

    success_records = [r for r in model.records if r.get("status") == "fallback"]
    assert len(success_records) == 1
    assert success_records[0]["model"] == "gemini-3.6-flash"
    assert model.model == "gemini-3.6-flash"



@pytest.mark.parametrize("reserve_primary,expected_calls", [(False, 1), (True, 2)])
async def test_fallback_reserves_quota_for_every_real_provider_attempt(
    monkeypatch, reserve_primary, expected_calls
):
    from google.adk.models import Gemini
    from google.adk.models.llm_request import LlmRequest
    from google.adk.models.llm_response import LlmResponse
    from google.genai.errors import ClientError

    attempts = []
    reservations = []

    class FakeQuota:
        def reserve(self, bucket, tokens):
            reservations.append((bucket, tokens))

        def reserve_with_wait(self, bucket, tokens, *, max_wait_seconds):
            assert max_wait_seconds == 60
            self.reserve(bucket, tokens)

    async def generate(self, request, stream=False):
        attempts.append(self.model)
        if self.model == "gemini-primary":
            raise ClientError(503, {"error": {"message": "unavailable"}})
        yield LlmResponse(content=types.Content(parts=[types.Part(text="OK")]))

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    model = RecoverableGemini(
        model="gemini-primary",
        fallback_model="gemini-fallback",
        quota=FakeQuota(),
        reserve_primary=reserve_primary,
    )
    replies = [
        response
        async for response in model.generate_content_async(LlmRequest(model="gemini-primary"))
    ]

    assert replies[0].content.parts[0].text == "OK"
    assert attempts == ["gemini-primary", "gemini-fallback"]
    assert len(reservations) == expected_calls
    assert all(bucket == "flash" and tokens >= 8192 for bucket, tokens in reservations)


@pytest.mark.parametrize("code", ["quota_daily_exhausted", "quota_minute_exhausted"])
async def test_adk_bounded_quota_wait_never_calls_provider_without_reservation(monkeypatch, code):
    from google.adk.models import Gemini
    from google.adk.models.llm_request import LlmRequest

    from app.tools.contracts import ToolError

    attempts, waits = [], []

    class Quota:
        def reserve_with_wait(self, bucket, tokens, *, max_wait_seconds):
            waits.append((bucket, max_wait_seconds))
            raise ToolError("limit reached", code=code)

    async def generate(self, request, stream=False):
        attempts.append(self.model)
        yield  # pragma: no cover

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    model = RecoverableGemini(
        model="gemini-primary", fallback_model="gemini-fallback",
        quota=Quota(), reserve_primary=True,
    )
    with pytest.raises(ToolError, match="limit reached"):
        [response async for response in model.generate_content_async(LlmRequest())]
    assert waits == [("flash", 60)]
    assert not attempts


async def test_primary_circuit_does_not_block_fallback_model(monkeypatch):
    from google.adk.models import Gemini
    from google.adk.models.llm_request import LlmRequest
    from google.adk.models.llm_response import LlmResponse
    from google.genai.errors import ServerError

    attempts = []
    circuit_calls = []

    class ModelScopedCircuit:
        def before_request(self, capability):
            circuit_calls.append(("before", capability))

        def failure(self, capability, exc):
            circuit_calls.append(("failure", capability))

        def success(self, capability):
            circuit_calls.append(("success", capability))

    async def generate(self, request, stream=False):
        attempts.append(self.model)
        if self.model == "gemini-primary":
            raise ServerError(503, {"error": {"message": "high demand"}})
        yield LlmResponse(content=types.Content(parts=[types.Part(text="OK")]))

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    model = RecoverableGemini(
        model="gemini-primary",
        fallback_model="gemini-fallback",
        circuit=ModelScopedCircuit(),
    )

    replies = [
        response
        async for response in model.generate_content_async(LlmRequest(model="gemini-primary"))
    ]

    assert replies[0].content.parts[0].text == "OK"
    assert attempts == ["gemini-primary", "gemini-fallback"]
    assert circuit_calls == [
        ("before", "generate:gemini-primary"),
        ("failure", "generate:gemini-primary"),
        ("before", "generate:gemini-fallback"),
        ("success", "generate:gemini-fallback"),
    ]


async def test_quota_exhaustion_blocks_fallback_provider_attempt(monkeypatch):
    from google.adk.models import Gemini
    from google.adk.models.llm_request import LlmRequest
    from google.genai.errors import ClientError

    from app.tools.contracts import ToolError

    attempts = []

    class FakeQuota:
        def reserve(self, bucket, tokens):
            raise ToolError("budget exhausted", code="quota_daily_exhausted")

    async def generate(self, request, stream=False):
        attempts.append(self.model)
        raise ClientError(503, {"error": {"message": "unavailable"}})
        yield  # pragma: no cover - keeps this an async generator

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    model = RecoverableGemini(
        model="gemini-primary", fallback_model="gemini-fallback", quota=FakeQuota()
    )
    with pytest.raises(ToolError, match="budget exhausted"):
        [
            response
            async for response in model.generate_content_async(LlmRequest(model="gemini-primary"))
        ]

    assert attempts == ["gemini-primary"]


async def test_adk_session_persists_and_isolates_user(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'adk.db'}"
    service = DatabaseSessionService(db_url=url)
    await service.create_session(app_name="drive_agent", user_id="a", session_id="conversation")
    await service.close()
    service = DatabaseSessionService(db_url=url)
    assert (
        await service.get_session(app_name="drive_agent", user_id="a", session_id="conversation")
        is not None
    )
    assert (
        await service.get_session(app_name="drive_agent", user_id="b", session_id="conversation")
        is None
    )
    await service.close()


def test_registry_schema_is_adk_function_declaration():
    import asyncio

    tool = GovernedAdkTool(
        calculator_tool_definitions()[0],
        ToolRegistry(),
        Settings(_env_file=None),
        "actor",
        "request",
        [],
        [],
        asyncio.Semaphore(2),
        set(),
    )
    declaration = tool._get_declaration()
    assert isinstance(declaration, types.FunctionDeclaration)
    assert declaration.name == "calculate"
    assert "values" in declaration.parameters_json_schema["properties"]


async def test_adk_returns_memoized_result_for_identical_tool_replay():
    import asyncio
    import json

    args = {"operation": "add", "values": [40, 2]}
    signature = "calculate" + json.dumps(args, sort_keys=True, ensure_ascii=False)
    cached = {"result": 42}
    records = []
    tool = GovernedAdkTool(
        calculator_tool_definitions()[0],
        ToolRegistry(),
        Settings(_env_file=None),
        "actor",
        "request",
        records,
        [],
        asyncio.Semaphore(2),
        {signature},
        {signature: cached},
    )

    result = await tool.run_async(args=args, tool_context=None)

    assert result == cached
    assert records == [
        {
            "stage": "tool_cache",
            "tool": "calculate",
            "status": "success",
            "cache_hit": True,
        }
    ]


async def test_memory_tool_supplies_numbered_real_reference_for_final_answer():
    import asyncio
    from datetime import UTC, datetime

    from app.agent.evidence import retain_referenced_citations
    from app.agent.orchestrator import AgentOrchestrator
    from app.api.schemas import MemoryResponse
    from app.services.memory import MemoryListResponse, memory_tool_definitions

    record = MemoryResponse(
        id="saved-memory", kind="fact", content="Dự án Mẫu có ba mục đã thống nhất.",
        tags=[], confidence=1.0, is_archived=False,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    registry = ToolRegistry()
    registry.execute = AsyncMock(return_value=MemoryListResponse(memories=[record]))
    evidence, events = [], []

    class FakeDb:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, model, owner):
            return SimpleNamespace(id=owner, is_active=True)

    definitions = memory_tool_definitions(SimpleNamespace(save=AsyncMock(), search=AsyncMock()))
    tool = GovernedAdkTool(
        definitions[1], registry, Settings(_env_file=None), "owner-a", "request-a",
        events, evidence, asyncio.Semaphore(2), set(),
    )
    with patch("app.agent.adk_orchestrator.SessionFactory", return_value=FakeDb()):
        payload = await tool.run_async(args={"query": "Dự án Mẫu"}, tool_context=None)
    assert payload["source_references"][0]["reference"] == 1
    assert payload["source_references"][0]["file_id"] == "memory:saved-memory"
    assert payload["source_references"][0]["snippet"] == record.content
    citations = AgentOrchestrator._collect_citations(evidence)
    answer, retained = retain_referenced_citations("Ba mục đã thống nhất [1].", citations)
    assert answer == "Ba mục đã thống nhất [1]."
    assert retained == citations
    assert len(retained) == 1


def test_adk_builds_real_coordinator_and_specialized_agents():
    """Multi-agent means an executable ADK tree, not only labels in the UI."""

    records = []
    model = RecoverableGemini(model="gemini-primary", fallback_model="gemini-fallback")
    agent = AdkOrchestrator._build_agent_tree(model, [], records)

    assert agent.name == "drive_coordinator"
    assert {child.name for child in agent.sub_agents} == {
        "email_agent",
        "web_research_agent",
        "company_info_agent",
        "calendar_agent",
        "report_generation_agent",
        "memory_agent",
        "human_approval_agent",
    }
    assert all(child.parent_agent is agent for child in agent.sub_agents)
    assert records[0]["stage"] == "multi_agent"


def test_adk_auto_router_skips_coordinator_for_clear_specialist_intents():
    assert AdkOrchestrator._auto_agent_for_request("So sánh hai cách ôn thi") == "study"
    assert AdkOrchestrator._auto_agent_for_request("Liệt kê các file Drive") == "research"
    assert (
        AdkOrchestrator._auto_agent_for_request(
            "Trong tài liệu DriveAgent QA Docs post-patch, mục tiêu là gì?"
        )
        == "research"
    )
    assert AdkOrchestrator._auto_agent_for_request("Tóm tắt email chưa đọc") == "communication"
    assert (
        AdkOrchestrator._auto_agent_for_request(
            "Dùng số liệu giả, không truy cập Gmail/Drive.",
            excluded_sources=frozenset({"gmail", "drive"}),
        )
        == "study"
    )
    assert AdkOrchestrator._auto_agent_for_request("Bạn làm được gì?") == "auto"


def test_memory_recall_does_not_route_to_excluded_local_sources():
    message = (
        "Chỉ tìm trong bộ nhớ dài hạn đã lưu mục dự án DEMO-V-031026. "
        "Mẫu báo cáo trước họp của dự án đó gồm những phần nào và áp dụng "
        "trong phạm vi nào? Không đọc Gmail, Drive, tài liệu local hay web; "
        "không lưu thêm hoặc tạo tài liệu. Nếu không có mục phù hợp thì nói "
        "chưa tìm thấy."
    )
    controls = ChatControls().enforce_explicit_source_exclusions(message)
    assert {"gmail", "drive", "local"}.issubset(controls.excluded_sources)
    assert "memory" not in controls.excluded_sources
    assert AdkOrchestrator._auto_agent_for_request(
        message, excluded_sources=controls.excluded_sources
    ) == "study"
    for marker in ("local", "trên máy", "vừa import"):
        assert AdkOrchestrator._auto_agent_for_request(
            f"Đọc tài liệu {marker}"
        ) == "research"
        assert AdkOrchestrator._auto_agent_for_request(
            f"Tìm bộ nhớ, không đọc tài liệu {marker}",
            excluded_sources=frozenset({"local"}),
        ) == "study"


def test_saved_skill_stays_in_adk_even_when_its_message_matches_direct_gmail_route():
    controls = ChatControls(skill_name="daily_news_brief")
    route = route_request("Tổng hợp email Bản chi tiết hôm nay")

    assert route.tool and route.tool.startswith("gmail_")
    assert not AdkOrchestrator._should_use_compiler(
        controls, route, "Tổng hợp email Bản chi tiết hôm nay"
    )
    assert AdkOrchestrator._should_use_compiler(
        ChatControls(),
        route,
        "Tổng hợp email Bản chi tiết hôm nay",
    )


def test_saved_skill_selects_dedicated_gmail_capability_agent():
    records = []
    model = RecoverableGemini(model="gemini-primary", fallback_model="gemini-fallback")
    agent = AdkOrchestrator._build_agent_tree(
        model,
        [],
        records,
        selected_agent="skill",
        selection_mode="user_selected",
        skill_capabilities=frozenset({"gmail"}),
    )

    assert agent.name == "skill_agent"
    assert "bắt buộc gọi skill_run" in agent.instruction
    assert "chỉ trả kết quả trong chat" in agent.instruction
    assert records[-1]["agent"] == "skill_agent"


def test_saved_skill_preserves_already_governed_explicit_source_tools():
    # This list represents the caller's filtered tools, not registry inventory.
    tools = [SimpleNamespace(name="local_source_read"), SimpleNamespace(name="calculate")]
    with patch("app.agent.adk_orchestrator.LlmAgent") as constructor:
        constructor.side_effect = lambda **kwargs: SimpleNamespace(**kwargs)
        agent = AdkOrchestrator._build_agent_tree(
            RecoverableGemini(model="gemini-primary", fallback_model="gemini-fallback"),
            tools, [], selected_agent="skill", skill_capabilities=frozenset(),
        )
    assert agent.name == "skill_agent"
    assert agent.tools == tools


@pytest.mark.parametrize("source_available", [False, True])
async def test_saved_skill_cannot_complete_without_reading_selected_local_source(source_available):
    from app.services.local_sources import local_source_tool_definitions
    from app.tools.contracts import ToolError

    class FakeSessions:
        async def get_session(self, **kwargs):
            return SimpleNamespace(id="existing")

    class FakeRunner:
        def __init__(self, **kwargs):
            pass

        async def run_async(self, **kwargs):
            yield SimpleNamespace(
                author="skill_agent", usage_metadata=None, is_final_response=lambda: True,
                content=types.Content(parts=[types.Part(text="Khách hàng có dự án ERP.")]),
            )

    registry = ToolRegistry()
    if source_available:
        for definition in local_source_tool_definitions():
            registry.register(definition)
    orchestrator = AdkOrchestrator(Settings(_env_file=None, gemini_api_key="test-key"), registry)
    orchestrator.client = genai.Client(api_key="test-key")
    orchestrator.sessions = FakeSessions()
    with (
        patch("app.agent.adk_orchestrator.skill_store", return_value=SimpleNamespace(
            get=lambda *_: {"active": True, "preferred_capabilities": []},
        )),
        patch("app.agent.adk_orchestrator.Runner", FakeRunner),
        pytest.raises(ToolError) as caught,
    ):
        await orchestrator.run(
            user=SimpleNamespace(id="user-a", role="editor"), session_id="session-a",
            request_id="skill-evidence-required",
            user_message="Chỉ dùng hai tài liệu local giả lập để tư vấn.",
            controls=ChatControls(skill_name="qa_final_tu_van"),
        )
    assert caught.value.code == (
        "skill_source_not_read" if source_available else "skill_source_unavailable"
    )


@pytest.mark.parametrize("calculator_available", [False, True])
async def test_saved_skill_cannot_silently_omit_requested_calculation(calculator_available):
    from app.tools.contracts import ToolError

    class FakeSessions:
        async def get_session(self, **kwargs):
            return SimpleNamespace(id="existing")

    class FakeRunner:
        def __init__(self, **kwargs):
            assert "calculate" in {tool.name for tool in kwargs["agent"].tools}

        async def run_async(self, **kwargs):
            yield SimpleNamespace(
                author="skill_agent", usage_metadata=None, is_final_response=lambda: True,
                content=types.Content(parts=[types.Part(text="Có 24 người trong nhóm.")]),
            )

    registry = ToolRegistry()
    if calculator_available:
        for definition in calculator_tool_definitions():
            registry.register(definition)
    orchestrator = AdkOrchestrator(Settings(_env_file=None, gemini_api_key="test-key"), registry)
    orchestrator.client = genai.Client(api_key="test-key")
    orchestrator.sessions = FakeSessions()
    with (
        patch("app.agent.adk_orchestrator.skill_store", return_value=SimpleNamespace(
            get=lambda *_: {"active": True, "preferred_capabilities": []},
        )),
        patch("app.agent.adk_orchestrator.Runner", FakeRunner),
        pytest.raises(ToolError) as caught,
    ):
        await orchestrator.run(
            user=SimpleNamespace(id="user-a", role="editor"), session_id="session-a",
            request_id="skill-calculation-required",
            user_message="Dữ liệu giả lập: 24 người, 12 phút/người. Tính thời gian bằng công cụ.",
            controls=ChatControls(skill_name="qa_final_tu_van"),
        )
    assert caught.value.code == (
        "skill_calculation_not_run" if calculator_available else "skill_calculation_unavailable"
    )


def test_forbidden_google_creation_does_not_disable_memory_agent_tools():
    from app.agent.routing import Route

    message = (
        "Lưu vào bộ nhớ một ghi chú giả lập: dự án TEST có ba mục. "
        "Không đọc Gmail, Drive hay nguồn bên ngoài, không tạo tài liệu Google."
    )
    assert not AdkOrchestrator._should_use_compiler(ChatControls(), Route(), message)
    assert not AdkOrchestrator._has_workspace_creation_request(
        "Không tạo Google Doc, chỉ ghi nhớ yêu cầu."
    )
    assert not AdkOrchestrator._has_workspace_creation_request(
        "Do not create a Google document. Save this preference in memory."
    )
    assert AdkOrchestrator._has_workspace_creation_request(
        "Không đọc Gmail, nhưng tạo Google Doc với dữ liệu giả."
    )
    assert AdkOrchestrator._should_use_compiler(
        ChatControls(), Route(), "Tạo tài liệu Google từ dữ liệu tôi cung cấp."
    )


def test_study_agent_keeps_unsourced_scientific_claims_conditional():
    records = []
    model = RecoverableGemini(model="gemini-primary", fallback_model="gemini-fallback")
    agent = AdkOrchestrator._build_agent_tree(
        model, [], records, selected_agent="study", selection_mode="server_routed"
    )

    assert agent.name == "memory_agent"
    assert "không tự thêm thời lượng, tỷ lệ" in agent.instruction
    assert "gọi calculate cho các biểu thức then chốt" in agent.instruction
    assert records[-1] == {
        "stage": "agent_selection",
        "status": "success",
        "agent": "memory_agent",
        "mode": "server_routed",
    }


def test_communication_agent_has_compact_evidence_aware_triage_contract():
    records = []
    model = RecoverableGemini(model="gemini-primary", fallback_model="gemini-fallback")
    agent = AdkOrchestrator._build_agent_tree(
        model, [], records, selected_agent="communication", selection_mode="server_routed"
    )

    assert agent.name == "email_agent"
    assert "### Cần trả lời" in agent.instruction
    assert "Không lặp thêm dòng `Bằng chứng: [n]`" in agent.instruction
    assert "cảnh báo tự động/no-reply" in agent.instruction
    assert "chỉ nêu deadline khi email nói rõ" in agent.instruction


@pytest.mark.parametrize(
    ("question", "required"),
    [
        (
            "/general Tổng hợp email chưa đọc và phân nhóm hành động.",
            (
                "## Cần trả lời",
                "## Cần theo dõi",
                "## Chỉ để biết",
                "## Bước tiếp theo",
                "1.",
                "2.",
            ),
        ),
        (
            "/general Tạo bản xem trước Google Doc từ ghi chú cuộc họp.",
            ("## Bản xem trước trước khi tạo", "## Xác nhận cần thiết", "Duyệt và tạo", "đọc lại"),
        ),
        (
            "/general Tạo bản xem trước Google Sheets theo dõi chi tiêu.",
            (
                "## Bản xem trước",
                "## Công thức dự kiến",
                "## Trước khi ghi",
                "=SUM",
                "Chưa tạo bảng",
                "đọc lại",
                "| Hạng mục |",
            ),
        ),
    ],
)
def test_general_workflow_templates_are_scannable_and_truthful(question, required):
    answer = deterministic_static_answer(question)
    assert answer is not None
    missing = [fragment for fragment in required if fragment not in answer]
    assert not missing, f"missing={missing!r}; answer={answer!r}"


def test_general_workflow_templates_do_not_intercept_real_provider_requests():
    assert deterministic_static_answer("Tổng hợp email chưa đọc và phân nhóm hành động.") is None


def test_short_mcp_explanation_is_plain_and_complete():
    answer = deterministic_static_answer("Hãy trả lời ngắn gọn MCP là gì.", general_route=True)
    assert answer is not None
    assert "giao thức mở" in answer
    assert "công cụ hoặc nguồn dữ liệu bên ngoài" in answer
    assert len(answer.split()) < 80


async def test_explicit_rag_only_request_uses_deterministic_compiler():
    orchestrator = AdkOrchestrator(Settings(_env_file=None), ToolRegistry())
    expected = SimpleNamespace(answer="stale index")
    orchestrator.compiler.run = AsyncMock(return_value=expected)

    result = await orchestrator.run(
        user=SimpleNamespace(id="user-a"),
        session_id="session-a",
        request_id="request-a",
        user_message="Chỉ dùng RAG đã lập chỉ mục: mục tiêu là gì?",
    )

    assert result is expected
    assert orchestrator.compiler.run.await_args.kwargs["controls"].source == "rag"


async def test_safe_direct_route_uses_compiler_without_coordinator_model_turn():
    orchestrator = AdkOrchestrator(Settings(_env_file=None), ToolRegistry())
    expected = SimpleNamespace(answer="13")
    orchestrator.compiler.run = AsyncMock(return_value=expected)

    result = await orchestrator.run(
        user=SimpleNamespace(id="user-a"),
        session_id="session-a",
        request_id="request-a",
        user_message="Tính 9 + 4",
    )

    assert result is expected
    orchestrator.compiler.run.assert_awaited_once()


async def test_local_source_request_uses_deterministic_compiler_gather():
    orchestrator = AdkOrchestrator(Settings(_env_file=None), ToolRegistry())
    expected = SimpleNamespace(answer="local")
    orchestrator.compiler.run = AsyncMock(return_value=expected)

    result = await orchestrator.run(
        user=SimpleNamespace(id="user-a"),
        session_id="session-a",
        request_id="request-a",
        user_message="Trong tệp local local-study-smoke.md: Mã kiểm thử là gì?",
    )

    assert result is expected
    orchestrator.compiler.run.assert_awaited_once()


async def test_adk_requires_configured_client_and_session_for_open_ended_work():
    orchestrator = AdkOrchestrator(Settings(_env_file=None), ToolRegistry())
    with pytest.raises(AgentNotConfiguredError, match="Gemini"):
        await orchestrator.run(
            user=SimpleNamespace(id="user-a", role="editor"),
            session_id="session-a",
            request_id="request-a",
            user_message="Hãy giúp tôi suy nghĩ về kế hoạch tuần này",
        )


async def test_adk_open_ended_run_records_session_handoff_usage_and_final_answer():
    runner_models = []

    class FakeSessions:
        async def get_session(self, **_kwargs):
            return SimpleNamespace(id="existing")

    class FakeRunner:
        def __init__(self, **_kwargs):
            runner_models.append(_kwargs["agent"].model)

        async def run_async(self, **_kwargs):
            yield SimpleNamespace(
                author="study_agent",
                usage_metadata=SimpleNamespace(
                    model_dump=lambda **_kwargs: {
                        "prompt_token_count": 12,
                        "candidates_token_count": 8,
                        "total_token_count": 20,
                    }
                ),
                is_final_response=lambda: False,
                content=None,
            )
            yield SimpleNamespace(
                author="study_agent",
                usage_metadata=None,
                is_final_response=lambda: True,
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(
                            text="## Kế hoạch\n\n1. Bắt đầu từ việc nhỏ.", thought=False
                        ),
                        SimpleNamespace(text="hidden", thought=True),
                    ]
                ),
            )

    settings = Settings(_env_file=None, gemini_api_key="test-key")
    orchestrator = AdkOrchestrator(settings, ToolRegistry())
    orchestrator.client = genai.Client(api_key="test-key")
    orchestrator.sessions = FakeSessions()
    with (
        patch("app.agent.adk_orchestrator.Runner", FakeRunner),
        patch(
            "app.agent.adk_orchestrator.enforce_presentation_contract",
            AsyncMock(side_effect=lambda **kwargs: kwargs["answer"]),
        ),
    ):
        result = await orchestrator.run(
            user=SimpleNamespace(id="user-a", role="editor"),
            session_id="session-a",
            request_id="request-a",
            user_message="Hãy giúp tôi suy nghĩ về kế hoạch tuần này",
        )

    assert result.answer == "## Kế hoạch\n\n1. Bắt đầu từ việc nhỏ."
    assert result.citations == []
    assert {record["stage"] for record in result.trace} >= {"agent_handoff", "usage"}
    assert len(runner_models) == 1
    assert runner_models[0].reserve_primary is True
    assert runner_models[0].quota is orchestrator.compiler.quota


@pytest.mark.parametrize("repair_mode", ["unchanged", "collapsed", "headline"])
async def test_adk_presentation_repair_receives_collected_tool_evidence_and_references(repair_mode):
    citation = {"file_id": "local:sample", "file_name": "sample.md", "chunk_index": 0,
                "snippet": "Nhóm khảo sát có 42 người.", "score": 1.0}
    if repair_mode == "headline":
        citation.update(file_name="Sản phẩm mẫu", evidence_kind="headline",
                        published_at="2026-10-02T07:00:00Z")
    tool_content = json.dumps({"data": {"citations": [citation]}}, ensure_ascii=False)

    class FakeSessions:
        async def get_session(self, **_kwargs):
            return SimpleNamespace(id="existing")

    class FakeRunner:
        def __init__(self, **kwargs):
            # Replace only tool/provider execution; the outer ADK route still
            # collects and forwards the same ToolMessages to presentation repair.
            tools = kwargs["agent"].tools
            tools[0].evidence.append(ToolMessage(
                name="local_source_read", content=tool_content, tool_call_id="read-sample",
            ))

        async def run_async(self, **_kwargs):
            yield SimpleNamespace(
                author="report_agent", usage_metadata=None, is_final_response=lambda: True,
                content=types.Content(parts=[types.Part(text="Nhóm có 42 người [1].")]),
            )

    registry = ToolRegistry()
    for definition in calculator_tool_definitions():
        registry.register(definition)
    orchestrator = AdkOrchestrator(Settings(_env_file=None, gemini_api_key="test-key"), registry)
    orchestrator.client = genai.Client(api_key="test-key")
    orchestrator.sessions = FakeSessions()
    def revised_answer(**kwargs):
        if repair_mode == "collapsed":
            return "## Hiện trạng\nNhóm có 42 người [1]. ## Việc tiếp theo\nHỏi ngân sách."
        if repair_mode == "headline":
            return "Đã ra mắt sản phẩm mới ngày 02/10 [1]."
        return kwargs["answer"]

    repair = AsyncMock(side_effect=revised_answer)
    with (
        patch("app.agent.adk_orchestrator.Runner", FakeRunner),
        patch.object(orchestrator, "_build_agent_tree",
                     side_effect=lambda model, tools, records, **kwargs:
                     SimpleNamespace(tools=tools)),
        patch("app.agent.adk_orchestrator.enforce_presentation_contract", repair),
    ):
        result = await orchestrator.run(
            user=SimpleNamespace(id="user-a", role="editor"), session_id="session-a",
            request_id="repair-evidence", user_message="Giải thích cách cải thiện báo cáo",
        )
    assert result.citations == [citation]
    if repair_mode == "collapsed":
        assert "[1].\n\n## Việc tiếp theo" in result.answer
        assert "Nhóm có 42 người" in result.answer
    if repair_mode == "headline":
        assert "Đã ra mắt" not in result.answer
        assert "ngày đăng: 2026-10-02 [1]" in result.answer
        assert "ngày sự kiện và nội dung chi tiết chưa xác minh" in result.answer
        assert any(item.get("rule") == "headline_evidence_boundary" for item in result.trace)
    repair.assert_awaited_once()
    assert repair.await_args.kwargs["source_evidence_untrusted"] == [
        {"tool": "local_source_read", "result_untrusted": tool_content},
    ]
    assert repair.await_args.kwargs["source_references_untrusted"] == [
        {"reference": 1, **citation},
    ]


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("with_sources", [False, True])
async def test_adk_restores_owner_scoped_canonical_history(existing, with_sources):
    captured = {}
    sources = [{"file_id": "local:sample", "file_name": "mau.md", "chunk_index": 0,
                "snippet": "42 nhân viên", "score": 1.0}]

    class FakeSessions:
        async def get_session(self, **kwargs):
            captured["execution_session"] = kwargs["session_id"]
            return SimpleNamespace(last_update_time=1.0) if existing else None

        async def create_session(self, **kwargs):
            captured["session"] = kwargs

    class FakeDb:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def scalars(self, query):
            captured["query"] = query.compile().params
            rows = [SimpleNamespace(role="user", content="Khách hàng Mẫu có 42 nhân viên.")]
            if with_sources:
                rows.append(SimpleNamespace(role="assistant", content="42 nhân viên [1].",
                                            citations_json=json.dumps(sources)))
            return rows

    class FakeRunner:
        def __init__(self, **kwargs):
            pass

        async def run_async(self, **kwargs):
            captured["runner_session"] = kwargs["session_id"]
            captured["request"] = kwargs["new_message"].parts[0].text
            yield SimpleNamespace(
                author="report_agent", usage_metadata=None,
                is_final_response=lambda: True,
                content=types.Content(parts=[types.Part(
                    text="Khách hàng có 42 nhân viên [1]." if with_sources
                    else "Khách hàng có 42 nhân viên."
                )]),
            )

    orchestrator = AdkOrchestrator(Settings(_env_file=None, gemini_api_key="test-key"),
                                 ToolRegistry())
    orchestrator.client = genai.Client(api_key="test-key")
    orchestrator.sessions = FakeSessions()
    with (
        patch("app.agent.adk_orchestrator.SessionFactory", return_value=FakeDb()),
        patch("app.agent.adk_orchestrator.Runner", FakeRunner),
        patch("app.agent.adk_orchestrator.enforce_presentation_contract",
              AsyncMock(side_effect=lambda **kwargs: kwargs["answer"])),
    ):
        result = await orchestrator.run(
            user=SimpleNamespace(id="owner-a", role="editor"), session_id="session-a",
            request_id="request-a", user_message=(
                "Nhắc lại thông tin đã trao đổi. Chỉ dùng ngữ cảnh cuộc trò chuyện."
                if with_sources else "Nhắc lại thông tin đã trao đổi."
            ),
        )
    assert "42 nhân viên" in captured["request"]
    assert "owner-a" in captured["query"].values()
    assert "session-a" in captured["query"].values()
    assert captured["runner_session"] == captured["execution_session"]
    assert captured["runner_session"].startswith("session-a--")
    assert "Asia/Bangkok" in captured["request"]
    assert "Không thay ngày giờ cuộc hẹn" in captured["request"]
    assert "giữ dữ kiện hội thoại sau đính chính mới nhất" in captured["request"]
    if existing:
        assert "session" not in captured
        assert any(hasattr(value, "year") for value in captured["query"].values())
    else:
        assert captured["session"]["user_id"] == "owner-a"
    assert any(item.get("restored_messages") == (2 if with_sources else 1)
               for item in result.trace)
    if with_sources:
        assert result.citations == sources
        assert "[1]" in result.answer
        assert "chưa xác minh lại" in captured["request"]
        assert "theo đính chính của bạn" in captured["request"]
        assert "không gắn tham chiếu tài liệu" in captured["request"]
        assert any(item.get("source_count") == 1 for item in result.trace)
