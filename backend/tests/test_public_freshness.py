from types import SimpleNamespace

import pytest

from app.agent.freshness import needs_public_evidence, server_time_context
from app.agent.routing import route_request
from app.core.config import Settings
from app.tools.web_research import (
    WebResearchInput,
    WebSource,
    _bundle_urls_are_verified,
    _has_valid_citations,
    _normalize_bundle_citations,
    _safe_unverified_bundle_summary,
    _supported_claims,
)


@pytest.mark.parametrize(
    "question",
    [
        "lịch thi đấu bóng đá nam ASIAD ngày hôm nay",
        "Tỷ giá USD hôm qua",
        "Thời tiết ngày mai",
        "CEO của Bosch là ai?",
        "Phiên bản mới của Python",
        "Chính sách mới nhất về nhập cảnh",
    ],
)
def test_public_freshness_requires_tool(question):
    route = route_request(question)
    assert route.tool == "web_research"
    assert route.direct
    assert route.arguments["question"] == question.strip().rstrip(".?!")


@pytest.mark.parametrize(
    "question",
    [
        "tóm tắt Gmail hôm nay",
        "đọc tài liệu mới nhất trong Drive",
        "đọc file local hôm nay",
        "ghi nhớ hôm nay tôi học Python",
        "Bài tập giả lập: giá cổ phiếu hôm nay là 100",
        "2 + 2",
    ],
)
def test_private_or_static_content_is_not_searched(question):
    assert not needs_public_evidence(question)
    assert route_request(question).tool != "web_research"


def test_public_question_with_explicit_private_source_exclusion_still_routes_web():
    question = "Lịch thi đấu ASIAD hôm nay? Không đọc Gmail hay Drive."
    assert route_request(question).tool == "web_research"
    assert not needs_public_evidence(
        "Đối chiếu nội dung Gmail hôm nay với tin web. Không đọc Drive."
    )


@pytest.mark.parametrize("exclusion", [
    "Không đọc Gmail, Drive, lịch hoặc bộ nhớ, không ghi dữ liệu.",
    "Không đọc Gmail, Drive, lịch hoặc bộ nhớ.",
    "Không dùng memory và calendar.",
])
def test_comma_separated_source_exclusions_do_not_select_memory(exclusion):
    question = "ASIAD hôm nay có đang diễn ra không? " + exclusion
    assert route_request(question).tool == "web_research"


def test_positive_private_content_still_blocks_web_with_negative_source_list():
    assert not needs_public_evidence(
        "Đối chiếu tài liệu khách hàng hôm nay với tin mới. Không đọc Gmail, Drive hoặc bộ nhớ."
    )


def test_live_asiad_followup_routes_to_registered_web_tool():
    question = (
        "Hôm nay theo giờ Việt Nam là ngày nào? ASIAD 2026 có đang diễn ra không, "
        "ở đâu và từ ngày nào đến ngày nào? Kiểm chứng bằng nguồn chính thức trên "
        "Internet, ghi liên kết nguồn. Không đọc Gmail, Drive, lịch hoặc bộ nhớ, "
        "không ghi dữ liệu."
    )
    route = route_request(question)
    assert route.tool == "web_research" and route.direct


def test_incomplete_negative_clause_cannot_hide_private_content():
    assert not needs_public_evidence(
        "Tin hôm nay? Không đọc Gmail, nội dung email khách hàng là bí mật."
    )


def test_official_rate_limit_question_with_comma_exclusions_routes_web():
    question = (
        "Thông tin hiện tại: hãy đọc nguồn chính thức "
        "https://ai.google.dev/gemini-api/docs/rate-limits và cho biết hạn mức Gemini "
        "tính theo API key hay project, hạn mức ngày đặt lại theo múi giờ nào, ngày "
        "cập nhật trang là ngày nào. Chỉ dùng web, không đọc Gmail, Drive, tài liệu "
        "local hoặc bộ nhớ; dẫn nguồn cho từng ý. Nếu không đọc được thì nói "
        "chưa xác minh, không đoán."
    )
    route = route_request(question)
    assert route.tool == "web_research"
    assert route.arguments["domain"] == "https://ai.google.dev/gemini-api/docs/rate-limits"
    assert not needs_public_evidence(
        "Thông tin hiện tại: hãy đối chiếu nội dung Gmail khách hàng với nguồn web, "
        "không đọc Drive, tài liệu local hoặc bộ nhớ."
    )


