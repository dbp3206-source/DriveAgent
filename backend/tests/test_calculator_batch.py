import pytest

from app.tools.calculator import CalculateInput, calculate
from app.tools.contracts import ToolError


def test_batch_computes_business_scenario_in_order():
    output = calculate(CalculateInput(operation="expressions", values=[
        "24*12*20/60", "24*12*20/60*0.25", "24*12*20/60*(1-0.25)",
    ], unit="giờ"))
    assert output.results == ["96", "24.00", "72.00"]
    assert output.count == 3


@pytest.mark.parametrize("values", [["1"] * 17, ["1+1", "1/0"], ["__import__('os')"]])
def test_batch_rejects_unsafe_or_excessive_input(values):
    with pytest.raises(ToolError):
        calculate(CalculateInput(operation="expressions", values=values))


def test_single_expression_contract_is_unchanged():
    assert calculate(CalculateInput(operation="expression", values=["2+2"])).result == "4"
    with pytest.raises(ToolError):
        calculate(CalculateInput(operation="expression", values=["2+2", "3+3"]))
