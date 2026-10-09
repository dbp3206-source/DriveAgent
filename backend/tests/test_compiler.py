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


@pytest.mark.parametrize("missing_first, drop_questions", [(False, False), (True, False),
                                                         (False, True)])
@pytest.mark.parametrize("source_selection", [
    "website chính thức https://example.org/company",
    "Dùng https://example.org/company",
    "Sử dụng https://example.org/company",
    "Đọc https://example.org/company",
])
async def test_company_compiler_receives_separate_web_evidence_and_date_contract(
    runtime, monkeypatch, missing_first, drop_questions, source_selection,
):
    from datetime import UTC, datetime

    from app.tools.web_research import WebResearchOutput, WebSource

    runner, user, session_id = runtime
    calls = []
    generations = []

    async def execute(name, arguments, context):
        calls.append(name)
        assert arguments["domain"] == "https://example.org/company"
        assert "An Bình" not in arguments["question"]
        assert context.source == "compiler_gather"
        assert context.metadata == {"defer_web_synthesis": True}
        return WebResearchOutput(
            summary="Dữ kiện doanh nghiệp [S1]. Tiêu đề tin [S2].",
            sources=[
                WebSource(title="Công ty", url="https://example.org/company",
                          evidence_kind="page_text", evidence_excerpt="Dữ kiện doanh nghiệp."),
                WebSource(title="Tiêu đề tin", url="https://news.google.com/articles/new",
                          evidence_kind="headline", evidence_excerpt="Chỉ tiêu đề tin.",
                          published_at=datetime(2026, 10, 5, tzinfo=UTC)),
            ], observed_at=datetime.now(UTC), model="test-boundary",
        )

    async def generate(self, request, stream=False):
        prompt = str(request.contents)
        instruction = str(request.config.system_instruction)
        assert 'headline' in prompt and 'published_at' in prompt and 'event_date' in prompt
        assert "Chỉ tiêu đề tin." in prompt
        assert "không khẳng định ngày sự kiện" in instruction
        assert "chưa gửi thư/tạo tài liệu/đặt lịch" in instruction
        assert "không thay bằng danh sách tin" in instruction
        assert "không cần website xác nhận" in instruction
        assert "không ghép nguồn chỉ có tiêu đề vào cùng câu" in instruction
        assert compiler.WEB_CONSULTATION_INSTRUCTION in instruction
        assert "Quy mô có căn cứ; Tin mới đã xác minh" in instruction
        assert "không thay quy mô bằng xếp hạng thương hiệu" in instruction
        assert "không thay thế tin mới" in instruction
        assert "chưa có ngày giờ" in instruction
        assert "không gắn trích dẫn web cho lời báo thiếu đó" in instruction
        assert "Không tìm thấy không có nghĩa" in instruction
        assert "chỉ dùng nội dung người dùng cung cấp trực tiếp" not in instruction
        schema = request.config.response_json_schema
        assert "clarification_questions" in schema["required"]
        generations.append(prompt)
        if len(generations) == 1:
            assert request.config.max_output_tokens == 4096
            assert request.config.http_options.timeout == 25000
            assert self.fallback_attempt_limit == 1
            assert self.fallback_timeout_ms == 10000
        if missing_first and len(generations) == 1:
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(
                text='{"answer":"Báo cáo chưa đủ câu hỏi [2]."}'
            )]))
            return
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(
            text=json.dumps({
                "answer": "Tin được đăng ngày 05/10; ngày sự kiện chưa xác minh [2].",
                "clarification_questions": [
                    "Công việc nào hiện mất nhiều thời gian?",
                    "Nguồn tài liệu nào cần tìm?",
                    "Kết quả mong muốn được đánh giá bằng cách nào?",
                ],
            })
        )]))

    monkeypatch.setattr(runner.registry, "execute", execute)
    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    async def presentation(**kwargs):
        assert "3. Kết quả mong muốn được đánh giá bằng cách nào?" in kwargs["answer"]
        assert kwargs["required_questions"] == [
            "Công việc nào hiện mất nhiều thời gian?",
            "Nguồn tài liệu nào cần tìm?",
            "Kết quả mong muốn được đánh giá bằng cách nào?",
        ]
        return kwargs["answer"].split("## Câu hỏi cần làm rõ")[0] if drop_questions else kwargs[
            "answer"
        ]

    monkeypatch.setattr(compiler, "enforce_presentation_contract", presentation)
    if drop_questions:
        with pytest.raises(ToolError) as caught:
            await runner.run(
                user=user, session_id=session_id, request_id="company-questions-lost",
                user_message=f"Báo cáo tư vấn. {source_selection}.",
            )
        assert caught.value.code == "incomplete_consultation_report"
        assert calls == ["web_research"] and len(generations) == 1
        return
    result = await runner.run(
        user=user, session_id=session_id, request_id="company-source-contract",
        user_message=(
            f"Dữ liệu giả lập: khách hàng An Bình. Báo cáo tư vấn. {source_selection}. "
            "Không đọc Gmail, Drive, lịch, tài liệu local hoặc bộ nhớ; không ghi dữ liệu."
        ),
    )
    assert calls == ["web_research"]
    assert len(generations) == (2 if missing_first else 1)
    assert len(result.citations) == 1
    assert result.citations[0]["evidence_kind"] == "headline"
    assert result.citations[0]["event_date"] is None
    assert "Chỉ đọc tiêu đề, chưa đọc toàn văn" in result.answer
    assert "Tin được đăng ngày 05/10" not in result.answer
    assert "## Câu hỏi cần làm rõ" in result.answer
    assert "3. Kết quả mong muốn được đánh giá bằng cách nào?" in result.answer


