"""Optional public search: bounded costs, page evidence and private-key isolation."""

import json
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import Settings
from app.core.security import redact
from app.services.user_inference import runtime_settings
from app.tools.contracts import ToolError
from app.tools.web_research import (
    WebResearchInput,
    WebResearchOutput,
    _assert_public_https,
    collect_tavily_source_bundle,
    web_research,
)

KEY = "unit-test-private-search-key"
PAGE = "Event dates are 19 September 2026 through 4 October 2026. " * 3


@pytest.fixture
def context():
    return SimpleNamespace(source="api", metadata={}, settings=Settings(
        _env_file=None, gemini_api_key="test-model-key", tavily_api_key=KEY))


def mock_http(monkeypatch, handler):
    factory = httpx.AsyncClient
    monkeypatch.setattr("app.tools.web_research.httpx.AsyncClient",
                        lambda **kwargs: factory(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr("app.tools.web_research._assert_public_https", AsyncMock())


def test_server_secret_is_masked_and_preserved_in_user_runtime(context):
    assert KEY not in repr(context.settings)
    assert KEY not in context.settings.model_dump_json()
    isolated = runtime_settings(context.settings, "another-user-model-key")
    assert isolated.tavily_api_key.get_secret_value() == KEY
    assert context.settings.gemini_api_key == "test-model-key"
    assert redact("tvly-" + "a" * 40) == "[REDACTED]"


async def test_basic_search_page_text_and_bounded_public_query(monkeypatch, context):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"results": [{
            "url": "https://example.com/schedule", "title": "Calendar",
            "content": "False snippet date 2030", "raw_content": PAGE,
            "published_date": "2026-10-08", "answer": "Fake answer",
        }]})

    mock_http(monkeypatch, handler)
    sources, blocks = await collect_tavily_source_bundle(WebResearchInput(
        question="ASIAD 2026 diễn ra lúc nào? Không dùng Gmail. Hôm nay là ngày nào?"), context)
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body["query"] == "ASIAD 2026 schedule dates"
    assert body["search_depth"] == "basic" and body["auto_parameters"] is False
    assert body["include_answer"] is False and body["include_raw_content"] == "text"
    assert body["max_results"] <= 6 and "include_domains" not in body
    assert requests[0].headers["authorization"] == f"Bearer {KEY}"
    assert requests[0].url == "https://api.tavily.com/search"
    assert sources[0].evidence_excerpt == PAGE.strip()
    assert sources[0].evidence_kind == "page_text"
    assert sources[0].published_at is None and sources[0].event_date is None
    assert "2030" not in "".join(blocks) and "Fake answer" not in "".join(blocks)
    assert "Tavily" in blocks[0]


async def test_company_query_omits_private_context_and_prefers_selected_host(monkeypatch, context):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"results": [
            {"url": "https://news.example/story", "title": "News", "raw_content": PAGE},
            {"url": "https://example.com", "title": "Overview", "raw_content": PAGE},
        ]})

    mock_http(monkeypatch, handler)
    sources, _ = await collect_tavily_source_bundle(WebResearchInput(
        company_name="Example", domain="example.com",
        question="Private contact 0901234567; budget 99 million", max_sources=2), context)
    body = json.loads(requests[0].content)
    assert "Private" not in body["query"] and "0901234567" not in body["query"]
    assert "99" not in body["query"] and "Example" in body["query"]
    assert body["include_domains"] == ["example.com"]
    assert body["include_domains_mode"] == "prefer"
    assert sources[0].url == "https://example.com"
    assert sources[1].title == "News"  # Third-party is not relabelled official.


async def test_missing_raw_content_reads_page_without_sending_key(monkeypatch, context):
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"results": [{
                "url": "https://example.com/page", "content": "Snippet is not evidence",
                "raw_content": None}]})
        assert "authorization" not in request.headers
        return httpx.Response(200, text=f"<html><body>{PAGE}</body></html>")

    mock_http(monkeypatch, handler)
    sources, _ = await collect_tavily_source_bundle(
        WebResearchInput(question="Event dates"), context)
    assert len(requests) == 2 and sources[0].evidence_excerpt == PAGE.strip()


