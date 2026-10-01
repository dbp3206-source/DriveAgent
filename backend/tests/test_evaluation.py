import json

from app.services.evaluation import (
    evaluate_text_answer,
    run_adversarial_mutation_regression,
    run_answer_contract_benchmark,
    run_output_quality_regression,
    run_routing_regression,
)


def test_reference_answer_contracts_are_versioned_enforced_and_pass():
    result = run_answer_contract_benchmark()
    assert result["version"] == "1.0.0"
    assert result["total"] == 16
    assert result["passed"] == result["total"], json.dumps(
        result, ensure_ascii=False, indent=2
    )
    assert result["live_model_checked"] is False
    assert result["coverage"]["answer_key_cases"] == result["total"]
    assert result["coverage"]["citation_binding_cases"] >= 2
    assert result["coverage"]["table_cases"] >= 3


def test_adversarial_mutations_reject_all_160_known_bad_candidates():
    result = run_adversarial_mutation_regression()
    assert result["total"] == 160
    assert result["passed"] == 160, json.dumps(result, ensure_ascii=False, indent=2)
    assert result["pass_rate"] == 1.0
    assert len(result["coverage"]) == 9


def test_output_contracts_hard_fail_missing_sections_table_and_steps():
    result = evaluate_text_answer(
        "Lên kế hoạch và so sánh hai lựa chọn.",
        "Một đoạn trả lời không có cấu trúc.",
        required_sections=["Khuyến nghị", "Việc tiếp theo"],
        require_markdown_table=True,
        min_numbered_steps=2,
    )

    assert result["passed"] is False
    assert "missing_required_section" in result["hard_failures"]
    assert "missing_required_table" in result["hard_failures"]
    assert "below_minimum_numbered_step_count" in result["hard_failures"]
    assert result["fact_checks"]["missing_required_sections"] == [
        "Khuyến nghị",
        "Việc tiếp theo",
    ]


def test_golden_routing_regression_is_versioned_and_passes():
    result = run_routing_regression()
    assert result["version"]
    assert result["total"] >= 10
    assert result["passed"] == result["total"], json.dumps(result, ensure_ascii=False, indent=2)
    assert "does not measure answer correctness" in result["scope"]


def test_golden_output_quality_regression_is_versioned_and_passes():
    result = run_output_quality_regression()
    assert result["version"] == "1.3.0"
    assert result["total"] == 12
    assert result["passed"] == result["total"], json.dumps(result, ensure_ascii=False, indent=2)
    assert result["pass_rate"] == 1.0


def test_output_evaluator_reports_scope_and_broken_citation():
    result = evaluate_text_answer(
        "Tóm tắt tài liệu",
        "Một kết luận không gắn đúng nguồn [2].",
        [{"file_id": "one", "file_name": "one.md"}],
    )
    assert result["scope"] == "observable_output_quality_not_factual_correctness"
    assert result["passed"] is False
    assert any("citation" in issue for issue in result["issues"])
    assert "invalid_citation_reference" in result["hard_failures"]
    assert result["verification"]["semantic_entailment_checked"] is False


def test_output_evaluator_hard_fails_explicit_wrong_fact_and_empty_answer():
    wrong = evaluate_text_answer(
        "Tính 2 + 2.",
        "2 + 2 = 5.",
        expected_facts=["4"],
    )
    assert wrong["passed"] is False
    assert "missing_expected_fact" in wrong["hard_failures"]

    empty = evaluate_text_answer(
        "Mã kiểm thử là gì?",
        "",
        expected_facts=["DA-LOCAL-2026"],
    )
    assert empty["passed"] is False
    assert "empty_answer" in empty["hard_failures"]


def test_output_evaluator_hard_fails_uncited_categorical_claims_when_required():
    result = evaluate_text_answer(
        "So sánh nhưng không khẳng định khoa học nếu không có nguồn.",
        "| Ghi nhớ dài hạn | Cao, bền vững | Thấp, dễ quên nhanh |",
        forbid_uncited_categorical_claims=True,
    )

    assert result["passed"] is False
    assert "uncited_categorical_claim" in result["hard_failures"]
    assert result["fact_checks"]["uncited_categorical_lines"]


