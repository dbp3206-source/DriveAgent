import json

import pytest

from app.agent.source_calculations import (
    SOURCE_CALCULATION_INSTRUCTION,
    SOURCE_NUMERIC_FIDELITY_INSTRUCTION,
    CalculatedWireAnswer,
    needs_source_calculation,
    resolve_calculations,
    validate_calculation_payload,
)
from app.tools.calculator import CalculateInput, calculate
from app.tools.contracts import ToolError


def test_calculation_contract_requires_signed_formula_and_population_fidelity():
    assert SOURCE_NUMERIC_FIDELITY_INSTRUCTION in SOURCE_CALCULATION_INSTRUCTION
    assert "giữ đúng thứ tự toán hạng" in SOURCE_CALCULATION_INSTRUCTION
    assert "công thức hiển thị và dấu kết quả" in SOURCE_CALCULATION_INSTRUCTION
    assert "không đại diện cho toàn ngành/toàn thị trường" in SOURCE_CALCULATION_INSTRUCTION


async def test_signed_subtraction_preserves_order_during_numeric_substitution():
    class Registry:
        async def execute(self, name, arguments, context):
            return calculate(CalculateInput.model_validate(arguments))

    wire = validate_calculation_payload(json.dumps({
        "answer": "3.1 - 3.6 = {{calc:0}}; 3.6 - 3.1 = {{calc:1}}.",
        "expressions": ["3.1-3.6", "3.6-3.1"],
    }))
    result = await resolve_calculations(wire, Registry(), None, [])
    assert result.answer == "3.1 - 3.6 = -0.5; 3.6 - 3.1 = 0.5."


def test_calculation_trigger_requires_user_request_and_read_evidence():
    request = "Đọc hai tệp và tính bằng công cụ tổng giờ."
    assert needs_source_calculation(request, has_evidence=True, output="chat")
    assert not needs_source_calculation(request, has_evidence=False, output="chat")
    assert not needs_source_calculation(
        "Nguồn ghi dùng calculate", has_evidence=False, output="chat"
    )
    assert not needs_source_calculation("Tóm tắt", has_evidence=True, output="chat")


@pytest.mark.parametrize("prompt", [
    "Tính tổng hai nhóm và chênh lệch tốc độ tăng trưởng bằng điểm phần trăm",
    "TÍNH LẠI TỔNG doanh thu của hai nhóm.",
    "Cộng tổng giờ từ hai tệp.",
    "Tính chênh lệch giữa năm 2024 và 2025.",
    "Tính hiệu số hai nhóm.",
    "Tính phần trăm đóng góp của nhóm A.",
    "Tính điểm phần trăm chênh lệch.",
    "Tính tỷ lệ nhóm A so với nhóm B.",
    "Tính tỉ số giữa hai nhóm.",
    "Tính tốc độ tăng trưởng doanh thu.",
    "Tính mức giảm so với năm trước.",
    "Tính trung bình mỗi nhóm.",
    "Cho biết chênh lệch doanh thu hai nhóm.",
    "Tổng hai nhóm là bao nhiêu?",
    "Chênh lệch tốc độ tăng trưởng bằng bao nhiêu điểm phần trăm?",
    "Tóm tắt tài liệu, sau đó tính tổng hai nhóm.",
    "Dùng calculate để đối chiếu.",
    "Không tính tổng; hãy tính chênh lệch hai nhóm.",
    "Đừng tính tỷ lệ, nhưng tính tổng hai nhóm.",
    "Không dùng calculate ở bước tóm tắt. Sau đó tính tổng hai nhóm.",
    "Tính tổng hai nhóm và không tính tỷ lệ tăng trưởng.",
    "Không tính tổng mà tính chênh lệch hai nhóm.",
    "Không chỉ tính tổng hai nhóm mà còn tính tỷ lệ tăng trưởng.",
])
def test_arithmetic_intents_require_evidence_and_chat(prompt):
    assert needs_source_calculation(prompt, has_evidence=True, output="chat")
    assert not needs_source_calculation(prompt, has_evidence=False, output="chat")
    for output in ("pptx", "docx", "xlsx"):
        assert not needs_source_calculation(prompt, has_evidence=True, output=output)