@pytest.mark.parametrize("status", [301, 401, 429, 432, 433, 503])
async def test_provider_failure_is_sanitized_once_without_model_or_paid_fallback(
    monkeypatch, context, status,
):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, headers={"location": "https://evil.example"},
                              text=f"secret {KEY} private input")

    mock_http(monkeypatch, handler)
    reason = AsyncMock()
    monkeypatch.setattr("app.tools.web_research._reason_over_sources", reason)
    with pytest.raises(ToolError) as error:
        await web_research(WebResearchInput(question="Event dates"), context)
    assert error.value.code == f"web_search_http_{status}"
    assert KEY not in str(error.value) and "private input" not in str(error.value)
    assert len(requests) == 1
    reason.assert_not_awaited()


@pytest.mark.parametrize("response", [{"results": None}, [], {"results": [{
    "url": "https://example.com/denied", "content": PAGE, "raw_content": None}]}])
async def test_invalid_or_snippet_only_result_never_becomes_verified_evidence(
    monkeypatch, context, response,
):
    def handler(request):
        return (httpx.Response(200, json=response) if request.method == "POST"
                else httpx.Response(403))

    mock_http(monkeypatch, handler)
    with pytest.raises(ToolError):
        await collect_tavily_source_bundle(WebResearchInput(question="Event dates"), context)


async def test_discovered_private_url_is_skipped_even_with_provider_raw_content(
    monkeypatch, context,
):
    mock_http(monkeypatch, lambda _: httpx.Response(200, json={"results": [
        {"url": "https://127.0.0.1/private", "raw_content": PAGE},
        {"url": "https://example.com/page", "raw_content": PAGE}]}))

    async def validate(url):
        if "127.0.0.1" in url:
            raise ToolError("Internal destination", code="unsafe_web_source")

    monkeypatch.setattr("app.tools.web_research._assert_public_https", validate)
    sources, _ = await collect_tavily_source_bundle(
        WebResearchInput(question="Event dates"), context)
    assert [source.url for source in sources] == ["https://example.com/page"]


async def test_tavily_path_skips_native_google_and_synthesizes_once(monkeypatch, context):
    collect = AsyncMock(return_value=([], ["read page"]))
    output = WebResearchOutput(summary="Test", sources=[], observed_at="2026-10-08T00:00:00Z",
                               model="test-model")
    reason = AsyncMock(return_value=output)
    native_client = AsyncMock(side_effect=AssertionError("Must not call Google Search"))
    monkeypatch.setattr("app.tools.web_research.collect_tavily_source_bundle", collect)
    monkeypatch.setattr("app.tools.web_research._reason_over_sources", reason)
    monkeypatch.setattr("app.tools.web_research.create_inference_client", native_client)
    context.source = "compiler_gather"
    context.metadata = {}
    assert await web_research(WebResearchInput(question="Event dates"), context) == output
    collect.assert_awaited_once()
    reason.assert_awaited_once()
    native_client.assert_not_called()


async def test_server_selected_gather_defers_only_the_intermediate_synthesis(monkeypatch, context):
    from app.tools.web_research import WebSource

    source = WebSource(title="Public page", url="https://example.com",
                       evidence_kind="page_text", evidence_excerpt=PAGE)
    collect = AsyncMock(return_value=([source], [PAGE]))
    reason = AsyncMock(side_effect=AssertionError("Compiler will synthesize the final report"))
    monkeypatch.setattr("app.tools.web_research.collect_tavily_source_bundle", collect)
    monkeypatch.setattr("app.tools.web_research._reason_over_sources", reason)
    context.source = "compiler_gather"
    context.metadata = {"defer_web_synthesis": True}
    result = await web_research(WebResearchInput(company_name="Example"), context)
    assert result.sources == [source]
    assert result.model == "tavily-basic-page-bundle"
    assert "chưa phải câu trả lời" in result.summary
    reason.assert_not_awaited()


@pytest.mark.parametrize("source, flag", [("api", True), ("compiler_gather", "true"),
                                         ("compiler_gather", False)])
async def test_deferral_requires_both_server_source_and_exact_boolean(
    monkeypatch, context, source, flag,
):
    output = WebResearchOutput(summary="Reasoned answer", sources=[],
                               observed_at="2026-10-08T00:00:00Z", model="test")
    monkeypatch.setattr("app.tools.web_research.collect_tavily_source_bundle",
                        AsyncMock(return_value=([], [])))
    reason = AsyncMock(return_value=output)
    monkeypatch.setattr("app.tools.web_research._reason_over_sources", reason)
    context.source = source
    context.metadata = {"defer_web_synthesis": flag}
    assert await web_research(WebResearchInput(question="Public question"), context) == output
    reason.assert_awaited_once()


