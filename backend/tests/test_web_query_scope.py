"""No model calls: fallback queries keep the subject, not response controls."""

from datetime import UTC, datetime
from email.utils import format_datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from app.core.config import Settings
from app.tools.contracts import ToolContext
from app.tools.web_research import (
    WebResearchInput,
    _news_items,
    _public_query_topic,
    collect_public_source_bundle,
)


@pytest.mark.parametrize("question,query,anchors", [
    ("Hôm nay theo giờ Việt Nam là ngày nào? ASIAD 2026 còn đang diễn ra không? "
     "Chỉ kết luận từ nguồn chính thức; không đọc dữ liệu riêng.",
     "ASIAD 2026 còn đang diễn ra không", ["ASIAD"]),
    ("NASA 2026 có thông báo gì? Không ghi dữ liệu. Nếu thiếu thì nói rõ.",
     "NASA 2026 có thông báo gì", ["NASA"]),
    ("Python latest release? Chỉ trả lời ngắn. Không đọc thư.",
     "Python latest release", []),
    ("Google API pricing? Chỉ trả lời ngắn.", "Google API pricing", ["API"]),
])
def test_query_retains_subject_without_answer_controls(question, query, anchors):
    assert _public_query_topic(question) == (query, anchors)


async def test_unrelated_headlines_do_not_consume_relevant_source_budget(monkeypatch):
    date = format_datetime(datetime.now(UTC))
    titles = ["Unrelated phone launch", "Unrelated airline", "NASA research update"]
    items = "".join(
        f"<item><title>{title}</title><link>https://news.google.com/articles/{index}</link>"
        f"<pubDate>{date}</pubDate></item>" for index, title in enumerate(titles)
    )
    rss = ("<rss><channel>" + items + "</channel></rss>").encode()
    queries = []

    async def fetch(_client, url, _maximum):
        queries.append(parse_qs(urlsplit(url).query)["q"][0])
        return rss

    monkeypatch.setattr("app.tools.web_research._fetch_with_retry", fetch)
    context = ToolContext(request_id="query-scope", user=SimpleNamespace(id="qa"),
                          db=SimpleNamespace(), settings=Settings(_env_file=None))
    sources, _blocks = await collect_public_source_bundle(
        WebResearchInput(question="NASA 2026 có thông báo gì? Không đọc thư.", max_sources=2),
        context,
    )
    assert queries == ["NASA 2026 có thông báo gì when:30d"] * 2
    assert [source.title for source in sources] == ["NASA research update"]
    # Relevance is not authority or full-text evidence.
    assert sources[0].evidence_kind == "headline"
    assert sources[0].event_date is None


async def test_synthesis_and_saved_source_use_identical_bounded_text(monkeypatch):
    async def fetch(_client, url, _maximum):
        if "news.google.com" in url:
            return b"<rss><channel/></rss>"
        return ("<html><body>" + "Verified source text. " * 700 + "</body></html>").encode()

    monkeypatch.setattr("app.tools.web_research._fetch_with_retry", fetch)
    context = ToolContext(request_id="same-source", user=SimpleNamespace(id="qa"),
                          db=SimpleNamespace(), settings=Settings(_env_file=None))
    sources, blocks = await collect_public_source_bundle(
        WebResearchInput(domain="example.com", question="Company overview", max_sources=2),
        context,
    )
    assert len(sources) == len(blocks) == 1
    assert sources[0].evidence_kind == "page_text"
    assert len(sources[0].evidence_excerpt) <= 9000
    assert blocks[0].split("\n", 1)[1] == sources[0].evidence_excerpt


async def test_explicit_company_query_rejects_unrelated_feed_entries(monkeypatch):
    date = format_datetime(datetime.now(UTC))
    titles = ["Football result - Publisher", "Acmeology announcement - Publisher",
              "Acme research update - Publisher"]
    rss = ("<rss><channel>" + "".join(
        f"<item><title>{title}</title><link>https://news.google.com/articles/{index}</link>"
        f"<pubDate>{date}</pubDate></item>" for index, title in enumerate(titles)
    ) + "</channel></rss>").encode()

    async def fetch(_client, url, _maximum):
        return rss if "news.google.com" in url else b"<html>Official company text. </html>" * 8

    monkeypatch.setattr("app.tools.web_research._fetch_with_retry", fetch)
    context = ToolContext(request_id="company-scope", user=SimpleNamespace(id="qa"),
                          db=SimpleNamespace(), settings=Settings(_env_file=None))
    sources, _blocks = await collect_public_source_bundle(
        WebResearchInput(company_name="Acme Global", domain="example.com",
                         news_query="Acme Vietnam", max_sources=2), context,
    )
    assert [source.title for source in sources if source.evidence_kind == "headline"] == [
        "Acme research update - Publisher"]


def test_empty_news_title_with_publisher_is_not_a_news_item():
    date = format_datetime(datetime.now(UTC))
    rss = (f"<rss><channel><item><title>- Publisher</title>"
           f"<link>https://news.google.com/articles/empty</link><pubDate>{date}</pubDate>"
           "</item></channel></rss>").encode()
    assert _news_items(rss, 2) == []
