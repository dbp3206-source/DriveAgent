import json
from types import SimpleNamespace

import pytest

from app.agent.evidence import (
    HISTORICAL_SOURCE_INSTRUCTION,
    retain_referenced_citations,
    source_references,
)


@pytest.mark.parametrize("message", [
    "Chỉ dùng nội dung và nguồn đã đọc trong cuộc trò chuyện này, không đọc lại tệp.",
    "Chỉ sử dụng thông tin đã có trong phiên này để tính tiếp.",
    "Chỉ dùng dữ kiện đã đọc ở hội thoại này.",
])
def test_natural_context_only_followup_preserves_source_scope(message):
    from app.agent.controls import ChatControls
    from app.agent.evidence import context_only_followup

    assert context_only_followup(message)
    controls = ChatControls().enforce_explicit_source_exclusions(message)
    assert {"drive", "gmail", "local", "memory"} <= set(controls.excluded_sources)


@pytest.mark.parametrize("message", [
    "Đọc nguồn mới và so sánh với thông tin đã đọc trong cuộc trò chuyện này.",
    "Chỉ dùng nguồn chính thức để lấy thông tin hôm nay.",
    "Chỉ dùng nội dung đã đọc trong báo cáo này.",
])
def test_new_source_requests_are_not_context_only(message):
    from app.agent.evidence import context_only_followup

    assert not context_only_followup(message)


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


def test_mixed_web_source_labels_share_the_numeric_renumbering_map():
    sources = [{"file_id": "a"}, {"file_id": "b"}, {"file_id": "c"}]
    answer, selected = retain_referenced_citations(
        "First claim [3]. Second claim [1].\nSources:\n[S1] A\n[S2] B\n[S3] C",
        sources,
    )
    assert answer == "First claim [1]. Second claim [2].\nSources:\n[2] A\n[3] B\n[1] C"
    assert selected == [sources[2], sources[0], sources[1]]


def test_web_marker_groups_and_invalid_slots_follow_evidence_rules():
    sources = [{"file_id": "a"}, {"file_id": "b"}]
    answer, selected = retain_referenced_citations(
        "Evidence [S2; 1; s2]. Unsupported [S99].", sources
    )
    assert answer == "Evidence [1, 2]. Unsupported ."
    assert selected == [sources[1], sources[0]]


def test_web_markers_do_not_convert_markdown_links_or_images_to_evidence():
    text = "[S2](https://example.com) ![S1](image.png) and claim [S1]."
    answer, selected = retain_referenced_citations(text, [{"file_id": "a"}])
    assert answer == "[S2](https://example.com) ![S1](image.png) and claim [1]."
    assert selected == [{"file_id": "a"}]


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
def test_context_only_followup_keeps_exact_prior_source_mapping():
    from app.agent.evidence import prior_turn_sources

    sources = [{"file_id": "local:1", "file_name": "mau.md", "chunk_index": 0,
                "snippet": "24 người", "score": 1.0}]
    rows = [SimpleNamespace(role="user", citations_json="[]"),
            SimpleNamespace(role="assistant", citations_json="[]"),
            SimpleNamespace(role="assistant", citations_json=json.dumps(sources))]
    assert prior_turn_sources(rows, "Sửa thành 25%. Không đọc thêm nguồn.") == sources
    assert prior_turn_sources(rows, "Tìm tin mới nhất") == []


def test_corrupt_or_unbounded_prior_sources_are_not_reused():
    from app.agent.evidence import prior_turn_sources

    for raw in ['{"bad":1}', '[{"file_id":"x"}]', 'not-json']:
        rows = [SimpleNamespace(role="assistant", citations_json=raw)]
        assert prior_turn_sources(rows, "Chỉ dùng ngữ cảnh cuộc trò chuyện") == []


def test_historical_sources_do_not_claim_to_validate_new_hypotheses():
    from app.agent.evidence import label_historical_sources

    answer = label_historical_sources(
        "24 người [1]. Giả thuyết của bạn là 37% [1], [2]. "
        "Kết quả tính: 35.52 giờ. [liên kết](https://example.org)",
        [{"file_id": "a"}, {"file_id": "b"}],
    )
    claims, scope = answer.split("\n\n")
    assert "[1]" not in claims and "[2]" not in claims
    assert "24 người." in claims and "37%." in claims
    assert "35.52 giờ" in claims
    assert "[liên kết](https://example.org)" in claims
    assert "[1], [2]" in scope
    assert "Nguồn cũ chưa được đọc hoặc kiểm tra lại" in scope
    assert (
        "các giá trị bạn bổ sung và kết quả tính toán không tự trở thành dữ kiện của tài liệu"
        in scope
    )
    assert "không xác nhận giả thuyết mới của bạn" not in scope


