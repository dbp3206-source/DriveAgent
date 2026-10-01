from types import SimpleNamespace

import pytest
from google.genai import errors, types

from app.agent.output_contract import enforce_presentation_contract, proactive_action_instruction
from app.agent.presentation import (
    explicit_presentation_contract,
    presentation_contract_violations,
)


def test_extracts_only_literal_measurable_contracts():
    contract = explicit_presentation_contract(
        "Giải thích trong khoảng 180-250 từ, có hai bullet và bảng so sánh."
    )
    assert contract.min_words == 180
    assert contract.max_words == 250
    assert contract.min_bullets == 2
    assert contract.require_markdown_table is True


def test_explicit_action_trigger_request_frontloads_the_business_deliverable():
    instruction = proactive_action_instruction(
        "Đề xuất hành động khả thi và trigger định lượng cho tồn kho."
    )
    assert "## Hành động và trigger" in instruction
    assert "Sau đó mới phân tích" in instruction
    assert "thời gian chờ" in instruction
    assert "không gọi tồn dương là thiếu hàng" in instruction
    assert proactive_action_instruction("Tính tồn kho cuối kỳ.") == ""


def test_bounded_length_instruction_gives_generation_a_concrete_target():
    contract = explicit_presentation_contract("Viết bản tư vấn chuyên sâu 700–900 từ.")
    assert contract.min_words == 700
    assert contract.max_words == 900
    assert "nhắm khoảng 800 từ" in contract.instruction()


def test_source_location_phrase_does_not_require_a_markdown_table():
    contract = explicit_presentation_contract("Giá trị ở ô A2 và N2 trong bảng Chi phí là gì?")
    assert contract.require_markdown_table is False
    assert contract.active is False


def test_concise_answer_phrase_uses_documented_maximum_without_affecting_plans():
    brief = explicit_presentation_contract("Hãy trả lời ngắn gọn MCP là gì.")
    plan = explicit_presentation_contract("Lập kế hoạch học tập ngắn gọn cho bốn tuần.")

    assert brief.max_words == 80
    assert brief.instruction() == "không quá 80 từ"
    assert plan.max_words is None


def test_one_page_request_gets_a_real_length_and_source_analysis_contract():
    contract = explicit_presentation_contract(
        "Giải thích email này thật chi tiết, độ dài một trang."
    )

    assert contract.min_words == 650
    assert contract.max_words == 1000
    assert contract.depth_profile == "page"
    assert "thông điệp trung tâm" in contract.depth_guidance
    assert "tác động hoặc việc cần làm" in contract.depth_guidance
    assert "không thêm dữ kiện thiếu căn cứ" in contract.instruction()


def test_expand_and_deep_dive_requests_require_substantive_depth():
    contract = explicit_presentation_contract(
        "Mở rộng câu trả lời, phân tích sâu các tác động và góc nhìn khác."
    )

    assert contract.min_words == 750
    assert contract.max_words == 1500
    assert contract.depth_profile == "deep_dive"
    assert "giới hạn, ngoại lệ hoặc góc nhìn khác" in contract.depth_guidance


def test_deep_cross_source_comparison_uses_comparison_dimensions_not_summary_only():
    contract = explicit_presentation_contract(
        "Đối chiếu email này với tài liệu Drive, phân tích toàn diện mọi góc độ."
    )

    assert contract.depth_profile == "deep_dive"
    assert "tiêu chí chung để so sánh" in contract.depth_guidance
    assert "khuyến nghị theo từng tình huống" in contract.depth_guidance


def test_explicit_numeric_length_overrides_inferred_depth_default():
    contract = explicit_presentation_contract("Mở rộng nhưng giữ trong 500-700 từ, có ba bullet.")

    assert contract.min_words == 500
    assert contract.max_words == 700
    assert contract.min_bullets == 3


def test_detects_word_bullet_step_and_table_violations():
    contract = explicit_presentation_contract(
        "Trả lời 20-30 từ, có hai bullet, ba bước và có bảng."
    )
    failures = presentation_contract_violations("Một câu trả lời ngắn.", contract)
    assert failures == [
        "below_explicit_word_minimum",
        "below_explicit_bullet_minimum",
        "below_explicit_numbered_step_minimum",
        "missing_explicit_markdown_table",
    ]


def test_deep_answer_requires_separate_sections_not_only_more_words():
    contract = explicit_presentation_contract("Mở rộng và đào sâu phân tích này.")
    shallow_wall = "## Ý chính\n\n" + "Một câu đủ ý. " * 270

    failures = presentation_contract_violations(shallow_wall, contract)

    assert "below_explicit_heading_minimum" in failures
    assert "below_explicit_word_minimum" not in failures


