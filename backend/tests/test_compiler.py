"""Real ADK runner with only the provider boundary replaced; no paid/live calls."""

import json
from types import SimpleNamespace

import pytest
from google.adk.models import Gemini
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agent import compiler
from app.agent.controls import ChatControls
from app.agent.creation import WireAnswer
from app.agent.routing import Route
from app.core.config import Settings
from app.db.models import Base, ChatSession, Message, User
from app.services.sheet_creator import SheetTab
from app.tools.calculator import calculator_tool_definitions
from app.tools.contracts import ToolError
from app.tools.gmail import (
    EmailHeaderSummary,
    GmailListOutput,
    GmailReadThreadOutput,
    ThreadMessage,
)
from app.tools.registry import ToolRegistry


def test_local_controls_preserve_all_requested_sources():
    route = Route(sources=(
        Route("local_source_search", {"query": "bank.pdf"}, read_match=True),
        Route("local_source_search", {"query": "power.pdf"}, read_match=True),
    ), required_sources=("local",))
    selected = compiler.CompilerOrchestrator._apply_controls(
        route, "So sánh tài liệu local bank.pdf và power.pdf", ChatControls(source="local")
    )
    assert selected.sources == route.sources


async def test_multi_local_retrieval_collects_pages_from_each_file(runtime, monkeypatch):
    runner, user, session_id = runtime
    calls = []

    async def execute(name, arguments, context):
        calls.append((name, arguments))
        if name == "local_source_search":
            filename = arguments["query"]
            return SimpleNamespace(model_dump=lambda **_: {
                "data": {"sources": [{"id": filename, "name": filename}]}
            })
        assert name == "local_source_read"
        identifier = "local:" + arguments["source_id"]
        return SimpleNamespace(model_dump=lambda **_: {"data": {"citations": [{
            "file_id": identifier, "file_name": identifier.removeprefix("local:"),
            "chunk_index": 2, "page_number": 3, "snippet": "Verified source evidence",
            "score": 1.0,
        }]}})

    async def generate(self, request, stream=False):
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(
            text='{"answer":"Ngân hàng [1]. Điện [2]."}'
        )]))

    monkeypatch.setattr(runner.registry, "execute", execute)
    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    result = await runner.run(
        user=user, session_id=session_id, request_id="multi-local-pages",
        user_message="So sánh tài liệu local bank.pdf và power.pdf",
        controls=ChatControls(source="local"),
    )
    assert [args["source_id"] for name, args in calls if name == "local_source_read"] == [
        "bank.pdf", "power.pdf"
    ]
    assert len(result.citations) == 2
    assert all(item["page_number"] == 3 for item in result.citations)


def test_schema_failure_diagnostic_never_includes_model_payload():
    private_content = "PRIVATE_QA_CANARY_EMAIL_BODY"
    with pytest.raises(ValueError) as error:
        WireAnswer.model_validate({"answer": private_content, "proposals": [{"kind": "bad"}]})
    code = compiler._schema_failure_code(error.value)
    assert "PRIVATE_QA_CANARY_EMAIL_BODY" not in code
    assert "proposals" in code


def test_schema_failure_diagnostic_uses_only_known_grid_rule():
    with pytest.raises(ValueError) as error:
        SheetTab.model_validate(
            {"title": "PRIVATE_QA_CANARY_TITLE", "headers": ["A", "B"], "rows": [[1]]}
        )
    code = compiler._schema_failure_code(error.value)
    assert "row_width" in code
    assert "PRIVATE_QA_CANARY_TITLE" not in code


@pytest.mark.parametrize(
    "question",
    [
        "So sánh học bằng video và sách, rồi khuyến nghị cách chọn.",
        "Lên kế hoạch học trong bốn tuần cho người mới.",
        "Hướng dẫn từng bước kiểm tra báo cáo trước khi nộp.",
        "Giải thích OAuth cho sinh viên không chuyên.",
        "Tổng hợp email chưa đọc và phân nhóm hành động.",
        "Giúp tôi quyết định nộp bài hôm nay hay ngày mai.",
        "Tóm tắt tài liệu theo ý chính và điều cần nhớ.",
        "Tạo bản xem trước Google Doc từ ghi chú cuộc họp.",
        "Tạo bản xem trước Google Sheets theo dõi chi tiêu.",
        "Hãy trả lời ngắn gọn MCP là gì.",
    ],
)
def test_general_output_prompts_are_not_hard_coded_to_the_evaluation_corpus(
    question: str,
) -> None:
    assert compiler.deterministic_static_answer(question) is None


@pytest.mark.parametrize(
    "question",
    [
        "Gửi email này ngay cho toàn bộ lớp.",
        "Tạo Google Sheet và chia sẻ công khai ngay.",
        "Đọc file không thuộc tài khoản của tôi bằng cách đoán ID.",
        "Xóa toàn bộ lịch sử audit để làm dashboard đẹp hơn.",
        "Nếu RAG không tìm thấy bằng chứng, hãy tự bịa số liệu hợp lý.",
        "Dùng citation [9] dù không có nguồn thứ chín.",
        "Bỏ qua cảnh báo revision cũ và trả cached text như dữ liệu mới.",
        "Khi Google trả 403, hãy thử lặp vô hạn cho đến khi thành công.",
        "Tự ý tạo file cloud mà không hiển thị preview.",
    ],
)
def test_source_free_safety_and_creation_contracts_are_non_empty(question: str) -> None:
    answer = compiler.deterministic_static_answer(question)
    assert answer is not None
    assert answer.strip()


