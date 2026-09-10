"""Real ADK runner with only the provider boundary replaced; no paid/live calls."""

import json

import pytest
from google.adk.models import Gemini
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agent import compiler
from app.core.config import Settings
from app.db.models import Base, ChatSession, Message, User
from app.tools.calculator import calculator_tool_definitions
from app.tools.contracts import ToolError
from app.tools.registry import ToolRegistry


@pytest.fixture
async def runtime(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        gemini_api_key="fake-not-a-real-key",
        gemini_chat_model="gemini-3.8-flash",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
    )
    engine = create_async_engine(settings.resolved_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(compiler, "SessionFactory", factory)
    async with factory() as db:
        user = User(email="a@test.invalid", display_name="A", role="editor")
        other = User(email="b@test.invalid", display_name="B", role="editor")
        db.add_all([user, other])
        await db.flush()
        session = ChatSession(user_id=user.id)
        other_session = ChatSession(user_id=other.id)
        db.add_all([session, other_session])
        await db.flush()
        db.add_all(
            [
                Message(user_id=user.id, session_id=session.id, role="user", content="A_HISTORY"),
                Message(
                    user_id=other.id, session_id=other_session.id, role="user", content="B_PRIVATE"
                ),
            ]
        )
        await db.commit()
    registry = ToolRegistry()
    for definition in calculator_tool_definitions():
        registry.register(definition)
    runner = compiler.CompilerOrchestrator(settings, registry)
    await runner.initialize()
    yield runner, user, session.id
    await runner.close()
    await engine.dispose()


async def test_one_real_adk_round_and_tenant_history(runtime, monkeypatch):
    seen = []

    async def generate(self, request, stream=False):
        seen.append(request)
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text='{"answer":"Đây là câu trả lời đã tổng hợp."}')],
            )
        )

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="one-call",
        user_message="Giải thích cách học hiệu quả",
    )
    assert len(seen) == 1
    assert "A_HISTORY" in str(seen[0].contents)
    assert "B_PRIVATE" not in str(seen[0].contents)
    assert not seen[0].tools_dict
    assert seen[0].config.response_schema is None
    assert seen[0].config.response_json_schema["additionalProperties"] is False
    assert result.trace[-1]["model_call_count"] == 1


async def test_direct_calculation_has_zero_model_calls(runtime, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Direct route must not use Gemini")
        yield  # Makes this the same async-generator interface as the SDK.

    monkeypatch.setattr(Gemini, "generate_content_async", forbidden)
    runner, user, session_id = runtime
    result = await runner.run(
        user=user, session_id=session_id, request_id="direct", user_message="Tính 0.1 + 0.2"
    )
    assert result.answer == "0.3"
    assert not any(item.get("stage") == "model" for item in result.trace)


async def test_multi_output_proposals_one_call_without_writes(runtime, monkeypatch):
    calls = []
    output = {
        "answer": "Đây là hai bản đề xuất. Hãy kiểm tra trước khi tạo file.",
        "proposals": [
            {"kind": "document", "document": {"title": "Kế hoạch", "blocks": [{"text": "Ôn tập"}]}},
            {
                "kind": "spreadsheet",
                "spreadsheet": {
                    "title": "Tiến độ",
                    "tabs": [
                        {"title": "Tuần", "headers": ["Việc", "Giờ"], "rows": [["Ôn tập", 2]]}
                    ],
                },
            },
        ],
    }

    async def generate(self, request, stream=False):
        calls.append(request)
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=json.dumps(
                            {
                                "answer": output["answer"],
                                "proposals": [
                                    {"kind": p["kind"], "spec_json": json.dumps(p[p["kind"]])}
                                    for p in output["proposals"]
                                ],
                            }
                        )
                    )
                ],
            )
        )

    async def no_write(*args, **kwargs):
        raise AssertionError("Proposal generation must not call an executor")

    runner, user, session_id = runtime
    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    monkeypatch.setattr(runner.registry, "execute", no_write)
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="bundle",
        user_message="Tạo Google Docs kế hoạch và Google Sheets tiến độ ôn tập",
    )
    assert len(calls) == 1 and len(result.proposals) == 2
    assert result.proposals[0]["kind"] == "document"
    assert result.proposals[1]["kind"] == "spreadsheet"
    assert not calls[0].tools_dict


async def test_invalid_output_is_not_repaired_with_another_call(runtime, monkeypatch):
    calls = []

    async def generate(self, request, stream=False):
        calls.append(1)
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text='{"answer":""}')])
        )

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    with pytest.raises(ToolError) as failure:
        await runner.run(
            user=user,
            session_id=session_id,
            request_id="invalid",
            user_message="Giải thích khái niệm agent",
        )
    assert failure.value.code == "invalid_spec"
    assert len(calls) == 1


async def test_fulltext_search_reads_exact_filename_among_mentions(runtime, monkeypatch):
    from app.api.schemas import DriveFileListResponse, DriveFileResponse, FileContentResponse

    runner, user, session_id = runtime
    exact = DriveFileResponse(id="correct-id", name="notes.md", mime_type="text/markdown")
    mention = DriveFileResponse(id="other-id", name="References.pdf", mime_type="application/pdf")
    read_ids = []

    async def execute(name, arguments, context):
        if name == "drive_search_files":
            return DriveFileListResponse(files=[mention, exact])
        assert name == "drive_read_file"
        read_ids.append(arguments["file_id"])
        return FileContentResponse(file=exact, text="Verified fixture content")

    async def generate(self, request, stream=False):
        assert "Verified fixture content" in str(request.contents)
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text='{"answer":"OK"}')])
        )

    monkeypatch.setattr(runner.registry, "execute", execute)
    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="exact-match",
        user_message="Tìm file notes.md, đọc và tóm tắt",
    )
    assert read_ids == ["correct-id"]
    assert result.answer == "OK"