async def test_contract_guard_repairs_once_and_revalidates():
    repaired = "- " + " ".join(["nội dung"] * 5) + "\n- " + " ".join(["kiểm chứng"] * 5)

    class Models:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(text=repaired)

    class Quota:
        def __init__(self):
            self.calls = 0

        def reserve(self, *args):
            self.calls += 1

    quota = Quota()
    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=Models())),
        quota=quota,
        user_message="Trả lời 20-30 từ bằng hai bullet.",
        answer="Quá ngắn.",
        model_name="gemini-3.5-flash-lite",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )
    assert result == repaired
    assert quota.calls == 1
    assert records[-1]["status"] == "corrected"


async def test_contract_guard_repairs_a_concise_answer_over_the_word_limit():
    repaired = "MCP là giao thức chuẩn giúp AI kết nối công cụ và nguồn dữ liệu."

    class Models:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(text=repaired)

    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=Models())),
        quota=SimpleNamespace(reserve=lambda *args: None),
        user_message="Hãy trả lời ngắn gọn MCP là gì.",
        answer=" ".join(["nội dung"] * 95),
        model_name="gemini-3.5-flash-lite",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )
    assert result == repaired
    assert records[-1]["status"] == "corrected"
    assert records[-1]["contract"] == "không quá 80 từ"


async def test_contract_guard_trims_trailing_sentences_when_concise_repair_is_still_long():
    first = "MCP là giao thức mở giúp AI kết nối công cụ và nguồn dữ liệu bên ngoài."
    repaired = first + " " + " ".join(["Chi tiết bổ sung."] * 40)

    class Models:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(text=repaired)

    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=Models())),
        quota=SimpleNamespace(reserve=lambda *args: None),
        user_message="Hãy trả lời ngắn gọn MCP là gì.",
        answer=" ".join(["nội dung"] * 95),
        model_name="gemini-3.5-flash-lite",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )

    assert result.startswith(first)
    assert len(result.split()) <= 80
    assert "Lưu ý về định dạng" not in result
    assert records[-1]["status"] == "corrected_locally"


async def test_contract_guard_can_honor_concise_limit_when_repair_quota_is_unavailable():
    answer = "MCP là giao thức mở giúp AI kết nối công cụ và nguồn dữ liệu bên ngoài. " + " ".join(
        ["Chi tiết bổ sung."] * 40
    )

    class NoQuota:
        def reserve(self, *args):
            raise RuntimeError("quota unavailable")

    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=None)),
        quota=NoQuota(),
        user_message="Hãy trả lời ngắn gọn MCP là gì.",
        answer=answer,
        model_name="gemini-3.5-flash-lite",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )

    assert result.startswith("MCP là giao thức mở")
    assert len(result.split()) <= 80
    assert "Lưu ý về định dạng" not in result
    assert records[-1]["status"] == "corrected_locally"
    assert records[-1]["repair_calls"] == 0


async def test_long_business_contract_compacts_locally_without_dropping_end_sections():
    answer = "\n\n".join(
        [
            "## Tóm tắt\n" + " ".join(["Tổng quan vận hành."] * 120),
            "## Rủi ro\n" + " ".join(["Rủi ro có điều kiện."] * 120),
            "## Chủ sở hữu\n" + " ".join(["Vai trò được đề xuất."] * 120),
            "## Bước kiểm tra tiếp theo\n" + " ".join(["Kiểm tra bằng chứng tiếp theo."] * 120),
        ]
    )
    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=None)),
        quota=SimpleNamespace(reserve=lambda *_args: (_ for _ in ()).throw(AssertionError())),
        user_message="Viết báo cáo 600-900 từ.",
        answer=answer,
        model_name="gemini-3.5-flash-lite",
        fallback_model="gemini-3.8-flash",
        records=records,
    )
    assert 600 <= len(result.split()) <= 900
    assert "## Rủi ro" in result
    assert "## Bước kiểm tra tiếp theo" in result
    assert records[-1]["status"] == "corrected_locally"
    assert records[-1]["reason"] == "section_preserving_compaction"


def test_compaction_never_cuts_an_action_mid_sentence():
    from app.agent.output_contract import _compact_markdown_sections

    action = "- Kiểm tra " + "toàn bộ lịch giao hàng và chứng từ vận tải " * 30 + "trước khi duyệt."
    original = "## Hành động\n\n" + action
    result = _compact_markdown_sections(original, 50)
    assert action in result
    assert "…" not in result