def test_public_question_preserves_explicit_evidence_page():
    route = route_request(
        "ASIAD hiện tại diễn ra ngày nào? Đọc nguồn https://www.joc.or.jp/games/asia/2026/. "
        "Không đọc Gmail, Drive hoặc bộ nhớ."
    )
    assert route.tool == "web_research"
    assert route.arguments["domain"] == "https://www.joc.or.jp/games/asia/2026/"
    assert not needs_public_evidence(
        "Đối chiếu tài liệu riêng hôm nay với https://example.com/news"
    )


def test_web_input_general_and_company_are_compatible():
    assert WebResearchInput(question="Lịch thi đấu hôm nay").company_name is None
    assert WebResearchInput(company_name="Bosch").company_name == "Bosch"
    assert Settings(_env_file=None).gemini_web_research_model == "gemini-2.5-flash"


def test_server_time_carries_timezone():
    assert server_time_context()["now"].endswith("+07:00")
    assert server_time_context("UTC")["now"].endswith("+00:00")


def test_grounding_links_only_supported_unicode_claims():
    metadata = SimpleNamespace(
        grounding_chunks=[SimpleNamespace(web=SimpleNamespace(uri="https://example.com"))],
        grounding_supports=[
            SimpleNamespace(
                segment=SimpleNamespace(text="Việt Nam thi đấu"), grounding_chunk_indices=[0]
            ),
            SimpleNamespace(
                segment=SimpleNamespace(text="Không được chứng minh"), grounding_chunk_indices=[5]
            ),
        ],
    )
    response = SimpleNamespace(candidates=[SimpleNamespace(grounding_metadata=metadata)])
    source = WebSource(title="Lịch", url="https://example.com")
    assert _supported_claims(response, [source]) == "Việt Nam thi đấu [1]"
    assert source.published_at is None and source.event_date is None
    assert _supported_claims(SimpleNamespace(candidates=[]), [source]) == ""


def test_source_bundle_normalizes_only_bounded_numeric_citations():
    normalized = _normalize_bundle_citations("Dữ kiện [1], nguồn khác [2], sai [9].", 2)
    assert normalized == "Dữ kiện [S1], nguồn khác [S2], sai [9]."
    assert _has_valid_citations(normalized, 2)


def test_valid_marker_does_not_accept_invented_source_url():
    sources = [WebSource(title="Nguồn thật", url="https://example.com/actual")]
    assert _bundle_urls_are_verified("Dữ kiện [S1]", sources)
    assert _bundle_urls_are_verified("[Nguồn](https://example.com/actual).", sources)
    assert not _bundle_urls_are_verified("[S1] https://www.tinhtex.com/news/1", sources)
    assert not _bundle_urls_are_verified("[S1] https://example.com/actual/forged", sources)


async def test_bundle_replaces_model_answer_with_invented_url(monkeypatch):
    from unittest.mock import AsyncMock, Mock

    from app.tools.web_research import _source_bundle_fallback

    sources = [WebSource(title="Nguồn thật", url="https://example.com/actual")]
    client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=AsyncMock(
            return_value=SimpleNamespace(text="Đang diễn ra [S1] https://fake.example/news"))),
            aclose=AsyncMock()), close=Mock())
    monkeypatch.setattr("app.tools.web_research.collect_public_source_bundle",
                        AsyncMock(return_value=(sources, ["[S1] Chỉ có tiêu đề"])))
    monkeypatch.setattr("app.tools.web_research.create_inference_client", lambda **_: client)
    reserve = Mock()
    monkeypatch.setattr("app.tools.web_research.quota_guard",
                        lambda *_args, **_kwargs: SimpleNamespace(reserve=reserve))
    context = SimpleNamespace(settings=Settings(_env_file=None, gemini_api_key="fake-qa-key"))
    output = await _source_bundle_fallback(WebResearchInput(question="Lịch hôm nay"), context)
    assert "Chưa có đủ bằng chứng" in output.summary
    assert "fake.example" not in output.summary
    assert output.sources == sources
    reserve.assert_called_once()
    client.aio.aclose.assert_awaited_once()


def test_source_bundle_can_fail_safe_with_a_cited_non_answer():
    source = WebSource(title="Một tiêu đề công khai", url="https://example.com/news")
    text = _safe_unverified_bundle_summary(
        WebResearchInput(question="Lịch thi đấu hôm nay là gì?"), [source]
    )
    assert "Chưa có đủ bằng chứng" in text
    assert "không khẳng định lịch" in text
    assert "Một tiêu đề công khai" in text
    assert _has_valid_citations(text, 1)


