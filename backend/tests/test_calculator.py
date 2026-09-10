import pytest

from app.tools.calculator import CalculateInput, calculate
from app.tools.contracts import ToolError


@pytest.mark.parametrize(
    ("op", "values", "expected"),
    [
        ("sum", ["0.1", "0.2"], "0.3"),
        ("mean", ["2", "4"], "3"),
        ("percent", ["3", "12"], "25.00"),
        ("subtract", ["3", "8"], "-5"),
        ("multiply", ["2", "3", "4"], "24"),
        ("min", ["-2", "3"], "-2"),
        ("max", ["-2", "3"], "3"),
        ("divide", ["8", "2"], "4"),
    ],
)
def test_calculate(op, values, expected):
    assert calculate(CalculateInput(operation=op, values=values)).result == expected


@pytest.mark.parametrize("value", ["NaN", "Infinity", "__import__('os')", "1e99999", "1,000"])
def test_reject_invalid_numbers(value):
    with pytest.raises(ToolError):
        calculate(CalculateInput(operation="sum", values=[value]))


def test_zero_division_and_operand_count():
    for values in (["1", "0"], ["1"]):
        with pytest.raises(ToolError):
            calculate(CalculateInput(operation="divide", values=values))
