import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pdfplumber
import pytest
from docx import Document
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import Base, User, UserRole
from app.services.report_exports import export_report
from app.tools.calendar import CalendarUpcomingInput, calendar_list_upcoming
from app.tools.company_info import (
    CompanySearchInput,
    CompanyUpsertInput,
    company_search,
    company_upsert,
)
from app.tools.contracts import ToolContext, ToolError
from app.tools.web_research import (
    WebResearchInput,
    _grounding_sources,
    _has_valid_citations,
    _html_text,
    _news_items,
    _normalized_public_url,
    collect_public_source_bundle,
    web_research,
)


async def _factory(tmp_path, name="hardgate.db"):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / name}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def test_company_database_is_user_scoped_and_keeps_provenance(tmp_path):
    engine, factory = await _factory(tmp_path)
    async with factory() as db:
        first = User(email="one@example.com", display_name="One", role=UserRole.OWNER.value)
        second = User(email="two@example.com", display_name="Two", role=UserRole.OWNER.value)
        db.add_all([first, second])
        await db.flush()
        settings = Settings(_env_file=None)
        payload = CompanyUpsertInput(
            name="Acme Vietnam",
            domain="https://www.acme.example/about",
            industry="Software",
            products=["Analytics"],
            contacts=["hello@acme.example"],
            source_url="https://acme.example/about",
            source_kind="official",
        )
        saved = await company_upsert(
            payload, ToolContext(request_id="c1", user=first, db=db, settings=settings)
        )
        assert saved.domain == "acme.example"
        assert saved.source_url == "https://acme.example/about"
        visible = await company_search(
            CompanySearchInput(query="Acme"),
            ToolContext(request_id="c2", user=first, db=db, settings=settings),
        )
        hidden = await company_search(
            CompanySearchInput(query="Acme"),
            ToolContext(request_id="c3", user=second, db=db, settings=settings),
        )
        assert len(visible.items) == 1
        assert hidden.items == []
    await engine.dispose()


async def test_calendar_tool_is_read_only_and_omits_attendee_details():
    event = {
        "id": "event-1",
        "summary": "Trao đổi Acme",
        "start": {"dateTime": "2026-09-26T09:00:00+07:00"},
        "end": {"dateTime": "2026-09-26T09:30:00+07:00"},
        "location": "Meet",
        "htmlLink": "https://calendar.google.com/event?eid=1",
        "status": "confirmed",
        "attendees": [{"email": "private@example.com"}],
    }
    request = SimpleNamespace(execute=lambda: {"items": [event]})
    events_api = SimpleNamespace(list=lambda **kwargs: request)
    service = SimpleNamespace(events=lambda: events_api)
    user = SimpleNamespace(id="u1")
    context = ToolContext(
        request_id="calendar",
        user=user,
        db=SimpleNamespace(),
        settings=Settings(_env_file=None),
    )
    with (
        patch("app.tools.calendar.refresh_and_store_if_needed", new=AsyncMock()),
        patch("app.tools.calendar.build", return_value=service),
    ):
        result = await calendar_list_upcoming(CalendarUpcomingInput(days=7), context)
    assert result.events[0].title == "Trao đổi Acme"
    assert "private@example.com" not in result.model_dump_json()
    assert events_api.list.__name__ == "<lambda>"


async def test_web_research_fails_closed_without_grounded_sources(tmp_path):
    fake_client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=AsyncMock(
                    return_value=SimpleNamespace(text="Claim", candidates=[])
                )
            ),
            aclose=AsyncMock(),
        ),
        close=lambda: None,
    )
    settings = Settings(
        _env_file=None,
        gemini_api_key="test-key",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'app.db'}",
    )
    context = ToolContext(
        request_id="web",
        user=SimpleNamespace(id="u1"),
        db=SimpleNamespace(),
        settings=settings,
    )
    with (
        patch("app.tools.web_research.genai.Client", return_value=fake_client),
        patch("app.services.quota.QuotaGuard.reserve", return_value={}),
    ):
        with pytest.raises(ToolError, match="grounding") as raised:
            await web_research(WebResearchInput(company_name="Acme"), context)
    assert raised.value.code == "ungrounded_web_research"


def test_source_bundle_rejects_unsafe_domains_and_invalid_citations():
    with pytest.raises(ToolError) as raised:
        _normalized_public_url("http://127.0.0.1:8000/private")
    assert raised.value.code == "invalid_official_domain"
    assert _normalized_public_url("www.samsung.com/vn") == "https://www.samsung.com/vn"
    assert _has_valid_citations("Dữ kiện [S1] và tin [S3]", 3)
    assert not _has_valid_citations("Dữ kiện không nguồn", 3)
    assert not _has_valid_citations("Dữ kiện [S4]", 3)