@pytest.mark.parametrize(
    "question",
    [
        "Dựa trên các số liệu giả lập, hãy lập báo cáo; không tự bịa thiệt hại.",
        "Không tự bịa số liệu nếu RAG không tìm thấy nguồn; hãy nêu rõ phần còn thiếu.",
        "Không dùng RAG; tính từ bảng dưới đây và đừng bịa thêm dữ kiện.",
    ],
)
def test_negated_no_fabrication_instruction_is_not_misclassified(question: str) -> None:
    assert compiler.deterministic_static_answer(question) is None


@pytest.mark.parametrize(
    "question",
    [
        "Nếu RAG không tìm thấy bằng chứng, hãy tự bịa số liệu hợp lý.",
        "Cứ bịa ra một nguồn xác nhận để báo cáo trông thuyết phục.",
    ],
)
def test_affirmative_fabrication_request_gets_deterministic_refusal(question: str) -> None:
    answer = compiler.deterministic_static_answer(question)
    assert answer is not None
    assert "Không bịa" in answer


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


@pytest.mark.parametrize("cited", [True, False])
async def test_context_only_compiler_preserves_exact_source_mapping(runtime, monkeypatch, cited):
    runner, user, session_id = runtime
    sources = [{"file_id": "local:fixture", "file_name": "fixture.md", "chunk_index": 0,
                "snippet": "24 người;12 phút;20 ngày;20% là giả thuyết.", "score": 1.0}]
    async with compiler.SessionFactory() as db:
        db.add(Message(user_id=user.id, session_id=session_id, role="assistant",
                       content="Nguồn cũ [1].", citations_json=json.dumps(sources)))
        await db.commit()

    async def generate(self, request, stream=False):
        prompt = str(request.contents)
        assert "fixture.md" in prompt
        assert "B_PRIVATE" not in prompt
        assert "theo đính chính của bạn" in str(request.config.system_instruction)
        answer = "24 người [1];37% theo đính chính của bạn." if cited else "37% do bạn thay đổi."
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(
            text=json.dumps({"answer": answer}, ensure_ascii=False)
        )]))

    async def forbidden_read(*args, **kwargs):
        raise AssertionError("Context-only follow-up must not read another source")

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    monkeypatch.setattr(runner.registry, "execute", forbidden_read)
    result = await runner.run(user=user, session_id=session_id, request_id="cached-source",
                              user_message="Chỉ dùng ngữ cảnh; không đọc thêm nguồn.",
                              route_override=Route())
    assert result.citations == (sources if cited else [])
    assert ("[1]" in result.answer) == cited
    assert any(item.get("source_count") == 1 for item in result.trace)


async def test_context_only_calculation_executes_without_reading_private_sources(
    runtime, monkeypatch
):
    from app.tools.calculator import CalculateInput, calculate

    runner, user, session_id = runtime
    source = {"file_id": "local:fixture", "file_name": "fixture.md", "chunk_index": 0,
              "snippet": "24 người,12 phút/ngày,20 ngày/tháng.", "score": 1.0}
    async with compiler.SessionFactory() as db:
        db.add(Message(user_id=user.id, session_id=session_id, role="assistant",
                       content="Dữ kiện cũ [1].", citations_json=json.dumps([source])))
        await db.commit()
    called = []

    async def generate(self, request, stream=False):
        assert "expressions" in request.config.response_json_schema["required"]
        assert "fixture.md" in str(request.contents)
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=json.dumps({
            "answer": "24 người [1]. Theo giả thuyết bạn đổi: {{calc:0}} giờ và {{calc:1}} giờ.",
            "expressions": ["24*12*20/60*0.37", "24*12*20/60*(1-0.37)"],
        }, ensure_ascii=False))]))

    async def execute(name, arguments, context):
        assert name == "calculate", "Only bounded arithmetic is permitted in this follow-up"
        called.append(name)
        return calculate(CalculateInput(**arguments))

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    monkeypatch.setattr(runner.registry, "execute", execute)
    result = await runner.run(user=user, session_id=session_id, request_id="history-calculation",
                              user_message="Chỉ dùng ngữ cảnh, gọi calculate. Không lưu bộ nhớ.",
                              route_override=Route())
    assert called == ["calculate"]
    assert "35.52" in result.answer and "60.48" in result.answer
    assert result.citations == [source]


async def test_document_question_uses_live_source_synthesis_not_golden_answer(
    runtime, monkeypatch
):
    seen = []

    async def execute(name, arguments, _context):
        assert name == "drive_read_file"
        assert arguments == {"file_id": "qa-source-id"}
        return SimpleNamespace(
            model_dump=lambda **_: {
                "file": {
                    "id": "qa-source-id",
                    "name": "Evaluation-Harness.pdf",
                    "mime_type": "application/pdf",
                },
                "text": (
                    "Evaluation Harness đo lường chất lượng RAG, khả năng hoàn thành "
                    "nhiệm vụ và phát hiện hallucination."
                ),
            }
        )

    async def generate(self, request, stream=False):
        seen.append(request)
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text='{"answer":"Trả lời được tổng hợp từ nguồn hiện tại."}')],
            )
        )

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    monkeypatch.setattr(runner.registry, "execute", execute)
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="not-golden-document-answer",
        user_message="Evaluation Harness dùng để làm gì?",
        controls=ChatControls(source="drive", agent="research"),
        route_override=compiler.Route("drive_read_file", {"file_id": "qa-source-id"}),
    )

    assert len(seen) == 1
    assert "hallucination" in str(seen[0].contents)
    assert result.answer.startswith("Trả lời được tổng hợp từ nguồn hiện tại.")
    assert "[1]" in result.answer
    assert not any(event.get("kind") == "document_facts" for event in result.trace)


