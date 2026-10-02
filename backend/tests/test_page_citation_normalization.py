from app.agent.evidence import retain_referenced_citations


def test_page_inside_marker_retains_only_actually_referenced_sources():
    sources = [{"file_id": "a", "page_number": 1},
               {"file_id": "b", "page_number": 8},
               {"file_id": "b", "page_number": 1}]
    text, retained = retain_referenced_citations(
        "Ngành A [1, trang 1]. Ngành B [2, trang 8].", sources, auto_reference=True,
    )
    assert text == "Ngành A [1] (trang 1). Ngành B [2] (trang 8)."
    assert retained == sources[:2]
    assert "Nguồn đã kiểm tra" not in text


def test_wrong_page_does_not_gain_a_clickable_source_or_auto_append():
    text, retained = retain_referenced_citations(
        "Nhận định [1, trang 8].", [{"file_id": "a", "page_number": 1}],
        auto_reference=True,
    )
    assert text == "Nhận định ."
    assert retained == []


def test_valid_page_reference_is_renumbered_after_unused_sources_removed():
    sources = [{"file_id": "a", "page_number": 1}, {"file_id": "b", "page_number": 8}]
    text, retained = retain_referenced_citations("Dữ kiện [2, PAGE 8].", sources)
    assert text == "Dữ kiện [1] (trang 8)."
    assert retained == [sources[1]]
