from app.agent.evidence import retain_referenced_citations, source_references


def test_reference_numbers_are_not_document_chunk_positions():
    citations = [
        {"file_id": "a", "chunk_index": 7, "snippet": "State"},
        {"file_id": "b", "chunk_index": 100, "snippet": "Nodes"},
    ]
    references = source_references(citations)
    assert [item["reference"] for item in references] == [1, 2]
    assert [item["chunk_index"] for item in references] == [7, 100]
    assert "reference" not in citations[0]


def test_empty_evidence_has_no_invented_reference():
    assert source_references([]) == []


def test_only_explicitly_referenced_sources_are_returned_and_renumbered():
    citations = [
        {"file_id": "unused", "chunk_index": 0},
        {"file_id": "used-second", "chunk_index": 1},
        {"file_id": "used-first", "chunk_index": 2},
    ]
    answer, selected = retain_referenced_citations(
        "Kết luận từ [3], sau đó đối chiếu [2] và lặp lại [3].",
        citations,
    )
    assert answer == "Kết luận từ [1], sau đó đối chiếu [2] và lặp lại [1]."
    assert [item["file_id"] for item in selected] == ["used-first", "used-second"]


def test_generated_answer_without_reference_does_not_expose_retrieval_candidates():
    answer, selected = retain_referenced_citations(
        "Không có bằng chứng phù hợp.",
        [{"file_id": "candidate", "chunk_index": 0}],
    )
    assert answer == "Không có bằng chứng phù hợp."
    assert selected == []


def test_production_auto_reference_keeps_verified_evidence_when_model_omits_marker():
    answer, selected = retain_referenced_citations(
        "Mã kiểm thử là LOCAL-STUDY-2026.",
        [{"file_id": "local:source-1", "chunk_index": 0}],
        auto_reference=True,
    )
    assert answer.endswith("Nguồn đã kiểm tra: [1]")
    assert selected == [{"file_id": "local:source-1", "chunk_index": 0}]


def test_numeric_markdown_link_is_not_treated_as_source_marker():
    answer, selected = retain_referenced_citations(
        "Xem [1](https://example.invalid) nhưng chưa trích nguồn.",
        [{"file_id": "candidate", "chunk_index": 0}],
    )
    assert answer == "Xem [1](https://example.invalid) nhưng chưa trích nguồn."
    assert selected == []


def test_grouped_and_spaced_citations_are_supported():
    citations = [
        {"file_id": "doc1", "chunk_index": 0},
        {"file_id": "doc2", "chunk_index": 1},
        {"file_id": "doc3", "chunk_index": 2},
    ]
    answer, selected = retain_referenced_citations(
        "Thông tin từ [ 3 ] và nhóm [1, 2], kiểm tra lại [1,2].",
        citations,
    )
    assert answer == "Thông tin từ [1] và nhóm [2, 3], kiểm tra lại [2, 3]."
    assert [item["file_id"] for item in selected] == ["doc3", "doc1", "doc2"]


def test_grouped_citations_support_semicolons_deduplication_and_phantom_filtering():
    citations = [
        {"file_id": "doc1", "chunk_index": 0},
        {"file_id": "doc2", "chunk_index": 1},
    ]
    answer, selected = retain_referenced_citations(
        "Nguồn [1; 2] và lặp [1, 1], có phantom [2; 99] và bỏ [999].",
        citations,
    )
    assert answer == "Nguồn [1, 2] và lặp [1], có phantom [2] và bỏ ."
    assert [item["file_id"] for item in selected] == ["doc1", "doc2"]


def test_adjacent_duplicate_inline_citations_are_collapsed() -> None:
    answer, selected = retain_referenced_citations(
        "Lý do có bằng chứng [2]. [2]\nDùng lại nguồn ở ý sau [2].",
        [{"file_id": "unused"}, {"file_id": "used"}],
    )

    assert answer == "Lý do có bằng chứng [1].\nDùng lại nguồn ở ý sau [1]."
    assert selected == [{"file_id": "used"}]


def test_markers_without_current_turn_evidence_are_removed() -> None:
    answer, selected = retain_referenced_citations("Claim [1]. Another [7].", [])

    assert answer == "Claim . Another ."
    assert selected == []


def test_explicit_pdf_page_corrects_unambiguous_wrong_marker() -> None:
    citations = [
        {"file_id": "pdf", "chunk_index": 1, "page_number": 2},
        {"file_id": "pdf", "chunk_index": 2, "page_number": 3},
    ]

    answer, selected = retain_referenced_citations(
        "Theo tài liệu (Trang 3), output phải tóm tắt đầy đủ [1].",
        citations,
    )

    assert answer == "Theo tài liệu (Trang 3), output phải tóm tắt đầy đủ [1]."
    assert selected == [citations[1]]


def test_explicit_page_alignment_fails_closed_when_page_is_ambiguous() -> None:
    citations = [
        {"file_id": "pdf-a", "chunk_index": 2, "page_number": 3},
        {"file_id": "pdf-b", "chunk_index": 2, "page_number": 3},
    ]

    answer, selected = retain_referenced_citations(
        "Đối chiếu Trang 3 [1].",
        citations,
    )

    assert answer == "Đối chiếu Trang 3 [1]."
    assert selected == [citations[0]]