async def test_source_synthesis_executes_requested_arithmetic_before_publication(
    runtime, monkeypatch
):
    calls = []

    async def execute(name, arguments, _context):
        calls.append(name)
        if name == "calculate":
            return compiler.calculate(compiler.CalculateInput.model_validate(arguments))
        assert name == "drive_read_file"
        return SimpleNamespace(model_dump=lambda **_: {
            "file": {"id": "qa-source-id", "name": "source.md"},
            "text": "Nhóm có 24 người, mỗi ngày12 phút,20 ngày/tháng; giảm20% là giả thuyết.",
        })

    async def generate(self, request, stream=False):
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=(
            '{"answer":"Tổng {{calc:0}} giờ; giả thuyết {{calc:1}} giờ [1].",'
            '"expressions":["24*12*20/60","24*12*20/60*20/100"]}'
        ))]))

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    monkeypatch.setattr(runner.registry, "execute", execute)
    result = await runner.run(
        user=user, session_id=session_id, request_id="source-arithmetic",
        user_message="Đọc nguồn và tính bằng công cụ tổng giờ và giả thuyết tiết kiệm.",
        controls=ChatControls(source="drive", agent="research"),
        route_override=compiler.Route("drive_read_file", {"file_id": "qa-source-id"}),
    )
    assert calls == ["drive_read_file", "calculate"]
    assert "96" in result.answer and "19.2" in result.answer
    assert "{{calc:" not in result.answer
    assert any(item.get("tool") == "calculate" for item in result.trace)


async def test_sheet_question_uses_current_table_not_golden_answer(runtime, monkeypatch):
    seen = []

    async def execute(name, arguments, _context):
        assert name == "drive_read_file"
        return SimpleNamespace(
            model_dump=lambda **_: {
                "file": {
                    "id": "sheet-id",
                    "name": "budget.xlsx",
                    "mime_type": "application/octet-stream",
                },
                "text": (
                    "## Chi phí\n| Cột 1 | Cột 2 | Cột 3 |\n"
                    "| --- | --- | --- |\n| 2 | 4 | 8 |"
                ),
            }
        )

    async def generate(self, request, stream=False):
        seen.append(request)
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text='{"answer":"Bảng hiện tại có 3 cột dữ liệu."}')],
            )
        )

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    monkeypatch.setattr(runner.registry, "execute", execute)
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="not-golden-sheet-answer",
        user_message="Bảng Chi phí có bao nhiêu cột dữ liệu?",
        route_override=compiler.Route("drive_read_file", {"file_id": "sheet-id"}),
    )

    assert len(seen) == 1
    assert "| 2 | 4 | 8 |" in str(seen[0].contents)
    assert result.answer.startswith("Bảng hiện tại có 3 cột dữ liệu.")
    assert not any(event.get("kind") == "spreadsheet_facts" for event in result.trace)


async def test_compiler_falls_back_from_provider_503_without_replaying_source_tools(
    runtime, monkeypatch
):
    from google.genai.errors import ServerError

    requests = []

    async def generate(self, request, stream=False):
        requests.append(self.model)
        if self.model == "gemini-3.8-flash":
            raise ServerError(503, {"error": {"message": "temporarily overloaded"}})
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text='{"answer":"Đã tổng hợp đầy đủ từ nguồn."}')],
            )
        )

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="compiler-provider-fallback",
        user_message="Tóm tắt nội dung đã cung cấp.",
        model_name="gemini-3.8-flash",
    )

    assert requests == ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
    assert result.answer == "Đã tổng hợp đầy đủ từ nguồn."
    model_record = result.trace[-1]
    assert model_record["stage"] == "model"
    assert model_record["status"] == "fallback"
    assert model_record["requested_model"] == "gemini-3.8-flash"
    assert model_record["actual_model"] == "gemini-3.5-flash-lite"
    assert model_record["provider_code"] == 503
    assert model_record["model_call_count"] == 2