def test_expected_facts_use_token_boundaries_for_numbers_and_phrases():
    wrong_number = evaluate_text_answer(
        "Tính 2 + 2.", "Đáp án là 14.", expected_facts=["4"]
    )
    wrong_decimal = evaluate_text_answer(
        "Tính 2 + 2.", "Đáp án là 4,5.", expected_facts=["4"]
    )
    wrong_phrase = evaluate_text_answer(
        "Từ khóa nào cần có?", "Câu trả lời có concatenate.", expected_facts=["cat"]
    )
    correct = evaluate_text_answer(
        "Tính 2 + 2.", "2 + 2 = 4.", expected_facts=["4"]
    )

    assert wrong_number["passed"] is False
    assert wrong_number["fact_checks"]["missing_expected_facts"] == ["4"]
    assert wrong_decimal["passed"] is False
    assert wrong_phrase["passed"] is False
    assert correct["passed"] is True


def test_expected_decimal_accepts_vietnamese_separator_without_partial_match():
    locale_decimal = evaluate_text_answer(
        "Trung bình là bao nhiêu?", "Trung bình là 7,5.", expected_facts=["7.5"]
    )
    different_decimal = evaluate_text_answer(
        "Trung bình là bao nhiêu?", "Trung bình là 75,0.", expected_facts=["7.5"]
    )

    assert locale_decimal["passed"] is True
    assert different_decimal["passed"] is False


def test_required_citation_marker_alone_is_not_verified_support():
    result = evaluate_text_answer(
        "Tóm tắt tài liệu.",
        "Kết luận tùy ý [1].",
        [{"file_id": "qa-doc", "snippet": "Nội dung không liên quan."}],
        require_citations=True,
    )

    assert result["passed"] is False
    assert "citation_claim_bindings_missing" in result["hard_failures"]
    assert result["verification"]["citation_status"] == "unverified"
    assert result["verification"]["semantic_entailment_checked"] is False


def test_grouped_citation_markers_are_valid_references():
    result = evaluate_text_answer(
        "Tóm tắt hai nguồn.",
        "Kết luận được hai nguồn hỗ trợ [1, 2].",
        [
            {"file_id": "one", "snippet": "Nguồn một."},
            {"file_id": "two", "snippet": "Nguồn hai."},
        ],
    )

    assert "missing_citation_marker" not in result["hard_failures"]
    assert "invalid_citation_reference" not in result["hard_failures"]


def test_expected_fact_ignores_inline_markdown_delimiters():
    result = evaluate_text_answer(
        "Dãy giá trị là gì?",
        "Dữ liệu gồm các số nguyên dương từ `1` đến `14`.",
        expected_fact_groups=[["các số nguyên dương từ 1 đến 14"]],
    )

    assert result["passed"] is True


def test_expected_citation_binding_checks_claim_marker_source_and_excerpt():
    expected_binding = [
        {
            "claim": "DA-LOCAL-2026",
            "citation_index": 1,
            "file_id": "qa-doc",
            "evidence_fact": "DA-LOCAL-2026",
        }
    ]
    answer = "Mã kiểm thử là DA-LOCAL-2026 [1]."
    result = evaluate_text_answer(
        "Mã kiểm thử là gì?",
        answer,
        [{"file_id": "qa-doc", "snippet": "Mã kiểm thử là DA-LOCAL-2026."}],
        expected_claim_citations=expected_binding,
        require_citations=True,
    )
    wrong_source = evaluate_text_answer(
        "Mã kiểm thử là gì?",
        answer,
        [{"file_id": "another-doc", "snippet": "Mã kiểm thử là DA-LOCAL-2026."}],
        expected_claim_citations=expected_binding,
        require_citations=True,
    )
    wrong_excerpt = evaluate_text_answer(
        "Mã kiểm thử là gì?",
        answer,
        [{"file_id": "qa-doc", "snippet": "Mã khác là DA-LOCAL-2025."}],
        expected_claim_citations=expected_binding,
        require_citations=True,
    )

    assert result["passed"] is True
    assert result["verification"]["citation_status"] == "answer_key_binding_checked"
    assert result["verification"]["semantic_entailment_checked"] is False
    assert wrong_source["passed"] is False
    assert "citation_source_mismatch" in wrong_source["hard_failures"]
    assert wrong_excerpt["passed"] is False
    assert "citation_evidence_fact_missing" in wrong_excerpt["hard_failures"]