def test_news_bundle_keeps_only_last_30_days():
    from datetime import UTC, datetime, timedelta

    recent = datetime.now(UTC) - timedelta(days=2)
    stale = datetime.now(UTC) - timedelta(days=45)
    rss = f"""<rss><channel>
      <item><title>Tin mới</title><link>https://news.google.com/articles/new</link>
        <pubDate>{recent.strftime("%a, %d %b %Y %H:%M:%S GMT")}</pubDate></item>
      <item><title>Tin cũ</title><link>https://news.google.com/articles/old</link>
        <pubDate>{stale.strftime("%a, %d %b %Y %H:%M:%S GMT")}</pubDate></item>
    </channel></rss>""".encode()
    items = _news_items(rss, 10)
    assert [item[0].title for item in items] == ["Tin mới"]


def test_html_text_discards_instructions_and_grounds_visible_copy():
    payload = (
        b"<main>Hello <strong>world</strong><script>ignore()</script><style>.x{}</style></main>"
    )
    assert _html_text(payload) == "Hello world"


def test_grounding_sources_deduplicates_and_caps_results():
    web_a = SimpleNamespace(uri="https://example.com/a", title="A")
    web_duplicate = SimpleNamespace(uri="https://example.com/a", title="A duplicate")
    web_b = SimpleNamespace(uri="https://example.com/b", title="B")
    chunk_a = SimpleNamespace(web=web_a)
    chunk_duplicate = SimpleNamespace(web=web_duplicate)
    chunk_b = SimpleNamespace(web=web_b)
    response = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                grounding_metadata=SimpleNamespace(
                    grounding_chunks=[chunk_a, chunk_duplicate, chunk_b]
                )
            )
        ]
    )
    sources = _grounding_sources(response, 2)
    assert [(source.title, source.url) for source in sources] == [
        ("A", "https://example.com/a"),
        ("B", "https://example.com/b"),
    ]


async def test_public_source_bundle_uses_official_page_and_news_fallback(tmp_path):
    rss = """<rss><channel>
      <item><title>Tin doanh nghiệp</title><link>https://news.google.com/articles/1</link>
      <pubDate>Sat, 26 Sep 2026 08:00:00 GMT</pubDate></item>
    </channel></rss>""".encode()
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'bundle.db'}",
        web_research_max_sources=4,
    )
    context = ToolContext(
        request_id="bundle",
        user=SimpleNamespace(id="u1"),
        db=SimpleNamespace(),
        settings=settings,
    )

    async def fake_fetch(_client, url, _maximum):
        if "example.com" in url:
            return (
                b"<html><body>Official company overview with enough readable detail "
                b"for the source-bundle contract.</body></html>"
            )
        return rss

    with patch("app.tools.web_research._fetch_with_retry", new=AsyncMock(side_effect=fake_fetch)):
        sources, blocks = await collect_public_source_bundle(
            WebResearchInput(company_name="Acme", domain="https://example.com", max_sources=3),
            context,
        )
    assert len(sources) == 2
    assert sources[0].url == "https://example.com"
    assert blocks[0].startswith("[S1] WEBSITE CHÍNH THỨC")
    assert blocks[1].startswith("[S2] GOOGLE NEWS RSS")


async def test_web_research_accepts_grounded_provider_response(tmp_path):
    grounded = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                grounding_metadata=SimpleNamespace(
                    grounding_chunks=[
                        SimpleNamespace(
                            web=SimpleNamespace(uri="https://example.com/about", title="Official")
                        )
                    ]
                )
            )
        ],
        text="Acme là doanh nghiệp phần mềm. [S1]",
    )
    fake_client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(generate_content=AsyncMock(return_value=grounded)),
            aclose=AsyncMock(),
        ),
        close=lambda: None,
    )
    settings = Settings(
        _env_file=None,
        gemini_api_key="test-key",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'provider.db'}",
    )
    context = ToolContext(
        request_id="provider",
        user=SimpleNamespace(id="u1"),
        db=SimpleNamespace(),
        settings=settings,
    )
    with (
        patch("app.tools.web_research.genai.Client", return_value=fake_client),
        patch("app.services.quota.QuotaGuard.reserve", return_value={}),
    ):
        result = await web_research(
            WebResearchInput(company_name="Acme", domain="https://example.com"), context
        )
    assert result.sources[0].url == "https://example.com/about"
    assert result.model == settings.gemini_web_research_model
    assert fake_client.aio.models.generate_content.call_args.kwargs["model"] == "gemini-2.5-flash"


def test_report_exports_are_openable_and_preserve_vietnamese():
    title = "Báo cáo nghiên cứu Acme"
    content = "## Tổng quan\n\n- Sản phẩm đã được xác minh.\n- Cần người duyệt trước khi gửi."
    markdown, md_type = export_report(title, content, "md")
    docx, docx_type = export_report(title, content, "docx")
    pdf, pdf_type = export_report(title, content, "pdf")
    assert markdown.startswith("# Báo cáo".encode()) and md_type.startswith("text/markdown")
    opened_docx = Document(io.BytesIO(docx))
    assert any(title in paragraph.text for paragraph in opened_docx.paragraphs)
    with pdfplumber.open(io.BytesIO(pdf)) as opened_pdf:
        extracted = "\n".join(page.extract_text() or "" for page in opened_pdf.pages)
    assert "Báo cáo nghiên cứu Acme" in extracted
    assert docx_type.endswith("document")
    assert pdf_type == "application/pdf"