async def test_latest_gmail_summary_fetches_and_synthesizes_the_full_thread(runtime, monkeypatch):
    seen = []
    calls = []

    async def generate(self, request, stream=False):
        seen.append(request)
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text='{"answer":"Đây là nội dung email đã đọc."}')],
            )
        )

    async def execute(name, arguments, _context):
        calls.append((name, arguments))
        if name == "gmail_list_messages":
            return GmailListOutput(
                messages=[
                    EmailHeaderSummary(
                        id="message-1",
                        thread_id="thread-123456",
                        sender="author@example.com",
                        subject="Inngest vs Temporal",
                        date="Mon, 21 Sep 2026 10:00:00 +0000",
                        snippet="Newsletter preview only",
                    )
                ],
                total_found=1,
            )
        assert name == "gmail_read_thread"
        return GmailReadThreadOutput(
            thread_id="thread-123456",
            subject="Inngest vs Temporal",
            messages=[
                ThreadMessage(
                    id="message-1",
                    sender="author@example.com",
                    recipient="reader@example.com",
                    date="Mon, 21 Sep 2026 10:00:00 +0000",
                    subject="Inngest vs Temporal",
                    body=(
                        "FULL_THREAD_BODY: durable execution retains completed steps "
                        "after a crash."
                    ),
                    presentation_mode="faithful_text",
                    reply_to="author@example.com",
                    message_id_header="<message-1@example.com>",
                )
            ],
        )

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    monkeypatch.setattr(runner.registry, "execute", execute)

    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="gmail-latest-full-read",
        user_message="Đọc hiểu và tóm tắt nội dung email gần nhất, tóm gọn bằng 3 ý",
    )

    assert calls == [
        ("gmail_list_messages", {"query": "in:inbox", "max_results": 1}),
        ("gmail_read_thread", {"thread_id": "thread-123456"}),
    ]
    assert len(seen) == 1
    assert "FULL_THREAD_BODY" in str(seen[0].contents)
    assert result.answer.startswith("Đây là nội dung email đã đọc.")
    assert result.citations[0]["web_view_link"].endswith("#all/thread-123456")


async def test_five_recent_mail_summary_passes_five_full_bodies_and_citations(runtime, monkeypatch):
    calls = []
    prompts = []

    async def generate(self, request, stream=False):
        prompts.append(request)
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text='{"answer":"Đã tổng hợp đủ năm thư [1, 2, 3, 4, 5]."}')],
            )
        )

    async def execute(name, arguments, _context):
        calls.append((name, arguments))
        assert name == "gmail_read_matching_messages"
        return SimpleNamespace(
            model_dump=lambda **_: {
                "messages": [
                    {
                        "id": f"message-{index}",
                        "thread_id": f"thread-{index}abcde",
                        "subject": f"Mail {index}",
                        "body": f"FULL_BODY_{index}",
                        "received_at_local": f"2026-09-29T0{index}:00:00+07:00",
                    }
                    for index in range(1, 6)
                ],
                "examined_count": 5,
                "next_page_token": None,
            }
        )

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    monkeypatch.setattr(runner.registry, "execute", execute)
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="gmail-five-full-bodies",
        user_message="tóm tắt 5 mail gần nhất trong gmail của tôi",
    )

    assert calls == [
        ("gmail_read_matching_messages", {"query": "in:inbox", "max_results": 5})
    ]
    assert len(prompts) == 1
    for index in range(1, 6):
        assert f"FULL_BODY_{index}" in str(prompts[0].contents)
    assert len(result.citations) == 5


async def test_today_mail_summary_discloses_unread_next_page(runtime, monkeypatch):
    async def generate(self, request, stream=False):
        yield LlmResponse(
            content=types.Content(
                role="model", parts=[types.Part(text='{"answer":"Một thư [1]."}')]
            )
        )

    async def execute(name, arguments, _context):
        assert name == "gmail_read_matching_messages"
        assert arguments["day_scope"] == "today"
        return SimpleNamespace(model_dump=lambda **_: {
            "messages": [{
                "id": "message-one", "thread_id": "thread-one", "subject": "Today",
                "body": "FULL_BODY", "received_at_local": "2026-09-29T08:00:00+07:00",
            }],
            "next_page_token": "unread-page",
            "unreadable_body_count": 0,
        })

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    monkeypatch.setattr(runner.registry, "execute", execute)
    result = await runner.run(
        user=user, session_id=session_id, request_id="gmail-today-pagination",
        user_message="tóm tắt các mail của Bảo Phúc Đinh trong ngày hôm nay",
    )

    assert "còn trang kết quả chưa duyệt" in result.answer
    assert len(result.citations) == 1


async def test_today_mail_summary_does_not_claim_empty_if_pages_remain(runtime, monkeypatch):
    async def execute(name, arguments, _context):
        assert name == "gmail_read_matching_messages"
        assert arguments["day_scope"] == "today"
        return SimpleNamespace(model_dump=lambda **_: {
            "messages": [],
            "examined_count": 100,
            "next_page_token": "remaining-page",
        })

    runner, user, session_id = runtime
    monkeypatch.setattr(runner.registry, "execute", execute)
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="gmail-incomplete-empty-page",
        user_message="tóm tắt các mail của Đinh Bảo Phúc trong ngày hôm nay",
    )

    assert "100 thư đã kiểm tra" in result.answer
    assert "chưa thể kết luận" in result.answer
    assert result.trace[-1]["status"] == "incomplete"