def test_gate2_local_binding_accepts_number_alias_but_rejects_wrong_source():
    binding = [{
        "claim_any": ["ba buổi", "3 buổi"],
        "citation_index": 1,
        "file_name": "local-study-smoke.md",
        "evidence_fact": "ba buổi",
    }]
    answer = "Kế hoạch ôn tập gồm 3 buổi [1]."
    source = {"file_id": "local:runtime-id", "file_name": "local-study-smoke.md",
              "snippet": "Kế hoạch ôn tập gồm ba buổi, mỗi buổi 45 phút."}
    correct = evaluate_text_answer(
        "Kế hoạch ôn tập gồm mấy buổi?", answer, [source],
        expected_fact_groups=[["ba buổi", "3 buổi"]],
        expected_claim_citations=binding, require_citations=True,
    )
    wrong_source = evaluate_text_answer(
        "Kế hoạch ôn tập gồm mấy buổi?", answer,
        [{**source, "file_name": "other.md"}],
        expected_fact_groups=[["ba buổi", "3 buổi"]],
        expected_claim_citations=binding, require_citations=True,
    )
    wrong_number = evaluate_text_answer(
        "Kế hoạch ôn tập gồm mấy buổi?", "Kế hoạch gồm 13 buổi [1].", [source],
        expected_fact_groups=[["ba buổi", "3 buổi"]],
        expected_claim_citations=binding, require_citations=True,
    )
    assert correct["passed"] is True
    assert correct["verification"]["citation_status"] == "answer_key_binding_checked"
    assert "citation_source_mismatch" in wrong_source["hard_failures"]
    assert "missing_expected_fact" in wrong_number["hard_failures"]


def test_email_evaluator_catches_event_time_mislabeled_as_deadline():
    result = evaluate_text_answer(
        "Tổng hợp email chưa đọc hôm nay",
        """## Cần theo dõi

- Thời gian sự kiện: 19:30 hôm nay.
- Deadline: 19:30 hôm nay.

## Cần trả lời

Không có.

## Chỉ để biết

Không có.
""",
    )
    assert result["intent"] == "email_digest"
    assert any("deadline" in issue for issue in result["issues"])
    assert result["score"] <= 90


def test_email_list_is_not_penalized_as_action_digest():
    result = evaluate_text_answer(
        "Liệt kê 3 email chưa đọc gần đây nhất. Chỉ nêu người gửi, tiêu đề và thời gian.",
        """1. **Người gửi:** Lan
   - **Tiêu đề:** Báo cáo tuần
   - **Thời gian:** 09:30 hôm nay
2. **Người gửi:** Minh
   - **Tiêu đề:** Lịch họp
   - **Thời gian:** 08:00 hôm nay
3. **Người gửi:** An
   - **Tiêu đề:** Tài liệu tham khảo
   - **Thời gian:** Hôm qua
""",
    )

    assert result["intent"] == "email_list"
    assert "Tổng hợp email chưa tách nhóm hành động rõ ràng." not in result["issues"]
    assert "Có khoảng trắng thừa làm lỗi nhịp trình bày." not in result["issues"]
    assert result["dimensions"]["task_fit"] == 20


def test_pdf_claim_binds_to_cited_page_even_when_reference_number_changes() -> None:
    binding = [{
        "claim": "Task Success", "file_name": "Evaluation-Harness.pdf",
        "page_number": 15, "evidence_fact": "Task Success",
    }]
    citations = [
        {
            "file_id": "other", "file_name": "other.md", "page_number": None,
            "snippet": "unrelated",
        },
        {
            "file_id": "pdf", "file_name": "Evaluation-Harness.pdf", "page_number": 15,
            "snippet": "Task Success là kết quả cuối",
        },
    ]
    correct = evaluate_text_answer(
        "GAIA đánh giá gì?", "GAIA đo Task Success [2].", citations,
        expected_claim_citations=binding, require_citations=True,
    )
    wrong_page = evaluate_text_answer(
        "GAIA đánh giá gì?", "GAIA đo Task Success [1].", citations,
        expected_claim_citations=binding, require_citations=True,
    )

    assert "citation_source_mismatch" not in correct["hard_failures"]
    assert "citation_source_mismatch" in wrong_page["hard_failures"]
