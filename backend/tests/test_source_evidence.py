import json
from types import SimpleNamespace

from app.agent.evidence import prior_turn_sources, source_references
from app.core.source_evidence import PROMINENT_LINES_LABEL, page_evidence_excerpt


def test_multiline_heading_survives_beyond_prefix_without_inferred_title():
    block = (PROMINENT_LINES_LABEL
             + "\n- PHÂN TÍCH VẬN HÀNH\n- Báo cáo tháng 8:\n- Các thay đổi quy trình")
    page = "Đơn vị Mẫu. Ngày phát hành 07/08/2026.\n" + "Nội dung cột nhỏ. " * 100 + "\n\n" + block
    snippet = page_evidence_excerpt(page)
    assert snippet.startswith("Đơn vị Mẫu.")
    assert block in snippet
    assert "- Báo cáo tháng 8:\n- Các thay đổi quy trình" in snippet
    assert len(snippet) <= 4000
    source = {"file_id": "local:synthetic", "file_name": "mau.pdf", "chunk_index": 0,
              "page_number": 1, "snippet": snippet, "score": 1.0}
    rows = [SimpleNamespace(role="assistant", citations_json=json.dumps([source]))]
    reused = prior_turn_sources(rows, "Chỉ dùng ngữ cảnh cuộc trò chuyện này")
    assert source_references(reused)[0]["snippet"] == snippet
    assert source_references(reused)[0]["reference"] == 1


def test_typography_budget_and_page_boundary_are_bounded():
    text = "x" * 8000 + PROMINENT_LINES_LABEL + "\n- " + "y" * 10000
    assert len(page_evidence_excerpt(text, plain_limit=3000)) <= 4000
    text = "Page one\n" + PROMINENT_LINES_LABEL + "\n- First heading\n<!-- page:2 -->Second heading"
    excerpt = page_evidence_excerpt(text)
    assert "First heading" in excerpt
    assert "Second heading" not in excerpt


def test_plain_page_preserves_previous_excerpt_limits():
    assert page_evidence_excerpt("x" * 10000) == "x" * 500
    assert page_evidence_excerpt("x" * 10000, plain_limit=3000) == "x" * 3000


def test_explicit_page_excerpt_keeps_body_qualification_not_only_broad_heading():
    heading = "Báo cáo doanh số thị trường: dự báo tăng 12%.\n"
    qualification = "Chỉ các cửa hàng trong mẫu khảo sát được dự báo tăng 12%."
    page = heading + "Nội dung bối cảnh. " * 50 + qualification
    for typography in ("", "\n\n" + PROMINENT_LINES_LABEL + "\n- Dự báo doanh số"):
        excerpt = page_evidence_excerpt(page + typography, plain_limit=3000)
        assert heading.strip() in excerpt
        assert qualification in excerpt
        assert len(excerpt) <= 4000


def test_larger_body_budget_keeps_typography_within_same_page():
    page = "Bối cảnh. " * 340 + PROMINENT_LINES_LABEL + "\n- Mục chính"
    excerpt = page_evidence_excerpt(
        page + "\n<!-- page:2 -->Không thuộc trang này", plain_limit=3000,
    )
    assert PROMINENT_LINES_LABEL in excerpt
    assert "Mục chính" in excerpt
    assert "Không thuộc trang này" not in excerpt
    assert len(excerpt) <= 4000