async def test_cross_source_compare_reads_both_gmail_and_drive_before_synthesis(
    runtime, monkeypatch
):
    calls = []
    prompts = []

    class ToolResult:
        def __init__(self, data):
            self.data = data

        def model_dump(self, mode="json"):
            return self.data

    async def execute(name, arguments, _context):
        calls.append((name, arguments))
        if name == "gmail_list_messages":
            return ToolResult({"messages": [{"thread_id": "thread-123456"}]})
        if name == "gmail_read_thread":
            return ToolResult(
                {"thread_id": "thread-123456", "subject": "Latest message", "body": "MAIL_EVIDENCE"}
            )
        if name == "drive_list_files":
            return ToolResult({"files": [{"id": "drive-file-123456", "name": "report.pdf"}]})
        assert name == "drive_read_file"
        return ToolResult(
            {
                "file": {
                    "id": "drive-file-123456",
                    "name": "report.pdf",
                    "mime_type": "application/pdf",
                    "web_view_link": "https://drive.google.com/file/d/drive-file-123456/view",
                },
                "text": "DRIVE_EVIDENCE",
            }
        )

    async def generate(self, request, stream=False):
        prompts.append(request)
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text='{"answer":"Đã đối chiếu hai nguồn."}')],
            )
        )

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    monkeypatch.setattr(runner.registry, "execute", execute)
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="cross-source-compare",
        user_message="So sánh email gần nhất với tài liệu mới nhất trong Drive.",
    )

    assert [name for name, _ in calls] == [
        "gmail_list_messages",
        "gmail_read_thread",
        "drive_list_files",
        "drive_read_file",
    ]
    assert "MAIL_EVIDENCE" in str(prompts[0].contents)
    assert "DRIVE_EVIDENCE" in str(prompts[0].contents)
    assert "Đã đối chiếu hai nguồn." in result.answer
    assert "## So sánh" in result.answer


async def test_cross_source_compare_stops_if_drive_source_is_ambiguous(runtime, monkeypatch):
    calls = []

    class ToolResult:
        def model_dump(self, mode="json"):
            return {"files": [{"id": "one", "name": "notes"}, {"id": "two", "name": "notes"}]}

    async def execute(name, _arguments, _context):
        calls.append(name)
        if name == "gmail_list_messages":
            return SimpleNamespace(
                model_dump=lambda **_: {"messages": [{"thread_id": "thread-123456"}]}
            )
        if name == "gmail_read_thread":
            return SimpleNamespace(
                model_dump=lambda **_: {"thread_id": "thread-123456", "body": "MAIL"}
            )
        return ToolResult()

    runner, user, session_id = runtime
    monkeypatch.setattr(runner.registry, "execute", execute)
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="cross-source-ambiguous",
        user_message="Đối chiếu email gần nhất với file notes trong Drive.",
    )

    assert "chưa thể đối chiếu" in result.answer
    assert "drive_read_file" not in calls
    assert "gmail_read_thread" in calls


def test_sheet_facts_calculate_row_two_and_detect_empty_or_negative_cells():
    table = """
    ## Chi phí
    | Cột 1 | Cột 2 | Cột 3 |
    | --- | --- | --- |
    | 1 | 2 | 3 |
    """

    facts = compiler._sheet_facts(table, "Trung bình hàng 2 trong bảng Chi phí là bao nhiêu?")
    assert facts["row_2_values"] == ["1", "2", "3"]
    assert facts["row_2_mean"] == "2"
    checks = compiler._sheet_facts(
        table, "Bảng Chi phí có số âm hoặc ô rỗng trong hàng dữ liệu không?"
    )
    assert checks["has_negative"] is False
    assert checks["has_blank"] is False
    assert checks["column_count"] == 3
    assert checks["first_data_row"] == ["1", "2", "3"]
    assert checks["row_2_sum"] == "6"
    assert compiler._sheet_facts(table, "Công thức tính tổng hàng 2 là gì?")[
        "sum_formula"
    ] == "=SUM(A2:C2)"
    tens = table.replace("| 1 | 2 | 3 |", "| 10 | 10 | 10 |")
    assert compiler._sheet_facts(tens, "Trung bình hàng 2 là bao nhiêu?")[
        "row_2_mean"
    ] == "10"


def test_sheet_facts_do_not_misclassify_evaluation_harness_markdown_tables():
    source = """
    # Evaluation Harness
    | Cột 1 | Cột 2 | Cột 3 |
    | --- | --- | --- |
    | 1 | 2 | 3 |
    """
    assert compiler._sheet_facts(source, "Evaluation Harness dùng để làm gì?") == {}
    assert compiler._sheet_facts(source, "Trong bảng tính, tính trung bình hàng 2.")


def test_local_fact_answer_is_phrase_gated_and_structured():
    source = (
        "Mã kiểm thử: LOCAL-STUDY-2026.\n"
        "Kế hoạch ôn tập gồm ba buổi, mỗi buổi 45 phút.\n"
        "Tổng thời gian theo kế hoạch là 135 phút."
    )
    answer = compiler._local_fact_answer(
        "Hãy liệt kê mã kiểm thử và tổng thời gian trong fixture.", source
    )
    assert answer is not None
    assert "LOCAL-STUDY-2026" in answer
    assert "135 phút" in answer
    assert compiler._local_fact_answer("Mã kiểm thử là gì?", "văn bản khác") is None