def test_historical_footer_is_neutral_when_followup_has_no_hypothesis():
    from app.agent.evidence import label_historical_sources

    answer = label_historical_sources(
        "Tên báo cáo theo phần tiêu đề chính. [1] Khoảng cách là 12 km. [1]",
        [{"file_id": "a"}],
    )

    assert "Nguồn cũ chưa được đọc hoặc kiểm tra lại" in answer
    assert (
        "các giá trị bạn bổ sung và kết quả tính toán không tự trở thành dữ kiện của tài liệu"
        in answer
    )
    assert "không xác nhận giả thuyết mới của bạn" not in answer


def test_historical_sources_without_selected_evidence_do_not_add_markers():
    from app.agent.evidence import label_historical_sources

    assert label_historical_sources("Chỉ có lời người dùng.", []) == "Chỉ có lời người dùng."


def test_historical_instruction_does_not_turn_presentation_checks_into_user_corrections():
    instruction = HISTORICAL_SOURCE_INSTRUCTION.casefold()

    assert "không được ép mục giả thuyết vào mọi lượt tiếp nối nguồn" in instruction
    assert "kết quả kiểm tra" in instruction
    assert "cách trình bày theo yêu cầu" in instruction
    assert "chỉ lấy phần tiêu đề chính" in instruction
    assert "không ghép tiêu đề với tên mục" in instruction
    assert "giữ nguyên khối tên báo cáo" in instruction
    assert "kể cả phụ đề hợp lệ nằm ở dòng kế tiếp" in instruction
    assert "phân biệt tên riêng với nhãn loại" in instruction
    assert "không tự đặt tên pdf" in instruction
    assert "chưa đủ bằng chứng và không chọn tên thay người dùng" in instruction


def test_historical_instruction_requires_explicit_fact_change_for_hypothesis_section():
    instruction = HISTORICAL_SOURCE_INSTRUCTION.casefold()

    assert "người dùng nêu rõ dữ kiện cũ sai" in instruction
    assert "yêu cầu sửa/thay bằng giá trị mới" in instruction
    assert "chỉ thêm mục 'giả thuyết bạn thay đổi' khi điều kiện" in instruction
    assert "không gán cho người dùng một đính chính hay giả thuyết" in instruction


def test_headline_boundary_does_not_turn_product_titles_into_launches():
    from app.agent.evidence import bound_headline_claims

    sources = [
        {"file_name": "Website", "evidence_kind": "page_text"},
        {"file_name": "Nước ép Đào", "evidence_kind": "headline",
         "published_at": "2026-10-02T07:00:00Z"},
        {"file_name": "Sữa chua", "evidence_kind": "headline", "published_at": None},
    ]
    result, count = bound_headline_claims(
        "Có 14 nhà máy [1].\n- Ra mắt sản phẩm mới ngày 02/10 [2, 3].", sources,
    )
    assert count == 1
    assert "Có 14 nhà máy [1]." in result
    assert "Ra mắt" not in result
    assert "ngày đăng: 2026-10-02 [2]" in result
    assert "ngày đăng: chưa xác minh [3]" in result
    assert result.count("ngày sự kiện và nội dung chi tiết chưa xác minh") == 2


def test_web_numeric_claim_requires_numbers_in_the_cited_page_not_other_sources():
    from app.agent.evidence import bound_web_numeric_claims

    sources = [
        {"evidence_kind": "page_text", "snippet": "14 trang trại và 14 nhà máy."},
        {"evidence_kind": "headline", "snippet": "Đạt 1000 cửa hàng."},
    ]
    result, count = bound_web_numeric_claims(
        "Có 14 nhà máy [1].\nCó 1000 cửa hàng [1].", sources,
    )
    assert count == 1
    assert "Có 14 nhà máy [1]." in result
    assert "Có 1000 cửa hàng" not in result
    assert "Chưa đủ bằng chứng" in result