async def test_contract_guard_returns_best_effort_when_repair_still_invalid():
    class Models:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(text="Vẫn ngắn.")

    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=Models())),
        quota=SimpleNamespace(reserve=lambda *args: None),
        user_message="Trả lời 20-30 từ.",
        answer="Quá ngắn.",
        model_name="gemini-3.5-flash-lite",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )
    assert result.startswith("Vẫn ngắn.")
    assert "Lưu ý về định dạng" in result
    assert records[-1]["status"] == "degraded"


async def test_contract_guard_preserves_original_when_rewrite_drops_citation_marker():
    repaired = "- " + " ".join(["nội dung"] * 10) + "\n- " + " ".join(["kiểm chứng"] * 10)

    class Models:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(text=repaired)

    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=Models())),
        quota=SimpleNamespace(reserve=lambda *args: None),
        user_message="Trả lời 20-30 từ bằng hai bullet.",
        answer="Fact có nguồn [1].",
        model_name="gemini-3.5-flash-lite",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )
    assert result.startswith("Fact có nguồn [1].")
    assert "Lưu ý về định dạng" in result
    assert "citation_markers_changed" in records[-1]["violations"]


async def test_repair_504_uses_distinct_approved_model_and_reserves_second_call():
    repaired = "MCP là giao thức mở giúp AI kết nối công cụ và nguồn dữ liệu bên ngoài."

    class Models:
        def __init__(self):
            self.called = []

        async def generate_content(self, **kwargs):
            self.called.append(kwargs["model"])
            if len(self.called) == 1:
                raise errors.APIError(504, {"error": {"message": "provider timeout"}})
            return SimpleNamespace(text=repaired)

    class Quota:
        def __init__(self):
            self.calls = 0

        def reserve(self, *_args):
            self.calls += 1

    models = Models()
    quota = Quota()
    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=models)),
        quota=quota,
        user_message="Hãy trả lời ngắn gọn MCP là gì.",
        answer=" ".join(["nội dung"] * 95),
        model_name="gemini-3.8-flash",
        fallback_model="gemini-3.8-flash",
        records=records,
    )
    assert result == repaired
    assert models.called == ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
    assert quota.calls == 2
    assert records[-1]["status"] == "corrected"
    assert records[-1]["model"] == "gemini-3.5-flash-lite"


async def test_repair_504_does_not_bypass_quota_for_fallback():
    class Models:
        def __init__(self):
            self.calls = 0

        async def generate_content(self, **_kwargs):
            self.calls += 1
            raise errors.APIError(504, {"error": {"message": "provider timeout"}})

    class Quota:
        def __init__(self):
            self.calls = 0

        def reserve(self, *_args):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("local quota unavailable")

    models = Models()
    quota = Quota()
    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=models)),
        quota=quota,
        user_message="Hãy trả lời ngắn gọn MCP là gì.",
        answer=" ".join(["nội dung"] * 95),
        model_name="gemini-3.8-flash",
        fallback_model="gemini-3.8-flash",
        records=records,
    )
    assert models.calls == 1
    assert quota.calls == 2
    assert "Lưu ý về định dạng" in result
    assert records[-1]["fallback_blocked_by"] == "RuntimeError"


async def test_rewrite_cannot_add_numbers_or_drop_major_sections_to_pass_word_limit():
    original = (
        "## Dữ kiện\n\nKho có 100 sản phẩm.\n\n"
        "## Hành động\n\nKiểm tra đơn nhập trước khi đặt thêm. "
        + " ".join(["Lập báo cáo tồn kho."] * 40)
    )

    class Models:
        async def generate_content(self, **_kwargs):
            return SimpleNamespace(text="Dữ kiện: kho có 100 sản phẩm, sẽ nhập 550 sản phẩm.")

    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=Models())),
        quota=SimpleNamespace(reserve=lambda *_args: None),
        user_message="Hãy trả lời ngắn gọn về tình trạng kho.",
        answer=original,
        model_name="gemini-3.8-flash",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )
    assert result.startswith(original.strip())
    assert "550" not in result
    assert "numeric_claims_added" in records[-1]["violations"]
    assert "source_sections_dropped" in records[-1]["violations"]
    assert records[-1]["status"] == "degraded"


def test_numeric_rewrite_guard_normalizes_vietnamese_number_formatting():
    from app.agent.output_contract import _numeric_literals

    assert _numeric_literals("1.260 và 3,5") == _numeric_literals("1260 và 3.5")
    assert _numeric_literals("1.260") != _numeric_literals("1.260,5")