@pytest.mark.parametrize("questions", [None, [], ["Một?", "Hai?"],
    ["Một?", "Hai?", ""], ["Một?", "Một?", "Ba?"],
    ["Một?", "Hai?", "Ba?", "Bốn?"], ["Một?", "Hai?", "x" * 1001],
])
def test_consultation_questions_reject_missing_empty_duplicate_or_wrong_count(questions):
    from pydantic import ValidationError

    from app.agent.creation import separate_consultation_questions

    with pytest.raises(ValidationError):
        separate_consultation_questions(json.dumps({
            "answer": "Báo cáo", "clarification_questions": questions,
        }))


def test_consultation_schema_does_not_change_generic_or_calculation_contract():
    from app.agent.creation import (
        WireAnswer,
        consultation_provider_schema,
        consultation_report_requested,
        separate_consultation_questions,
    )

    base = WireAnswer.provider_schema()
    shaped = consultation_provider_schema(base)
    assert "clarification_questions" not in base["required"]
    assert shaped["properties"]["clarification_questions"]["minItems"] == 3
    assert not consultation_report_requested("Hôm nay có tin mới gì?")
    assert consultation_report_requested("Chuẩn bị hồ sơ tư vấn cho Công ty Mộc An")
    raw, questions = separate_consultation_questions(json.dumps({
        "answer": "Chưa thực thi.", "proposals": [],
        "clarification_questions": ["Một?", "Hai?", "Ba?"],
        "calculations": [{"expression": "24*12*20"}],
    }))
    assert questions == ["Một?", "Hai?", "Ba?"]
    assert json.loads(raw)["calculations"] == [{"expression": "24*12*20"}]


@pytest.mark.parametrize("reset", [
    "Nguồn duy nhất cho lần này là dữ liệu trong lượt hiện tại: nhóm mới có 8 người.",
    "Chỉ dùng nội dung tin nhắn này: nhóm mới có 11 người.",
    "Only use the current message: the new team has 6 people.",
])
def test_evidence_reset_excludes_old_facts_and_survives_followup(reset):
    old = SimpleNamespace(role="assistant", content="Nhóm trước: 24 người, 5760 phút.")
    current = SimpleNamespace(role="user", content=reset)
    new_answer = SimpleNamespace(role="assistant", content="Cần hỏi nhóm mới về nhu cầu.")
    assert compiler.conversation_context([old], reset) == []
    followup = compiler.conversation_context([new_answer, current, old], "Hỏi rõ thêm.")
    assert len(followup) == 2
    assert all("5760" not in item["text"] for item in followup)
    assert compiler.scoped_conversation_history([new_answer, current, old], "Hỏi rõ thêm.") == [
        new_answer, current,
    ]