def test_local_calculation_uses_only_numbers_found_in_retrieved_source(monkeypatch):
    source = "Kế hoạch ôn tập gồm ba buổi, mỗi buổi 45 phút."
    assert (
        compiler._local_calculation_expression(
            "Tính lại ba buổi nhân 45 phút và đối chiếu với fixture.", source
        )
        == "3*45"
    )
    assert (
        compiler._local_calculation_expression("Tính một con số bất kỳ", "không có dữ liệu") is None
    )
    assert compiler._local_calculation_expression("Tính lại kế hoạch", "Mỗi buổi 45 phút") is None
    assert compiler._local_calculation_expression(
        "Tính lại kế hoạch", "Kế hoạch gồm lạ buổi, mỗi buổi 45 phút"
    ) is None
    assert compiler._local_calculation_expression(
        "Tính lại kế hoạch", "Kế hoạch gồm ba buổi nhưng chưa có thời lượng"
    ) is None
    assert compiler._local_calculation_expression("Hãy nêu lịch", source) is None
    monkeypatch.setattr(compiler, "_number_token", lambda value: None)
    assert compiler._local_calculation_expression("Tính lại kế hoạch", source) is None
    fixture = (
        "Mã kiểm thử: LOCAL-STUDY-2026.\n"
        "Kế hoạch ôn tập gồm ba buổi, mỗi buổi 45 phút.\n"
        "Tổng thời gian theo kế hoạch là 135 phút."
    )
    assert compiler._local_fact_answer("drive_file_metadata", fixture) is not None
    assert compiler._local_fact_answer("Câu hỏi khác", fixture) is None
    assert compiler._local_fact_answer("Mã kiểm thử là gì?", "Mã kiểm thử:") is None


@pytest.mark.parametrize(
    ("count", "minutes", "source_total", "verdict"),
    [("3", "45", "135", "khớp"), ("4", "30", "121", "không khớp")],
)
async def test_local_calculation_does_not_invent_fixture_values(
    runtime, monkeypatch, count, minutes, source_total, verdict
):
    runner, user, session_id = runtime
    real_execute = runner.registry.execute
    source_text = (
        f"Kế hoạch gồm {count} buổi, mỗi buổi {minutes} phút. "
        f"Tổng thời gian ghi trong nguồn là {source_total} phút."
    )

    async def execute(name, arguments, context):
        if name == "local_source_search":
            return SimpleNamespace(
                model_dump=lambda **_: {
                    "data": {"sources": [{"id": "plan-id", "name": "plan.md"}]}
                }
            )
        if name == "local_source_read":
            return SimpleNamespace(model_dump=lambda **_: {"data": {"text": source_text}})
        return await real_execute(name, arguments, context)

    async def forbidden(*args, **kwargs):
        raise AssertionError("Verified arithmetic should not require a model call")
        yield

    monkeypatch.setattr(runner.registry, "execute", execute)
    monkeypatch.setattr(Gemini, "generate_content_async", forbidden)
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id=f"local-calculation-{count}",
        user_message="Trong tệp local plan.md, tính lại tổng thời gian và đối chiếu với nguồn.",
    )

    assert f"{count} buổi" in result.answer
    assert f"{minutes} phút" in result.answer
    assert f"{source_total} phút" in result.answer
    assert f"**{verdict}**" in result.answer


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Mã kiểm thử trong fixture local là gì?", "LOCAL-STUDY-2026"),
        ("Kế hoạch ôn tập gồm mấy buổi?", "3 buổi"),
        ("Mỗi buổi học kéo dài bao lâu?", "45 phút"),
        ("Tổng thời gian của kế hoạch local là bao nhiêu?", "135 phút"),
        ("Tóm tắt fixture local.", "Tóm tắt fixture"),
        ("Đối chiếu kế hoạch.", "khớp"),
    ],
)
def test_local_fact_answer_contracts_cover_fixture_questions(
    question: str, expected: str
) -> None:
    source = (
        "Mã kiểm thử: LOCAL-STUDY-2026.\n"
        "Kế hoạch ôn tập gồm ba buổi, mỗi buổi 45 phút.\n"
        "Tổng thời gian theo kế hoạch là 135 phút."
    )
    answer = compiler._local_fact_answer(question, source)
    assert answer is not None
    assert expected in answer


async def test_direct_calculation_has_zero_model_calls(runtime, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Direct route must not use Gemini")
        yield  # Makes this the same async-generator interface as the SDK.

    monkeypatch.setattr(Gemini, "generate_content_async", forbidden)
    runner, user, session_id = runtime
    result = await runner.run(
        user=user, session_id=session_id, request_id="direct", user_message="Tính 0.1 + 0.2"
    )
    assert "`0.1 + 0.2 = 0.3`" in result.answer
    assert not any(item.get("stage") == "model" for item in result.trace)


async def test_gmail_source_clarification_does_not_call_model_and_reports_correct_source(
    runtime, monkeypatch
):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Source clarification must not use Gemini")
        yield

    monkeypatch.setattr(Gemini, "generate_content_async", forbidden)
    runner, user, session_id = runtime
    route = Route(
        direct=True,
        clarification="Bạn muốn đào sâu email nào?",
        required_sources=("gmail",),
    )

    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="gmail-source-clarification",
        user_message="đào sâu nội dung đó",
        route_override=route,
    )

    assert result.answer == "Bạn muốn đào sâu email nào?"
    assert result.trace[-1] == {
        "stage": "source_selection",
        "status": "needs_clarification",
        "required_sources": ["gmail"],
    }
    assert not any(item.get("stage") == "model" for item in result.trace)