@pytest.mark.parametrize(("value", "accepted"), [("840", True), ("940", False)])
async def test_rewrite_only_allows_calculator_verified_new_numbers(value, accepted):
    original = "Kho có 100 sản phẩm. " + "Lập báo cáo kiểm tra tồn kho. " * 40

    class Models:
        async def generate_content(self, **kwargs):
            assert '"verified_calculations"' in kwargs["contents"]
            return SimpleNamespace(text=f"Tồn dự kiến {value} sản phẩm theo giả định đã nêu.")

    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=Models())),
        quota=SimpleNamespace(reserve=lambda *_args: None),
        user_message="Trả lời ngắn gọn về kho.", answer=original,
        model_name="gemini-3.5-flash-lite", fallback_model="gemini-3.8-flash", records=records,
        verified_calculations={"ending_stock": "840"},
    )
    if accepted:
        assert result.startswith("Tồn dự kiến 840")
        assert records[-1]["status"] == "corrected"
    else:
        assert result.startswith(original.rstrip())
        assert "numeric_claims_added" in records[-1]["violations"]


async def test_max_token_rewrite_is_not_marked_complete_even_if_word_count_passes():
    original = " ".join(["Nguồn đã ghi nhận. "] * 100)

    class Models:
        async def generate_content(self, **_kwargs):
            return SimpleNamespace(
                text="Nguồn đã ghi nhận.",
                candidates=[SimpleNamespace(finish_reason=types.FinishReason.MAX_TOKENS)],
            )

    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=Models())),
        quota=SimpleNamespace(reserve=lambda *_args: None),
        user_message="Hãy trả lời ngắn gọn về nguồn.",
        answer=original,
        model_name="gemini-3.8-flash",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )
    assert result.startswith(original.strip())
    assert "rewrite_truncated" in records[-1]["violations"]


async def test_explicit_actions_and_triggers_cannot_disappear_from_a_valid_length():
    class Models:
        async def generate_content(self, **_kwargs):
            return SimpleNamespace(
                text="Bản phân tích có số liệu và giải thích nhưng không có việc cần làm."
            )

    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=Models())),
        quota=SimpleNamespace(reserve=lambda *_args: None),
        user_message="Trả lời ngắn gọn, đề xuất hành động khả thi và trigger định lượng.",
        answer=" ".join(["Phân tích"] * 100),
        model_name="gemini-3.8-flash",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )
    assert "Lưu ý về định dạng" in result
    assert "missing_action_section" in records[-1]["violations"]
    assert records[-1]["status"] == "degraded"


async def test_action_and_trigger_request_without_format_contract_is_not_false_pass():
    class Models:
        async def generate_content(self, **_kwargs):
            raise AssertionError("No extra Gemini call should be made")

    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=Models())),
        quota=SimpleNamespace(reserve=lambda *_args: None),
        user_message="Đề xuất hành động khả thi và trigger định lượng cho kho.",
        answer="Kho cuối ngày là 840 đơn vị, cao hơn mức đệm.",
        model_name="gemini-3.8-flash",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )
    assert result.startswith("Kho cuối ngày là 840 đơn vị")
    assert "Lưu ý về định dạng" in result
    assert records[-1]["status"] == "degraded"
    assert records[-1]["violations"] == ["missing_action_section"]
    assert records[-1]["repair_calls"] == 0


async def test_action_and_trigger_request_without_format_contract_can_pass():
    answer = "## Hành động và trigger\n- Nếu tồn kho dưới 600, đặt thêm hàng."
    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=None)),
        quota=SimpleNamespace(reserve=lambda *_args: None),
        user_message="Đề xuất hành động khả thi và trigger định lượng cho kho.",
        answer=answer,
        model_name="gemini-3.8-flash",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )
    assert result == answer
    assert records == []


async def test_action_gate_does_not_borrow_a_trigger_from_later_analysis():
    answer = (
        "## Hành động và trigger\n- Theo dõi tồn kho.\n"
        "## Phân tích\n- Nếu tồn kho dưới 600, nhu cầu có thể tăng."
    )
    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=None)),
        quota=SimpleNamespace(reserve=lambda *_args: None),
        user_message="Đề xuất hành động khả thi và trigger định lượng cho kho.",
        answer=answer,
        model_name="gemini-3.8-flash",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )
    assert result.startswith(answer)
    assert records[-1]["violations"] == ["missing_action_section"]