def test_normal_followup_and_source_selection_keep_short_term_memory():
    old = SimpleNamespace(role="user", content="Nhóm có 24 người.")
    for question in [
        "Hỏi rõ thêm.", "Chỉ dùng web để kiểm tra nhận định trước.",
        "Không chỉ dùng nội dung tin nhắn này; hãy dùng cả trao đổi trước.",
        "Giải thích câu 'Chỉ dùng nội dung tin nhắn này' trong tài liệu.",
    ]:
        assert compiler.conversation_context([old], question) == [
            {"role": "user", "text": old.content},
        ]


def test_local_controls_preserve_all_requested_sources():
    route = Route(sources=(
        Route("local_source_search", {"query": "bank.pdf"}, read_match=True),
        Route("local_source_search", {"query": "power.pdf"}, read_match=True),
    ), required_sources=("local",))
    selected = compiler.CompilerOrchestrator._apply_controls(
        route, "So sánh tài liệu local bank.pdf và power.pdf", ChatControls(source="local")
    )
    assert selected.sources == route.sources


@pytest.mark.parametrize("code", [
    "ungrounded_web_research", "web_research_provider_error", "web_source_dns_error",
    "web_source_transport_error", "official_source_empty", "news_sources_empty",
    "news_feed_invalid",
])
async def test_unverified_public_source_is_reported_without_synthesis(runtime, monkeypatch, code):
    runner, user, session_id = runtime
    calls = []

    async def execute(name, arguments, context):
        calls.append(name)
        raise ToolError("Untrusted provider detail", code=code)

    async def forbidden_model(*args, **kwargs):
        raise AssertionError("No answer may be synthesized without public evidence")

    monkeypatch.setattr(runner.registry, "execute", execute)
    monkeypatch.setattr(Gemini, "generate_content_async", forbidden_model)
    result = await runner.run(
        user=user, session_id=session_id, request_id="unverified-public",
        user_message="Kiểm nguồn cập nhật tại https://example.invalid/schedule",
    )
    assert calls == ["web_research"]
    assert "Chưa xác minh" in result.answer
    assert "Untrusted provider detail" not in result.answer
    assert result.citations == []
    assert result.trace[-2] == {
        "stage": "tool", "tool": "web_research", "status": "error", "error_code": code,
    }
    assert result.trace[-1]["status"] == "unverified"


@pytest.mark.parametrize("code", ["permission_denied", "unsafe_web_source", "quota_exhausted"])
async def test_public_source_authority_and_quota_failures_remain_errors(runtime, monkeypatch, code):
    runner, user, session_id = runtime

    async def execute(*args, **kwargs):
        raise ToolError("blocked", code=code)

    monkeypatch.setattr(runner.registry, "execute", execute)
    with pytest.raises(ToolError) as caught:
        await runner.run(
            user=user, session_id=session_id, request_id="blocked-public",
            user_message="Kiểm nguồn cập nhật tại https://example.invalid/schedule",
        )
    assert caught.value.code == code


async def test_multi_local_retrieval_collects_pages_from_each_file(runtime, monkeypatch):
    runner, user, session_id = runtime
    calls = []
    repair_inputs = []

    async def repair(**kwargs):
        repair_inputs.append(kwargs)
        return kwargs["answer"]

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
    monkeypatch.setattr(compiler, "enforce_presentation_contract", repair)
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
    assert len(repair_inputs) == 1
    repair_input = repair_inputs[0]
    evidence = repair_input["source_evidence_untrusted"]["sources"]
    assert len(evidence) == 2
    assert [item["data"]["data"]["citations"][0]["file_id"] for item in evidence] == [
        "local:bank.pdf", "local:power.pdf",
    ]
    assert repair_input["source_references_untrusted"] == [
        {"reference": index, **citation}
        for index, citation in enumerate(result.citations, 1)
    ]