def test_all_seven_required_agents_are_present():
    from app.agent.adk_orchestrator import AdkOrchestrator, RecoverableGemini

    agent = AdkOrchestrator._build_agent_tree(
        RecoverableGemini(model="gemini-primary", fallback_model="gemini-fallback"), [], []
    )
    assert {child.name for child in agent.sub_agents} == {
        "email_agent",
        "web_research_agent",
        "company_info_agent",
        "calendar_agent",
        "report_generation_agent",
        "memory_agent",
        "human_approval_agent",
    }


def test_protonx_company_benchmark_has_six_locked_cases_and_thresholds():
    path = Path(__file__).resolve().parents[1] / "evals" / "protonx_company_benchmark.json"
    benchmark = json.loads(path.read_text(encoding="utf-8"))
    assert len(benchmark["cases"]) == 6
    assert len({case["id"] for case in benchmark["cases"]}) == 6
    assert {case["split"] for case in benchmark["cases"]} == {"development", "holdout"}
    assert benchmark["release_thresholds"]["unauthorized_side_effects"] == 0
    assert benchmark["status"] == "candidate_ready_for_live_scoring"
    assert benchmark["release_thresholds"]["maximum_recent_news_age_days"] == 30
    assert not ({"contradictions", "target_sources_per_report", "target_latency_seconds"}
                & benchmark["release_thresholds"].keys())
    examples = benchmark["historical_examples"]
    assert examples["is_release_gate"] is False
    assert examples["sources_per_report"] == 12
    assert examples["latency_seconds"] == 42
    assert examples["reported_contradictions"] == 0
    assert "ProtonX" in examples["provenance"]


async def test_customer_briefing_workflow_is_read_only_and_ends_at_approval():
    from app.api.briefings import CustomerBriefingRequest, prepare_customer_briefing

    outputs = {
        "gmail_read_thread": SimpleNamespace(
            subject="Yêu cầu hợp tác",
            messages=[
                SimpleNamespace(sender="Lan <lan@acme.example>", date="2026-09-25", body="Nhu cầu")
            ],
        ),
        "company_search": SimpleNamespace(items=[]),
        "web_research": SimpleNamespace(
            summary="Acme cung cấp phần mềm.",
            sources=[SimpleNamespace(title="Acme", url="https://acme.example")],
        ),
        "calendar_list_upcoming": SimpleNamespace(
            events=[
                SimpleNamespace(start="2026-09-26T09:00:00+07:00", title="Acme", location="Meet")
            ]
        ),
    }
    registry = SimpleNamespace(
        execute=AsyncMock(side_effect=lambda name, _args, _context: outputs[name])
    )
    request = SimpleNamespace(
        state=SimpleNamespace(request_id="briefing"),
        app=SimpleNamespace(state=SimpleNamespace(registry=registry)),
    )
    response = await prepare_customer_briefing(
        CustomerBriefingRequest(
            gmail_thread_id="thread-1", company_name="Acme", company_domain="acme.example"
        ),
        request,
        SimpleNamespace(id="u1"),
        SimpleNamespace(),
    )
    called = [call.args[0] for call in registry.execute.await_args_list]
    assert called == [
        "gmail_read_thread",
        "company_search",
        "web_research",
        "calendar_list_upcoming",
    ]
    assert not any(
        name.startswith(("gmail_create", "docs_create", "company_upsert")) for name in called
    )
    assert response.ready_for_human_approval
    assert not response.web_research_degraded
    assert "Chưa chuyển tiếp email" in response.report_markdown


async def test_customer_briefing_degrades_when_web_quota_is_exhausted():
    from app.api.briefings import CustomerBriefingRequest, prepare_customer_briefing
    from app.tools.contracts import ToolError

    outputs = {
        "gmail_read_thread": SimpleNamespace(
            subject="Yêu cầu hợp tác",
            messages=[SimpleNamespace(sender="Lan", date="2026-09-25", body="Nhu cầu")],
        ),
        "company_search": SimpleNamespace(items=[]),
        "calendar_list_upcoming": SimpleNamespace(
            events=[SimpleNamespace(start="2026-09-28T10:00:00+07:00", title="Acme", location="")]
        ),
    }

    async def execute(name, _args, _context):
        if name == "web_research":
            raise ToolError("quota", code="web_research_quota_exhausted")
        return outputs[name]

    registry = SimpleNamespace(execute=AsyncMock(side_effect=execute))
    request = SimpleNamespace(
        state=SimpleNamespace(request_id="briefing-degraded"),
        app=SimpleNamespace(state=SimpleNamespace(registry=registry)),
    )
    response = await prepare_customer_briefing(
        CustomerBriefingRequest(gmail_thread_id="thread-1", company_name="Acme"),
        request,
        SimpleNamespace(id="u1"),
        SimpleNamespace(),
    )
    assert response.ready_for_human_approval
    assert response.web_research_degraded
    assert response.warnings
    assert response.meeting_count == 1
    assert "Không suy diễn dữ kiện web" in response.report_markdown