async def test_general_fallback_reads_news_without_requiring_company_domain(monkeypatch, tmp_path):
    from datetime import UTC, datetime
    from email.utils import format_datetime

    from app.tools.contracts import ToolContext
    from app.tools.web_research import collect_public_source_bundle

    date = format_datetime(datetime.now(UTC))
    rss = (f"<rss><channel><item><title>Current public headline</title>"
           f"<link>https://news.google.com/articles/test</link><pubDate>{date}</pubDate>"
           "</item></channel></rss>").encode()
    fetched = []

    async def fetch(_client, url, _maximum):
        fetched.append(url)
        return rss

    monkeypatch.setattr("app.tools.web_research._fetch_with_retry", fetch)
    context = ToolContext(request_id="general", user=SimpleNamespace(id="u"),
                          db=SimpleNamespace(), settings=Settings(_env_file=None,
                          database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"))
    sources, blocks = await collect_public_source_bundle(
        WebResearchInput(question="Public schedule today"), context)
    assert len(fetched) == 2 and all("news.google.com/rss/search" in url for url in fetched)
    assert len(sources) == 1 and blocks[0].startswith("[S1] GOOGLE NEWS RSS")
    assert sources[0].published_at is not None and sources[0].event_date is None


@pytest.mark.parametrize("rss_available", [True, False])
async def test_official_source_survives_empty_or_unavailable_news(monkeypatch, tmp_path,
                                                               rss_available):
    import httpx

    from app.tools.contracts import ToolContext
    from app.tools.web_research import collect_public_source_bundle

    official = "https://example.com/schedule"

    async def fetch(_client, url, _maximum):
        if url == official:
            return (b"<html><body>Official schedule: September 19 to October 4, 2026. "
                    b"Location: Aichi and Nagoya. This is the published event overview."
                    b"</body></html>")
        if not rss_available:
            raise httpx.ConnectError("News unavailable")
        return b"<rss><channel></channel></rss>"

    monkeypatch.setattr("app.tools.web_research._fetch_with_retry", fetch)
    context = ToolContext(request_id="official-only", user=SimpleNamespace(id="u"),
                          db=SimpleNamespace(), settings=Settings(_env_file=None,
                          database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"))
    sources, blocks = await collect_public_source_bundle(
        WebResearchInput(question="Published schedule", domain=official), context)
    assert len(sources) == len(blocks) == 1
    assert sources[0].url == official
    assert blocks[0].startswith("[S1] WEBSITE CHÍNH THỨC")
    assert "September 19 to October 4" in blocks[0]


@pytest.mark.parametrize("url", ["https://user:secret@example.com/", "https://example.com:8443/"])
async def test_public_fetch_rejects_credentials_and_nonstandard_ports(url):
    from app.tools.contracts import ToolError
    from app.tools.web_research import _assert_public_https

    with pytest.raises(ToolError, match="HTTPS"):
        await _assert_public_https(url)


@pytest.mark.parametrize("status", [404, 429])
async def test_unavailable_grounding_uses_readonly_bundle_not_paid_search(monkeypatch, tmp_path,
                                                                       status):
    from unittest.mock import AsyncMock, Mock

    from google.genai.errors import ClientError

    from app.tools.contracts import ToolContext
    from app.tools.web_research import WebResearchOutput, web_research

    result = WebResearchOutput(summary="Chưa xác minh lịch thi đấu [S1]",
                               sources=[WebSource(title="News", url="https://news.google.com/a")],
                               observed_at=WebSource(title="x", url="https://example.com").accessed_at,
                               model="normal-chat+source-bundle")
    generate = AsyncMock(side_effect=ClientError(status, {"error": {"message": "unavailable"}}))
    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate),
                                                aclose=AsyncMock()), close=Mock())
    fallback = AsyncMock(return_value=result)
    monkeypatch.setattr("app.tools.web_research.create_inference_client", lambda **_kwargs: client)
    monkeypatch.setattr("app.tools.web_research._source_bundle_fallback", fallback)
    settings = Settings(_env_file=None, gemini_api_key="fake-qa-key",
                        database_url=f"sqlite+aiosqlite:///{tmp_path / 'state.db'}")
    context = ToolContext(request_id="fallback", user=SimpleNamespace(id="u"),
                          db=SimpleNamespace(), settings=settings)
    assert await web_research(WebResearchInput(question="Schedule today"), context) is result
    assert generate.await_count == 1 and fallback.await_count == 1
    assert generate.call_args.kwargs["model"] == "gemini-2.5-flash"
    client.aio.aclose.assert_awaited_once()
    client.close.assert_called_once()