@pytest.mark.parametrize("invalid_first", [False, True])
async def test_source_arithmetic_reaches_presentation_in_both_compiler_paths(
    runtime, monkeypatch, invalid_first,
):
    from app.tools.calculator import CalculateInput, calculate

    runner, user, session_id = runtime
    calls = []
    model_calls = []
    questions = ["Thời gian được đo thế nào?", "Chất lượng hiện tại ra sao?",
                 "Đã cho phép xử lý nguồn chưa?"]

    async def execute(name, arguments, context):
        calls.append(name)
        if name == "calculate":
            return calculate(CalculateInput.model_validate(arguments))
        if name == "local_source_search":
            filename = arguments["query"]
            return SimpleNamespace(model_dump=lambda **_: {"data": {"sources": [
                {"id": filename, "name": filename},
            ]}})
        assert name == "local_source_read"
        return SimpleNamespace(model_dump=lambda **_: {"data": {"citations": [{
            "file_id": "local:" + arguments["source_id"], "file_name": arguments["source_id"],
            "chunk_index": 0, "page_number": None,
            "snippet": "Nhóm có 17 người, 9 phút/ngày, 22 ngày/tháng; giảm 20% là giả thuyết.",
            "score": 1.0,
        }]}})

    async def generate(self, request, stream=False):
        model_calls.append(request)
        if invalid_first and len(model_calls) == 1:
            raw = '{"answer":"Thiếu câu hỏi và biểu thức."}'
        else:
            raw = json.dumps({
                "answer": "Nền {{calc:0}}, giảm giả định {{calc:1}}, còn {{calc:2}} phút [1].",
                "expressions": ["17*9*22", "17*9*22*20/100", "17*9*22*(1-20/100)"],
                "clarification_questions": questions,
            })
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=raw)]))

    async def presentation(**kwargs):
        assert kwargs["verified_calculations"]["source_calculations"] == [
            {"expression": "17*9*22", "result": "3366"},
            {"expression": "17*9*22*20/100", "result": "673.2"},
            {"expression": "17*9*22*(1-20/100)", "result": "2692.8"},
        ]
        assert kwargs["required_questions"] == questions
        return kwargs["answer"]

    monkeypatch.setattr(runner.registry, "execute", execute)
    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    monkeypatch.setattr(compiler, "enforce_presentation_contract", presentation)
    result = await runner.run(
        user=user, session_id=session_id, request_id="arithmetic-evidence-transfer",
        user_message="Đọc tài liệu local alpha.md và beta.md; lập báo cáo chuẩn bị tư vấn "
                     "200–240 từ, tính thời gian theo giả thuyết bằng công cụ. Không ghi dữ liệu.",
        controls=ChatControls(source="local"),
    )
    assert calls.count("calculate") == 1
    assert len(model_calls) == (2 if invalid_first else 1)
    assert "3366" in result.answer and "673.2" in result.answer
    assert all(question in result.answer for question in questions)
    assert result.proposals == []


@pytest.mark.parametrize("multiple_sources", [False, True])
async def test_explicit_pdf_page_reads_requested_page_not_relevance_preview(
    runtime, monkeypatch, multiple_sources,
):
    from app.db.models import LocalSource
    from app.services.local_sources import hash_content, local_source_tool_definitions

    runner, user, session_id = runtime
    filenames = ["sector-review.pdf", "company-review.pdf"] if multiple_sources else [
        "sector-review.pdf"
    ]
    content = "<!-- page:1 -->Introduction\n<!-- page:2 -->TARGET_ROW_WITH_COMMENTARY\n"
    content += "<!-- page:11 -->" + "sector-review.pdf company-review.pdf repeated row " * 100
    async with compiler.SessionFactory() as db:
        for index, filename in enumerate(filenames):
            body = content + str(index)
            db.add(LocalSource(user_id=user.id, name=filename, content=body,
                               content_hash=hash_content(body)))
        await db.commit()
    for definition in local_source_tool_definitions():
        runner.registry.register(definition)

    async def generate(self, request, stream=False):
        prompt = str(request.contents)
        assert "TARGET_ROW_WITH_COMMENTARY" in prompt
        assert "repeated row" not in prompt
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(
            text='{"answer":"Nhận định cùng dòng [1]."}'
        )]))

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    result = await runner.run(
        user=user, session_id=session_id, request_id="explicit-page-review",
        user_message=f"Đọc {' và '.join(filenames)}; đối chiếu dòng và nhận định ở trang 2.",
        controls=ChatControls(source="local"),
    )
    assert result.citations
    assert all(citation["page_number"] == 2 for citation in result.citations)


