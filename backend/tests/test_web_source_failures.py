"""Independent source failures must not erase successfully fetched evidence."""

from datetime import UTC, datetime
from email.utils import format_datetime
from types import SimpleNamespace

import httpx
import pytest

from app.core.config import Settings
from app.tools.contracts import ToolContext, ToolError
from app.tools.web_research import WebResearchInput, _fetch_with_retry, collect_public_source_bundle


@pytest.mark.parametrize("status", [403, 404])
async def test_permanent_http_failure_is_not_retried(monkeypatch, status):
    attempts = []

    async def fetch(*_args):
        attempts.append(status)
        response = httpx.Response(status, request=httpx.Request("GET", "https://example.com"))
        response.raise_for_status()

    monkeypatch.setattr("app.tools.web_research._fetch_bounded", fetch)
    with pytest.raises(ToolError) as error:
        await _fetch_with_retry(SimpleNamespace(), "https://example.com", 1000)
    assert error.value.code == f"web_source_http_{status}"
    assert not error.value.retryable
    assert attempts == [status]


@pytest.mark.parametrize("failure", ["web_source_http_403", "web_source_transport_error",
                                     "official_source_empty"])
async def test_unread_official_page_is_not_cited_and_news_survives(monkeypatch, tmp_path, failure):
    published = format_datetime(datetime.now(UTC))
    rss = ("<rss><channel><item><title>Verified headline only</title>"
           "<link>https://news.google.com/articles/example</link>"
           f"<pubDate>{published}</pubDate></item></channel></rss>").encode()
    calls = []

    async def fetch(_client, url, _maximum):
        calls.append(url)
        if url == "https://example.com":
            if failure == "official_source_empty":
                return b"<html></html>"
            raise ToolError("Unread source", code=failure)
        return rss

    monkeypatch.setattr("app.tools.web_research._fetch_with_retry", fetch)
    context = ToolContext(request_id="partial", user=SimpleNamespace(id="u"),
                          db=SimpleNamespace(), settings=Settings(_env_file=None,
                          database_url=f"sqlite+aiosqlite:///{tmp_path / 'state.db'}"))
    sources, blocks = await collect_public_source_bundle(
        WebResearchInput(company_name="Example", domain="https://example.com"), context)
    assert len(calls) == 3
    assert len(sources) == 1
    assert sources[0].url == "https://news.google.com/articles/example"
    assert "Chưa đọc được website chính thức" in blocks[0]
    assert blocks[1].startswith("[S1] GOOGLE NEWS RSS")
    assert "WEBSITE CHÍNH THỨC" not in "\n".join(blocks)


async def test_unsafe_official_source_is_never_degraded_to_news(monkeypatch, tmp_path):
    async def fetch(_client, url, _maximum):
        if url == "https://example.com":
            raise ToolError("Private destination", code="unsafe_web_source")
        return b"<rss><channel></channel></rss>"

    monkeypatch.setattr("app.tools.web_research._fetch_with_retry", fetch)
    context = ToolContext(request_id="unsafe", user=SimpleNamespace(id="u"),
                          db=SimpleNamespace(), settings=Settings(_env_file=None,
                          database_url=f"sqlite+aiosqlite:///{tmp_path / 'state.db'}"))
    with pytest.raises(ToolError) as error:
        await collect_public_source_bundle(WebResearchInput(domain="https://example.com"), context)
    assert error.value.code == "unsafe_web_source"


@pytest.mark.parametrize("status", [429, 503])
async def test_transient_http_failure_still_retries(monkeypatch, status):
    attempts = []

    async def fetch(*_args):
        attempts.append(status)
        if len(attempts) < 3:
            httpx.Response(status, request=httpx.Request("GET", "https://example.com"))\
                .raise_for_status()
        return b"Recovered actual response"

    async def no_sleep(_delay):
        pass

    monkeypatch.setattr("app.tools.web_research._fetch_bounded", fetch)
    monkeypatch.setattr("app.tools.web_research.asyncio.sleep", no_sleep)
    assert await _fetch_with_retry(SimpleNamespace(), "https://example.com", 1000) == \
        b"Recovered actual response"
    assert len(attempts) == 3


async def test_no_readable_sources_retains_precise_http_error(monkeypatch, tmp_path):
    async def fetch(_client, url, _maximum):
        if url == "https://example.com":
            raise ToolError("Denied", code="web_source_http_403")
        raise ToolError("Unavailable news", code="web_source_transport_error", retryable=True)

    monkeypatch.setattr("app.tools.web_research._fetch_with_retry", fetch)
    context = ToolContext(request_id="all-failed", user=SimpleNamespace(id="u"),
                          db=SimpleNamespace(), settings=Settings(_env_file=None,
                          database_url=f"sqlite+aiosqlite:///{tmp_path / 'state.db'}"))
    with pytest.raises(ToolError) as error:
        await collect_public_source_bundle(WebResearchInput(domain="https://example.com"), context)
    assert error.value.code == "web_source_http_403"


async def test_generic_company_brief_discovers_news_for_public_host_not_private_text(
    monkeypatch, tmp_path,
):
    from urllib.parse import parse_qs, urlsplit

    queries = []

    async def fetch(_client, url, _maximum):
        if url == "https://example.com":
            return b"<html>" + b"Public company overview " * 8 + b"</html>"
        queries.append(parse_qs(urlsplit(url).query)["q"][0])
        return b"<rss><channel></channel></rss>"

    monkeypatch.setattr("app.tools.web_research._fetch_with_retry", fetch)
    context = ToolContext(request_id="query-scope", user=SimpleNamespace(id="u"),
                          db=SimpleNamespace(), settings=Settings(_env_file=None,
                          database_url=f"sqlite+aiosqlite:///{tmp_path / 'state.db'}"))
    await collect_public_source_bundle(WebResearchInput(
        domain="https://example.com", question="Generic overview. Private contact context"
    ), context)
    assert queries == ["site:example.com when:30d", "site:example.com when:30d"]