async def test_private_redirect_is_blocked_and_partial_good_sources_survive(monkeypatch, context):
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"results": [
                {"url": "https://example.com/redirect", "raw_content": None},
                {"url": "https://example.com/good", "raw_content": PAGE}]})
        return httpx.Response(302, headers={"location": "https://127.0.0.1/private"})

    mock_http(monkeypatch, handler)
    monkeypatch.setattr("app.tools.web_research._assert_public_https", _assert_public_https)
    monkeypatch.setattr("app.tools.web_research.socket.getaddrinfo", lambda host, *_a, **_k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "",
         ("127.0.0.1" if host == "127.0.0.1" else "93.184.216.34", 443))])
    sources, _ = await collect_tavily_source_bundle(
        WebResearchInput(question="Event dates"), context)
    assert [source.url for source in sources] == ["https://example.com/good"]
    assert not any("127.0.0.1" in str(request.url) for request in requests)


async def test_explicit_private_domain_stops_before_search(monkeypatch, context):
    requests = []
    mock_http(monkeypatch, lambda request: requests.append(request))
    monkeypatch.setattr("app.tools.web_research._assert_public_https",
                        AsyncMock(side_effect=ToolError("Private", code="unsafe_web_source")))
    with pytest.raises(ToolError, match="Private"):
        await collect_tavily_source_bundle(WebResearchInput(domain="127.0.0.1"), context)
    assert not requests


async def test_secret_in_query_stops_before_search(monkeypatch, context):
    requests = []
    mock_http(monkeypatch, lambda request: requests.append(request))
    with pytest.raises(ToolError) as error:
        await collect_tavily_source_bundle(WebResearchInput(
            question="api_key = private-value"), context)
    assert error.value.code == "private_search_query" and not requests


async def test_search_transport_timeout_does_not_retry_or_disclose_key(monkeypatch, context):
    requests = []

    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout(f"secret {KEY}", request=request)

    mock_http(monkeypatch, handler)
    with pytest.raises(ToolError) as error:
        await collect_tavily_source_bundle(WebResearchInput(question="Event dates"), context)
    assert error.value.code == "web_search_transport_error"
    assert KEY not in str(error.value) and error.value.__cause__ is None
    assert len(requests) == 1


async def test_search_response_size_is_bounded(monkeypatch, context):
    mock_http(monkeypatch, lambda _: httpx.Response(200, content=b"x" * 2_000_001))
    with pytest.raises(ToolError) as error:
        await collect_tavily_source_bundle(WebResearchInput(question="Event dates"), context)
    assert error.value.code == "web_search_too_large"


async def test_long_raw_content_and_duplicate_urls_are_bounded(monkeypatch, context):
    mock_http(monkeypatch, lambda _: httpx.Response(200, json={"results": [
        {"url": "https://example.com/page", "raw_content": PAGE * 200},
        {"url": "https://example.com/page", "raw_content": PAGE}]}))
    sources, blocks = await collect_tavily_source_bundle(
        WebResearchInput(question="Dates"), context)
    assert len(sources) == 1 and len(sources[0].evidence_excerpt) == 9000
    assert sources[0].evidence_excerpt in blocks[0]


@pytest.mark.parametrize("topic, auxiliary", [("ASIAD 2026", "còn đang diễn ra không"),
                                             ("Lễ hội hoa Nhật Bản", "diễn ra khi nào")])
async def test_official_source_and_date_requirements_survive_query_normalization(
    monkeypatch, context, topic, auxiliary,
):
    queries = []

    def handler(request):
        queries.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": [
            {"url": "https://example.com/event", "raw_content": PAGE}]})

    mock_http(monkeypatch, handler)
    await collect_tavily_source_bundle(WebResearchInput(
        question=f"Hôm nay theo giờ Việt Nam là ngày nào? {topic} {auxiliary}? "
        "Chỉ kết luận từ nguồn chính thức và nêu khoảng ngày sự kiện; "
        "không đọc Gmail hoặc dữ liệu riêng."), context)
    assert queries == [f"{topic} official website schedule dates"]
    assert "Gmail" not in queries[0] and "dữ liệu riêng" not in queries[0]