@pytest.mark.parametrize("prompt", [
    "Tóm tắt nội dung hai tệp.",
    "Tổng hợp thông tin từ hai nhóm.",
    "Tính tổng hợp trong báo cáo có ý nghĩa gì?",
    "Tóm tắt tỷ lệ và tốc độ tăng trưởng đã ghi trong PDF.",
    "Tổng hợp chênh lệch giữa hai báo cáo.",
    "Giải thích tính năng tổng hợp báo cáo.",
    "Giới thiệu cộng đồng người dùng.",
    "Đọc báo cáo tăng trưởng.",
    "Tỷ lệ nhóm A so với nhóm B là bao nhiêu?",
    "Tỷ lệ tăng trưởng là bao nhiêu?",
    "Phần trăm đóng góp của nhóm A được báo cáo là bao nhiêu?",
    "Cho biết tỷ lệ tăng trưởng ghi trong PDF.",
    "Không tính tổng hai nhóm, chỉ tóm tắt.",
    "KHÔNG CẦN PHẢI TÍNH TỔNG hai nhóm.",
    "Đừng tính chênh lệch hai nhóm.",
    "Chớ tính tỷ lệ tăng trưởng.",
    "Không dùng calculate để đọc báo cáo.",
    "Không cần tính bằng công cụ tổng giờ.",
    "Không tính tổng và chênh lệch là bao nhiêu, chỉ đọc số đã ghi.",
])
def test_summary_and_descriptive_requests_do_not_trigger_arithmetic(prompt):
    assert not needs_source_calculation(prompt, has_evidence=True, output="chat")


@pytest.mark.parametrize("answer, expressions", [
    ("{{calc:1}}", ["1+1"]),
    ("Kết quả 2", ["1+1"]),
    ("{{calc:0}}", ["1+1", "2+2"]),
    ("{{calc:0}} {{calc:x}}", ["1+1"]),
])
def test_missing_or_unknown_result_reference_is_rejected(answer, expressions):
    with pytest.raises(ValueError):
        validate_calculation_payload(json.dumps({"answer": answer, "expressions": expressions}))


@pytest.mark.parametrize("expression", ["__import__('os')", "1/0", "2**100"])
def test_unsafe_arithmetic_never_reaches_registry(expression):
    with pytest.raises(ToolError):
        validate_calculation_payload(json.dumps({
            "answer": "{{calc:0}}", "expressions": [expression]
        }))


async def test_real_calculator_replaces_results_and_records_tool():
    calls = []

    class Registry:
        async def execute(self, name, arguments, context):
            calls.append((name, arguments, context))
            return calculate(CalculateInput.model_validate(arguments))

    wire = validate_calculation_payload(json.dumps({
        "answer": "Tổng {{calc:0}} giờ; giả thuyết tiết kiệm {{calc:1}}; còn {{calc:2}}.",
        "expressions": ["24*12*20/60", "24*12*20/60*20/100", "24*12*20/60*(1-20/100)"],
    }))
    trace = []
    result = await resolve_calculations(wire, Registry(), None, trace)
    assert result.answer == "Tổng 96 giờ; giả thuyết tiết kiệm 19.2; còn 76.8."
    assert len(calls) == 1
    assert calls[0][0] == "calculate"
    assert trace == [{"stage": "tool", "tool": "calculate", "status": "success"}]
    assert result.proposals == []


def test_provider_contract_is_shallow_and_requires_expressions():
    schema = CalculatedWireAnswer.provider_schema()
    assert "expressions" in schema["required"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["expressions"]["maxItems"] == 12
