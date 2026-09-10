from google.adk.sessions import DatabaseSessionService
from google.genai import types

from app.agent.adk_orchestrator import AdkOrchestrator, GovernedAdkTool, RecoverableGemini
from app.core.config import Settings
from app.tools.calculator import calculator_tool_definitions
from app.tools.registry import ToolRegistry


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


def test_adk_builds_real_coordinator_and_specialized_agents():
    """Multi-agent means an executable ADK tree, not only labels in the UI."""

    records = []
    model = RecoverableGemini(model="gemini-primary", fallback_model="gemini-fallback")
    agent = AdkOrchestrator._build_agent_tree(model, [], records)

    assert agent.name == "drive_coordinator"
    assert {child.name for child in agent.sub_agents} == {
        "research_agent",
        "communication_agent",
        "study_agent",
        "workspace_agent",
    }
    assert all(child.parent_agent is agent for child in agent.sub_agents)
    assert records[0]["stage"] == "multi_agent"