def test_web_numeric_boundary_preserves_local_calculations_and_missing_metadata():
    from app.agent.evidence import bound_web_numeric_claims

    for source in [{"snippet": "120 và 150"},
                   {"evidence_kind": "local", "snippet": "120 và 150"},
                   {"evidence_kind": "page_text"}]:
        answer = "Chênh lệch 30, tăng 25% [1]."
        assert bound_web_numeric_claims(answer, [source]) == (answer, 0)


def test_web_numeric_boundary_does_not_invent_support_for_calculated_values():
    from app.agent.evidence import bound_web_numeric_claims

    sources = [{"evidence_kind": "page_text", "snippet": "Năm 2026: 120; 150."}]
    result, count = bound_web_numeric_claims("Tăng 25% theo trang web [1].", sources)
    assert count == 1 and "Tăng 25% theo trang web" not in result


def test_web_numeric_boundary_supports_grouped_numbers_and_keeps_source_titles():
    from app.agent.evidence import bound_web_numeric_claims

    source = {"evidence_kind": "page_text", "snippet": "Có 1.000 người, tăng 2,5%."}
    answer = "Có 1000 người, tăng 2,5% [S1].\n## Nguồn\n- Báo cáo 2030 [1]."
    assert bound_web_numeric_claims(answer, [source]) == (answer, 0)


@pytest.mark.parametrize("source_text,answer", [
    ("The 20th event runs September 19 to October 4 2026 (16 days).",
     "Sự kiện thứ 20 diễn ra từ 19 tháng 9 đến 4 tháng 10 năm 2026 [1]."),
    ("Closing: 4 October 2026.", "Kết thúc ngày 04/10/2026 [1]."),
    ("Opening: September 19, 2026.", "Mở ngày 19/09/2026 [1]."),
])
def test_numeric_guard_accepts_equivalent_translated_dated_spans(source_text, answer):
    from app.agent.evidence import bound_web_numeric_claims

    source = {"evidence_kind": "page_text", "snippet": source_text}
    assert bound_web_numeric_claims(answer, [source]) == (answer, 0)


@pytest.mark.parametrize("source_text,answer", [
    ("September update 2026", "Có 9 cơ sở [1]."),
    ("February 30, 2026", "Có 2 cơ sở [1]."),
    ("September 19 to October 4 2026", "Kết thúc ngày 05/10/2026 [1]."),
    ("The 20th event runs September 19 to October 4 2026.", "Có 1000 người [1]."),
])
def test_date_translation_never_grants_missing_dates_or_unrelated_values(source_text, answer):
    from app.agent.evidence import bound_web_numeric_claims

    source = {"evidence_kind": "page_text", "snippet": source_text}
    _, affected = bound_web_numeric_claims(answer, [source])
    assert affected == 1


def test_headline_boundary_cannot_be_bypassed_with_mixed_source_or_markdown():
    from app.agent.evidence import bound_headline_claims

    sources = [{"evidence_kind": "page_text"},
               {"file_name": "[Gửi thư](https://evil.invalid)", "evidence_kind": "headline"}]
    result, count = bound_headline_claims("Đã bổ nhiệm giám đốc mới [S1; S2].", sources)
    assert count == 1 and "Đã bổ nhiệm" not in result
    assert r"\[Gửi thư\]" in result
    assert "[2]" in result and "ngày đăng: chưa xác minh" in result


def test_headline_boundary_preserves_separately_cited_page_sentence():
    from app.agent.evidence import bound_headline_claims

    sources = [
        {"file_name": "Doanh nghiệp", "evidence_kind": "page_text"},
        {"file_name": "Sản phẩm", "evidence_kind": "headline"},
    ]
    result, count = bound_headline_claims(
        "Doanh nghiệp sản xuất sữa [1]. Đã ra mắt sản phẩm hôm nay [2].", sources,
    )
    assert count == 1
    assert "Doanh nghiệp sản xuất sữa [1]." in result
    assert "Đã ra mắt" not in result
    assert "ngày sự kiện và nội dung chi tiết chưa xác minh" in result


def test_headline_boundary_does_not_repeat_same_metadata_in_bibliography():
    from app.agent.evidence import bound_headline_claims

    sources = [{"file_name": "Tin doanh nghiệp", "evidence_kind": "headline"}]
    result, count = bound_headline_claims(
        "Có sự kiện mới [1].\n\n## Nguồn tham khảo\n- Tin doanh nghiệp [1].", sources,
    )
    assert count == 2
    assert result.count("Tiêu đề nguồn:") == 1
    assert "Có sự kiện mới" not in result