async def test_exact_pdf_pages_follow_pagination_and_fail_closed_on_missing_page(
    runtime,
):
    from app.db.models import LocalSource
    from app.services.local_sources import hash_content, local_source_tool_definitions
    from app.tools.contracts import ToolContext

    runner, user, _ = runtime
    content = "<!-- page:2 -->" + "x" * 12000 + "TAIL_COMMENTARY"
    content += "<!-- page:3 -->SECOND_PAGE\n<!-- page:11 -->IRRELEVANT"
    async with compiler.SessionFactory() as db:
        source = LocalSource(user_id=user.id, name="report.pdf", content=content,
                             content_hash=hash_content(content))
        db.add(source)
        await db.commit()
        for definition in local_source_tool_definitions():
            runner.registry.register(definition)
        context = ToolContext(request_id="exact-pages", user=user, db=db,
                              settings=runner.settings, source="compiler_gather")
        source_ref = {"id": source.id, "name": source.name}
        result = await runner._read_local_evidence(
            source_ref, "Read pages 2-3", context,
        )
        assert "TAIL_COMMENTARY" in result["data"]["text"]
        assert "SECOND_PAGE" in result["data"]["text"]
        assert "IRRELEVANT" not in result["data"]["text"]
        assert [item["page_number"] for item in result["data"]["citations"]] == [2, 2, 3]
        with pytest.raises(ToolError) as error:
            await runner._read_local_evidence(
                source_ref, "Read page 4", context,
            )
        assert error.value.code == "source_page_not_found"
        with pytest.raises(ToolError) as error:
            await runner._read_local_evidence(
                source_ref,
                "Đọc a.pdf trang 2 và b.pdf trang 5.", context,
            )
        assert error.value.code == "source_page_scope_ambiguous"


async def test_adk_model_page_cannot_override_current_request(runtime, monkeypatch):
    import asyncio

    from app.agent import adk_orchestrator
    from app.db.models import LocalSource
    from app.services.local_sources import hash_content, local_source_tool_definitions

    runner, user, _ = runtime
    monkeypatch.setattr(adk_orchestrator, "SessionFactory", compiler.SessionFactory)
    body = "<!-- page:2 -->CURRENT_PAGE\n<!-- page:11 -->STALE_PAGE"
    async with compiler.SessionFactory() as db:
        source = LocalSource(user_id=user.id, name="report.pdf", content=body,
                             content_hash=hash_content(body))
        db.add(source)
        await db.commit()
    definitions = local_source_tool_definitions()
    for definition in definitions:
        runner.registry.register(definition)
    tool = adk_orchestrator.GovernedAdkTool(
        definitions[1], runner.registry, runner.settings, user.id, "adk-pages", [], [],
        asyncio.Semaphore(2), set(), {}, user_message="Đọc trang 2; không đọc trang 11.",
        local_reader=runner._read_local_evidence,
    )
    result = await tool.run_async(
        args={"source_id": source.id, "page_number": 11, "query": "STALE_PAGE"},
        tool_context=None,
    )
    assert "CURRENT_PAGE" in result["data"]["text"]
    assert "STALE_PAGE" not in result["data"]["text"]
    assert all(item["page_number"] == 2 for item in result["data"]["citations"])
    cached = await tool.run_async(
        args={"source_id": source.id, "page_number": 3, "query": "another stale guess"},
        tool_context=None,
    )
    assert cached is result
    assert tool.records[-1]["stage"] == "tool_cache"
    missing = await tool.run_async(args={"source_id": "foreign-source"}, tool_context=None)
    assert missing["code"] == "source_not_found"


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
@pytest.mark.parametrize("message", [
    "Chỉ dùng ngữ cảnh; không đọc thêm nguồn.",
    "Chỉ dùng nội dung và nguồn đã đọc trong cuộc trò chuyện này, không đọc lại tệp.",
])
async def test_context_only_compiler_preserves_exact_source_mapping(
    runtime, monkeypatch, cited, message
):
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
                              user_message=message,
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


