"""Locked web fixes: compound questions, exact excerpts and actual source authority."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.core.config import Settings
from app.tools.web_research import (
    PublicAnswer,
    PublicConclusion,
    PublicSupport,
    WebResearchInput,
    WebSource,
    _official_source_ids,
    _reason_over_sources,
    _render_public_answer,
    _with_requested_clock,
    collect_tavily_source_bundle,
)
from app.tools.web_scope import government_publication, official_sources_requested, relevant_excerpt


@pytest.mark.parametrize("question", [
    "Chỉ kết luận từ nguồn chính thức.", "Theo nguồn chính thức, lịch ASIAD ngày mai?",
    "Kiểm nguồn chính thức: ESA có công bố mới không?", "Use official sources.",
])
def test_official_request_is_not_limited_to_one_phrase(question):
    assert official_sources_requested(question)


def test_explicitly_not_requiring_official_sources_is_not_misread():
    assert not official_sources_requested("Không cần nguồn chính thức. Tìm bài nhận xét.")


@pytest.mark.parametrize("url,expected", [
    ("https://xaydungchinhsach.chinhphu.gov.vn/schedule", True),
    ("https://xaydungchinhsach.chinhphu.vn/schedule", True),
    ("https://www.example.gov.vn/schedule", True),
    ("https://www.example.go.jp/schedule", True),
    ("https://www.example.gov.uk/schedule", True),
    ("https://www.example.gov.vn.evil.invalid/schedule", False),
    ("https://notgov.vn/schedule", False),
    ("https://example.org/official-website", False),
])
def test_government_namespace_is_host_bound(url, expected):
    assert government_publication(url) is expected


def test_official_identity_cannot_be_self_declared_or_transferred_to_unrelated_subject():
    sources = [
        WebSource(title="Official ASIAD schedule", url="https://news.example/official",
                  evidence_kind="page_text", evidence_excerpt="We are the official site of ASIAD."),
        WebSource(title="NASA event", url="https://example.gov.vn/schedule",
                  evidence_kind="page_text", evidence_excerpt="NASA event ends on 04/10/2026."),
        WebSource(title="ASIAD government schedule", url="https://example.go.jp/schedule",
                  evidence_kind="page_text", evidence_excerpt="ASIAD ends on 04/10/2026."),
    ]
    payload = WebResearchInput(question="Theo nguồn chính thức, ASIAD đã kết thúc?")
    assert _official_source_ids(payload, sources) == {3}


def test_exact_secondary_quote_cannot_bypass_official_source_contract():
    source = WebSource(title="ASIAD news", url="https://football.example/asiad",
                       evidence_kind="page_text", evidence_excerpt="ASIAD ends on 04/10/2026.")
    answer = PublicAnswer(conclusions=[PublicConclusion(kind="inference", text="Đã kết thúc.",
        basis="Ngày kiểm tra sau ngày kết thúc.", supports=[PublicSupport(
            source_id=1, quote="ASIAD ends on 04/10/2026.")])])
    with pytest.raises(ValueError, match="official-source"):
        _render_public_answer(answer, [source], allowed_source_ids=set())


def test_a_quote_cannot_join_two_omitted_page_sections():
    source = WebSource(title="ORBIT schedule", url="https://example.gov.vn/orbit",
                       evidence_kind="page_text",
                       evidence_excerpt="First premise.\n[…]\nOther event.")
    answer = PublicAnswer(conclusions=[PublicConclusion(kind="inference", text="Một kết luận.",
        basis="Đối chiếu nguồn.", supports=[PublicSupport(
            source_id=1, quote="First premise. […] Other event.")])])
    with pytest.raises(ValueError, match="quote"):
        _render_public_answer(answer, [source], allowed_source_ids={1})


async def test_no_official_evidence_preserves_absolute_date_without_spending_model(monkeypatch):
    monkeypatch.setattr("app.tools.web_research.server_time_context",
                        lambda _: {"now": "2026-10-09T23:50:00+07:00"})
    generate = Mock(side_effect=AssertionError("No sufficient official source; do not spend quota"))
    monkeypatch.setattr("app.tools.web_research.create_inference_client", generate)
    source = WebSource(title="Football news", url="https://football.example/asiad",
                       evidence_kind="page_text", evidence_excerpt="ASIAD ends on 04/10/2026.")
    output = await _reason_over_sources(WebResearchInput(
        question="```text Theo nguồn chính thức, ngày mai ASIAD có bóng đá không?```"),
        SimpleNamespace(settings=Settings(_env_file=None)), [source], [])
    assert "10/10/2026" in output.summary
    assert "Chưa xác minh" in output.summary and "Đã kết thúc" not in output.summary
    assert "[S1]" not in output.summary
    generate.assert_not_called()


def test_yesterday_is_absolute_even_when_web_answer_is_unknown(monkeypatch):
    monkeypatch.setattr("app.tools.web_research.server_time_context",
                        lambda _: {"now": "2026-10-09T00:01:00+07:00"})
    text = _with_requested_clock("Chưa xác minh lịch sự kiện.", WebResearchInput(
        question="Hôm qua có kết quả thi đấu không?"))
    assert "Hôm qua theo giờ Việt Nam là 08/10/2026" in text
    assert "không phải ngày sự kiện đã xác minh" in text
    assert "[S" not in text


def test_relevant_lower_page_text_and_source_identity_survive_the_9000_character_bound():
    quote = "ORBIT 2026 event schedule: 19/09/2026 through 04/10/2026."
    raw = "Organizer identity. " + "Navigation and accessibility information. " * 600 + quote
    excerpt = relevant_excerpt(raw, "ORBIT 2026 schedule dates")
    assert len(excerpt) <= 9000 and excerpt.startswith("Organizer identity.")
    assert quote in excerpt and "[…]" in excerpt
    assert excerpt.split("\n[…]\n")[-1] in raw


async def test_discovered_official_link_is_bounded_without_extra_search_or_key_leak(monkeypatch):
    requests = []
    page = ("ORBIT 2026 official website: https://organizer.example/schedule. "
            "The public agency announces the ORBIT event. ")

    def handler(request):
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"results": [
                {"url": "https://agency.gov.vn/orbit", "title": "ORBIT announcement",
                 "raw_content": page},
                {"url": "https://news.example/orbit", "title": "ORBIT report",
                 "raw_content": "ORBIT report from the media. " * 5},
            ]})
        assert request.url == "https://organizer.example/schedule"
        assert "authorization" not in request.headers
        return httpx.Response(200, text="<html>ORBIT 2026 schedule dates: "
                              "19/09/2026 through 04/10/2026. " * 3 + "</html>")

    client = httpx.AsyncClient
    monkeypatch.setattr("app.tools.web_research.httpx.AsyncClient",
                        lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr("app.tools.web_research._assert_public_https", AsyncMock())
    monkeypatch.setattr("app.tools.web_research.server_time_context",
                        lambda _: {"now": "2026-10-09T23:50:00+07:00"})
    context = SimpleNamespace(settings=Settings(_env_file=None, tavily_api_key="fake-test-key"))
    payload = WebResearchInput(
        question="Theo nguồn chính thức, ORBIT ngày mai có lịch gì?", max_sources=2)
    sources, blocks = await collect_tavily_source_bundle(payload, context)
    assert len(requests) == 2
    assert len([request for request in requests if request.method == "POST"]) == 1
    assert "10/10/2026" in json.loads(requests[0].content)["query"]
    assert {source.url for source in sources} == {
        "https://agency.gov.vn/orbit", "https://organizer.example/schedule"}
    assert _official_source_ids(payload, sources) == {1, 2}
    assert all(source.evidence_excerpt in block
               for source, block in zip(sources, blocks, strict=True))