async def test_action_gate_uses_real_action_section_after_short_recommendation_heading():
    answer = (
        "## Khuyến nghị ngắn\nKho cần được theo dõi.\n"
        "## Hành động và trigger\n- Nếu tồn kho dưới 600, đặt thêm hàng.\n"
        "## Phân tích\nDữ kiện khác cần kiểm chứng."
    )
    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=None)),
        quota=SimpleNamespace(reserve=lambda *_args: None),
        user_message="Đề xuất hành động khả thi và trigger định lượng cho kho.",
        answer=answer,
        model_name="gemini-3.8-flash",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )
    assert result == answer
    assert records == []


async def test_action_gate_requires_a_quantified_condition_in_an_action_bullet():
    answer = "## Hành động và trigger\n- Nếu thấy rủi ro, kiểm tra kho."
    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=None)),
        quota=SimpleNamespace(reserve=lambda *_args: None),
        user_message="Đề xuất hành động khả thi và trigger định lượng cho kho.",
        answer=answer,
        model_name="gemini-3.8-flash",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )
    assert result.startswith(answer)
    assert records[-1]["violations"] == ["missing_action_section"]


async def test_rewrite_without_actions_cannot_replace_an_actionable_draft():
    original = (
        "## Hành động và trigger\n- Nếu tồn kho dưới 600, đặt thêm hàng.\n"
        + " ".join(["Phân tích"] * 100)
    )

    class Models:
        async def generate_content(self, **_kwargs):
            return SimpleNamespace(text="## Tổng quan\nKho cần được theo dõi.")

    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=Models())),
        quota=SimpleNamespace(reserve=lambda *_args: None),
        user_message="Trả lời ngắn gọn, đề xuất hành động khả thi và trigger định lượng.",
        answer=original,
        model_name="gemini-3.8-flash",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )
    assert result.startswith(original)
    assert "missing_action_section" in records[-1]["violations"]


async def test_explicit_wrong_number_comparison_is_not_marked_complete():
    answer = "Tồn kho 1.650 đơn vị vượt mức 2.100 đơn vị."
    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=None)),
        quota=SimpleNamespace(reserve=lambda *_args: None),
        user_message="Kiểm tra tình trạng tồn kho.",
        answer=answer,
        model_name="gemini-3.8-flash",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )
    assert result.startswith(answer)
    assert "Lưu ý về định dạng" in result
    assert records[-1]["violations"] == ["numeric_comparison_inconsistent"]
    assert records[-1]["status"] == "degraded"
    assert records[-1]["repair_calls"] == 0


async def test_repair_cannot_introduce_wrong_comparison_with_existing_numbers():
    original = " ".join(["Kho 1.650 đơn vị, ngưỡng 2.100 đơn vị."] * 16)

    class Models:
        async def generate_content(self, **_kwargs):
            return SimpleNamespace(text="Kho 1.650 đơn vị vượt ngưỡng 2.100 đơn vị.")

    records = []
    result = await enforce_presentation_contract(
        client=SimpleNamespace(aio=SimpleNamespace(models=Models())),
        quota=SimpleNamespace(reserve=lambda *_args: None),
        user_message="Hãy trả lời ngắn gọn về tồn kho.",
        answer=original,
        model_name="gemini-3.8-flash",
        fallback_model="gemini-3.5-flash-lite",
        records=records,
    )
    assert result.startswith(original)
    assert "numeric_comparison_inconsistent" in records[-1]["violations"]


async def test_correct_numeric_comparisons_and_different_scale_are_not_flagged():
    correct = "Kho 1.650 thấp hơn 2.100; 3.5 lớn hơn 2.1."
    different_scale = "2 triệu lớn hơn 500 nghìn."
    different_dimensions = "Có 18 trường hợp đã vượt ngưỡng thời gian xử lý 48 giờ."
    labelled_metric = "Nếu Day-1 Churn tiếp tục tăng vượt mức 6,0%, hãy dừng chiến dịch."
    duration = "Lượng tiêu thụ tích lũy 2 tuần đầu vượt 1.040 chiếc."
    delta = "Safety stock 250 chiếc, phần đệm hiện tại cao hơn mức an toàn là 590 chiếc."
    for answer in (correct, different_scale, different_dimensions,
                   labelled_metric, duration, delta):
        records = []
        result = await enforce_presentation_contract(
            client=SimpleNamespace(aio=SimpleNamespace(models=None)),
            quota=SimpleNamespace(reserve=lambda *_args: None),
            user_message="Kiểm tra tình trạng tồn kho.",
            answer=answer,
            model_name="gemini-3.8-flash",
            fallback_model="gemini-3.5-flash-lite",
            records=records,
        )
        assert result == answer
        assert records == []