@pytest.mark.parametrize("table, answer, expected", [
    (
        "Hàng | Giá trị\nX | 12\nY | 8\nMô tả riêng: X đạt 12 nghìn đồng.",
        "X: 12 nghìn đồng [1]; Y: 8, chưa xác định đơn vị [1]. "
        "Tổng các số: {{calc:0}}; chưa thể xác nhận tổng cùng đơn vị.",
        "Tổng các số: 20; chưa thể xác nhận tổng cùng đơn vị.",
    ),
    (
        "Bảng: đơn vị giờ\nHàng | Giá trị\nX | 12\nY | 8",
        "Tổng {{calc:0}} giờ [1].",
        "Tổng 20 giờ.",
    ),
    (
        "Báo cáo ngày 14/03/2025. Dự báo năm 2026, đơn vị tấn: X=12; Y=8.",
        "Theo báo cáo ngày 14/03/2025, tổng dự báo năm 2026: {{calc:0}} tấn [1].",
        "tổng dự báo năm 2026: 20 tấn.",
    ),
    (
        "Trong nhóm doanh nghiệp được khảo sát có X=12 và Y=8; đơn vị triệu đồng.",
        "Tổng của nhóm doanh nghiệp được khảo sát: {{calc:0}} triệu đồng [1].",
        "Tổng của nhóm doanh nghiệp được khảo sát: 20 triệu đồng.",
    ),
])
async def test_source_metadata_contract_reaches_calculation_provider(
    runtime, monkeypatch, table, answer, expected,
):
    """Offline contract test, not a claim that a live model obeys semantic rules."""
    from app.tools.calculator import CalculateInput, calculate

    runner, user, session_id = runtime
    source = {"file_id": "local:units", "file_name": "units.md", "chunk_index": 0,
              "snippet": table, "score": 1.0}
    async with compiler.SessionFactory() as db:
        db.add(Message(user_id=user.id, session_id=session_id, role="assistant",
                       content="Đã đọc bảng [1].", citations_json=json.dumps([source])))
        await db.commit()
    calls = []

    async def generate(self, request, stream=False):
        instruction = str(request.config.system_instruction)
        assert "không tự lan sang hàng khác hay cả bảng" in " ".join(instruction.split())
        assert "chưa thể xác nhận tổng/chênh lệch cùng đơn vị" in instruction
        assert "không biến dự báo thành kết quả thực tế" in " ".join(instruction.split())
        assert "không xác minh đơn vị hay ý nghĩa dữ liệu" in instruction
        assert "Giữ đúng tập mẫu và phạm vi mà nguồn mô tả" in instruction
        assert "không suy rộng thành toàn ngành" in " ".join(instruction.split())
        payload = json.loads(request.contents[-1].parts[0].text)
        assert table in [item["snippet"] for item in payload["source_references"]]
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(
            text=json.dumps({"answer": answer, "expressions": ["12+8"]}, ensure_ascii=False),
        )]))

    async def execute(name, arguments, context):
        assert name == "calculate"
        calls.append(arguments)
        return calculate(CalculateInput.model_validate(arguments))

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    monkeypatch.setattr(runner.registry, "execute", execute)
    result = await runner.run(
        user=user, session_id=session_id, request_id="metadata-calculation",
        user_message="Chỉ dùng ngữ cảnh, tính tổng bằng calculate.", route_override=Route(),
    )
    assert expected in result.answer
    assert calls == [{"operation": "expressions", "values": ["12+8"]}]
    assert {"stage": "tool", "tool": "calculate", "status": "success"} in result.trace


async def test_inline_user_data_executes_calculator_before_returning_answer(runtime, monkeypatch):
    runner, user, session_id = runtime
    calls = []

    async def generate(self, request, stream=False):
        assert "expressions" in request.config.response_json_schema["required"]
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(
            text=json.dumps({
                "answer": "Chênh lệch {{calc:0}} triệu đồng; tăng trưởng {{calc:1}}%.",
                "expressions": ["150-120", "(150-120)/120*100"],
            }, ensure_ascii=False),
        )]))

    async def execute(name, arguments, context):
        from app.tools.calculator import CalculateInput, calculate

        assert name == "calculate"
        calls.append(arguments)
        return calculate(CalculateInput.model_validate(arguments))

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    monkeypatch.setattr(runner.registry, "execute", execute)
    result = await runner.run(
        user=user, session_id=session_id, request_id="inline-calculation",
        user_message=(
            "Dữ liệu giả lập: tháng 1 là 120 triệu đồng, tháng 2 là 150 triệu đồng. "
            "Chỉ dùng dữ liệu này, tính chênh lệch và tăng trưởng bằng công cụ, "
            "không ghi dữ liệu."
        ), route_override=Route(),
    )
    assert result.answer == "Chênh lệch 30 triệu đồng; tăng trưởng 25.00%."
    assert calls == [{"operation": "expressions", "values": [
        "150-120", "(150-120)/120*100",
    ]}]
    assert {"stage": "tool", "tool": "calculate", "status": "success"} in result.trace
    assert result.citations == []
    assert result.proposals == []


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