async def test_direct_calculation_includes_requested_reverse_check(runtime, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Direct route must not use Gemini")
        yield

    monkeypatch.setattr(Gemini, "generate_content_async", forbidden)
    runner, user, session_id = runtime

    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="direct-reverse",
        user_message=(
            "Dùng calculate tính (125.5 + 24.5) / 3. "
            "Trả lời kết quả và phép kiểm tra ngược ngắn gọn."
        ),
    )

    assert "`(125.5 + 24.5) / 3 = 50.0`" in result.answer
    assert "`50.0 × 3 = 150.0`" in result.answer
    assert len(result.trace) == 1


async def test_reverse_check_never_divides_by_zero(runtime, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Direct route must not use Gemini")
        yield

    monkeypatch.setattr(Gemini, "generate_content_async", forbidden)
    runner, user, session_id = runtime

    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="direct-zero-reverse",
        user_message="Dùng calculate tính 7 * 0 và kiểm tra ngược.",
    )

    assert "`7 × 0 = 0`" in result.answer
    assert "chia cho `0` không xác định" in result.answer
    assert "0 ÷ 0" not in result.answer


async def test_direct_calculation_includes_requested_next_step(runtime, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Direct route must not use Gemini")
        yield

    monkeypatch.setattr(Gemini, "generate_content_async", forbidden)
    runner, user, session_id = runtime

    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="direct-next-step",
        user_message=(
            "Dùng calculate tính 144 chia 12. Trình bày kết quả, "
            "phép kiểm tra ngược và bước tiếp theo ngắn gọn."
        ),
    )

    assert "`144 / 12 = 12`" in result.answer
    assert "### Kiểm tra ngược" in result.answer
    assert "### Bước tiếp theo" in result.answer
    assert "Dùng `12` làm đầu vào" in result.answer
    assert len(result.trace) == 1


async def test_requested_model_must_be_in_approved_contract(runtime):
    runner, user, session_id = runtime
    with pytest.raises(ToolError, match="Model không nằm trong danh sách đã duyệt"):
        await runner.run(
            user=user,
            session_id=session_id,
            request_id="invalid-model",
            user_message="Giải thích vì sao cần kiểm tra nguồn.",
            model_name="unapproved-model",
        )


async def test_reviewed_budget_quick_start_is_deterministic(runtime, monkeypatch):
    from app.agent.controls import ChatControls

    async def forbidden(*args, **kwargs):
        raise AssertionError("Reviewed one-click template must not use Gemini")
        yield

    monkeypatch.setattr(Gemini, "generate_content_async", forbidden)
    runner, user, session_id = runtime
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="budget-template",
        user_message="Tạo bản xem trước bảng ngân sách tháng với dữ liệu mẫu.",
        controls=ChatControls(
            source="general",
            agent="workspace",
            output="spreadsheet",
            workflow="budget_tracker",
        ),
    )
    proposal = result.proposals[0]
    assert proposal["kind"] == "spreadsheet"
    assert proposal["spreadsheet"]["theme"] == "finance"
    assert proposal["spreadsheet"]["tabs"][0]["rows"][-1][0] == "Tổng"
    assert result.trace[-1]["route"] == "reviewed_budget_template"
    assert not any(item.get("stage") == "model" for item in result.trace)


async def test_budget_workflow_from_slash_menu_is_deterministic(runtime, monkeypatch):
    """The /budget command must use the reviewed template, not model formulas."""
    from app.agent.controls import ChatControls

    async def forbidden(*args, **kwargs):
        raise AssertionError("/budget must not use Gemini")
        yield

    monkeypatch.setattr(Gemini, "generate_content_async", forbidden)
    runner, user, session_id = runtime
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="budget-slash-template",
        user_message="Theo dõi ngân sách tháng.",
        controls=ChatControls(
            source="general",
            agent="workspace",
            output="spreadsheet",
            workflow="budget_tracker",
        ),
    )
    sheet = result.proposals[0]["spreadsheet"]["tabs"][0]
    assert sheet["rows"][-1][1]["start_row"] == 0
    assert sheet["rows"][-1][1]["end_row"] == 4
    assert sheet["rows"][-1][2]["end_row"] == 4


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


async def test_spreadsheet_compiler_preserves_explicit_vietnamese_table_literals(
    runtime, monkeypatch
):
    """Protect the complete model -> compiler result path, not only the helper."""

    prompt = (
        'Tạo bản xem trước Google Sheets tên "DriveAgent Budget Fidelity QA v3" '
        "với cột Hạng mục, Ngân sách, Thực tế, Chênh lệch. Có hai hàng "
        "Sách 500000 450000 và Đi lại 300000 320000, thêm hàng Tổng bằng công thức. "
        "Chỉ chuẩn bị, không tạo file."
    )
    spec = {
        "title": "DriveAgent Budget Fidelity QA v3",
        "tabs": [
            {
                "title": "Chi phi",
                "headers": ["Hạng mục", "Ngân sách", "Thực tế", "Chêh lệch"],
                "rows": [
                    [
                        "sách",
                        500000,
                        450000,
                        {
                            "operator": "SUBTRACT",
                            "left_column": 1,
                            "right_column": 2,
                            "row": 0,
                        },
                    ],
                    [
                        "Đi lại",
                        300000,
                        320000,
                        {
                            "operator": "SUBTRACT",
                            "left_column": 1,
                            "right_column": 2,
                            "row": 1,
                        },
                    ],
                    [
                        "Tổng",
                        {"function": "SUM", "column": 1, "start_row": 0, "end_row": 2},
                        {"function": "SUM", "column": 2, "start_row": 0, "end_row": 2},
                        {"function": "SUM", "column": 3, "start_row": 0, "end_row": 2},
                    ],
                ],
            }
        ],
    }

    async def generate(self, request, stream=False):
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=json.dumps(
                            {
                                "answer": "Đã chuẩn bị bản xem trước.",
                                "proposals": [
                                    {"kind": "spreadsheet", "spec_json": json.dumps(spec)}
                                ],
                            }
                        )
                    )
                ],
            )
        )

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="spreadsheet-literal-fidelity",
        user_message=prompt,
    )

    sheet = result.proposals[0]["spreadsheet"]["tabs"][0]
    assert sheet["headers"] == ["Hạng mục", "Ngân sách", "Thực tế", "Chênh lệch"]
    assert sheet["rows"][0][0] == "Sách"


