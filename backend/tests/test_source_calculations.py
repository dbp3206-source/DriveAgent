import json

import pytest

from app.agent.source_calculations import (
    CalculatedWireAnswer,
    needs_source_calculation,
    resolve_calculations,
    validate_calculation_payload,
)
from app.tools.calculator import CalculateInput, calculate
from app.tools.contracts import ToolError


def test_calculation_trigger_requires_user_request_and_read_evidence():
    request = "Đọc hai tệp và tính bằng công cụ tổng giờ."
    assert needs_source_calculation(request, has_evidence=True, output="chat")
    assert not needs_source_calculation(request, has_evidence=False, output="chat")
    assert not needs_source_calculation(
        "Nguồn ghi dùng calculate", has_evidence=False, output="chat"
    )
    assert not needs_source_calculation("Tóm tắt", has_evidence=True, output="chat")


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