async def test_combined_brief_reads_bounded_mail_and_calendar_before_one_synthesis(
    runtime, monkeypatch
):
    calls, prompts = [], []

    class ToolResult:
        def __init__(self, data):
            self.data = data

        def model_dump(self, mode="json"):
            return self.data

    async def execute(name, arguments, _context):
        calls.append((name, arguments))
        if name == "gmail_read_matching_messages":
            return ToolResult({"messages": [{
                "id": "mail-123", "thread_id": "thread-123", "subject": "Hồ sơ",
                "body": "MAIL_EVIDENCE", "body_available": True,
            }]})
        assert name == "calendar_list_upcoming"
        return ToolResult({"events": [{
            "id": "event-123", "title": "CALENDAR_EVIDENCE",
            "start": "2026-10-06T18:00:00+07:00", "end": "2026-10-06T19:00:00+07:00",
            "all_day": False, "html_link": "https://calendar.google.com/calendar/event?eid=123",
        }]})

    async def generate(self, request, stream=False):
        prompts.append(request)
        yield LlmResponse(content=types.Content(
            role="model", parts=[types.Part(text='{"answer":"Thư [1] và cuộc hẹn [2]."}')]
        ))

    monkeypatch.setattr(Gemini, "generate_content_async", generate)
    runner, user, session_id = runtime
    monkeypatch.setattr(runner.registry, "execute", execute)
    result = await runner.run(
        user=user, session_id=session_id, request_id="bounded-inbox-calendar",
        user_message="Đọc 5 thư Gmail và lịch 24 giờ tới. Không mở Drive, local hoặc web.",
    )
    assert calls == [
        ("gmail_read_matching_messages", {"query": "in:inbox", "max_results": 5}),
        ("calendar_list_upcoming", {"days": 1, "max_results": 20}),
    ]
    assert len(prompts) == 1
    assert "MAIL_EVIDENCE" in str(prompts[0].contents)
    assert "CALENDAR_EVIDENCE" in str(prompts[0].contents)
    assert [citation["file_id"] for citation in result.citations] == [
        "mail-123", "calendar:event-123"
    ]


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


@pytest.mark.parametrize("source, message", [
    ("auto", "Đọc cả hai tài liệu local và tổng hợp báo cáo."),
    ("local", "Đọc cả hai tài liệu local và tổng hợp báo cáo."),
    ("local", "Đọc cả ba tài liệu và tổng hợp báo cáo."),
])
async def test_ambiguous_multi_local_read_has_no_tool_or_model_calls(
    runtime, monkeypatch, source, message
):
    async def forbidden_model(*args, **kwargs):
        raise AssertionError("Ambiguous source selection must not call Gemini")
        yield

    async def forbidden_tool(*args, **kwargs):
        raise AssertionError("Ambiguous source selection must not read a ranked source")

    monkeypatch.setattr(Gemini, "generate_content_async", forbidden_model)
    runner, user, session_id = runtime
    monkeypatch.setattr(runner.registry, "execute", forbidden_tool)
    result = await runner.run(
        user=user, session_id=session_id, request_id="ambiguous-multi-local",
        user_message=message,
        controls=ChatControls(source=source),
    )
    assert "tên" in result.answer
    assert result.trace[-1]["status"] == "needs_clarification"
    assert result.trace[-1]["required_sources"] == ["local"]
    assert not result.citations
    assert not any(item.get("stage") in {"model", "tool"} for item in result.trace)


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