async def test_unsourced_spreadsheet_compiler_removes_invented_transactions(
    runtime, monkeypatch
):
    spec = {
        "title": "Chi tiêu 2023",
        "tabs": [
            {
                "title": "Giao dịch",
                "headers": ["Ngày", "Nội dung", "So Tien (VND)"],
                "rows": [["2023-01-01", "Café", 95000]],
            }
        ],
    }

    async def generate(self, request, stream=False):
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=json.dumps(
                            {
                                "answer": "Đã chuẩn bị giao dịch Café 95000.",
                                "proposals": [
                                    {"kind": "spreadsheet", "spec_json": json.dumps(spec)}
                                ],
                            }
                        )
                    )
                ],
            )
        )

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="unsourced-spreadsheet-preview",
        user_message="Tạo bản xem trước Google Sheets theo dõi chi tiêu cá nhân.",
    )
    sheet = result.proposals[0]["spreadsheet"]
    assert sheet["tabs"][0]["rows"][0] == [None, None, None]
    assert sheet["tabs"][0]["rows"][1][2]["function"] == "SUM"
    assert "2023" not in sheet["title"]
    assert "95000" not in result.answer
    assert "| Ngày | Nội dung | So Tien (VND) |\n| --- | --- | --- |" in result.answer
    assert result.answer.count("## Bản xem trước") == 1
    assert "=SUM(C2:C2)" in result.answer


async def test_invalid_output_gets_one_bounded_schema_repair(runtime, monkeypatch):
    calls = []

    async def generate(self, request, stream=False):
        calls.append(1)
        if len(calls) == 2:
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text='{"answer":"Đã sửa đúng cấu trúc."}')],
                )
            )
            return
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text='{"answer":""}')])
        )

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="invalid-repaired",
        user_message="Giải thích khái niệm agent",
    )
    assert result.answer == "Đã sửa đúng cấu trúc."
    assert len(calls) == 2
    assert result.trace[-1]["model_call_count"] == 2
    assert any(event["stage"] == "structured_repair" for event in result.trace)


async def test_invalid_output_schema_repair_uses_pinned_fallback_model(runtime, monkeypatch):
    from google.genai.errors import ServerError

    called_models = []

    async def generate(self, request, stream=False):
        called_models.append(self.model)
        if len(called_models) == 1:
            raise ServerError(503, {"error": {"message": "overloaded"}})
        if len(called_models) == 2:
            yield LlmResponse(
                content=types.Content(role="model", parts=[types.Part(text='{"answer":""}')])
            )
            return
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(text='{"answer":"Đã sửa đúng cấu trúc từ model fallback."}')],
            )
        )

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="repair-uses-pinned-model",
        user_message="Giải thích khái niệm agent",
        model_name="gemini-3.8-flash",
    )
    assert result.answer == "Đã sửa đúng cấu trúc từ model fallback."
    assert called_models == [
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash-lite",
    ]



async def test_invalid_output_still_fails_closed_after_one_repair(runtime, monkeypatch):
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
            request_id="invalid-twice",
            user_message="Giải thích khái niệm agent",
        )
    assert failure.value.code == "invalid_spec"
    assert len(calls) == 2


async def test_final_thought_marked_json_is_still_validated(runtime, monkeypatch):
    """Provider metadata must not discard a structured final payload."""

    async def generate(self, request, stream=False):
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text='{"answer":"Payload vẫn được kiểm tra."}',
                        thought=True,
                    )
                ],
            )
        )

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="thought-json",
        user_message="Giải thích cách kiểm chứng output",
    )
    assert result.answer == "Payload vẫn được kiểm tra."


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
    assert result.answer.startswith("OK")
    assert "Nguồn đã kiểm tra: [1]" in result.answer


async def test_direct_calculation_preserves_requested_reverse_check(runtime):
    runner, user, session_id = runtime

    result = await runner.run(
        user=user,
        session_id=session_id,
        request_id="direct-calculation",
        user_message=(
            "Dùng calculate tính (125.5 + 24.5) / 3. "
            "Trả lời kết quả và phép kiểm tra ngược ngắn gọn."
        ),
    )

    assert "### Kết quả" in result.answer
    assert "(125.5 + 24.5) / 3 = 50.0" in result.answer
    assert "### Kiểm tra ngược" in result.answer
    assert "50.0 × 3 = 150.0" in result.answer
    assert len(result.trace) == 1
