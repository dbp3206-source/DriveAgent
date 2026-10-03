import pytest

from app.tools.calculator import CalculateInput, calculate
from app.tools.contracts import ToolError


@pytest.mark.parametrize(("values", "expected"), [
    (["2026-04-29", "2026-05-04"], "5"),
    (["2024-02-28", "2024-03-01"], "2"),
    (["2026-01-01", "2025-12-31"], "-1"),
    (["2026-10-03", "2026-10-03"], "0"),
])
def test_calendar_difference(values, expected):
    result = calculate(CalculateInput(operation="date_difference", values=values))
    assert result.result == expected
    assert result.unit == "ngày"
    assert "không phải số ngày làm việc" in result.explanation


@pytest.mark.parametrize("values", [
    ["2026-02-29", "2026-03-01"],
    ["29/04/2026", "04/05/2026"],
    ["2026-04-29"],
    ["2026-04-29T00:00:00", "2026-05-04"],
])
def test_invalid_dates_are_not_guessed(values):
    with pytest.raises(ToolError):
        calculate(CalculateInput(operation="date_difference", values=values))


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


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("(125.5 + 24.5) / 3", "50.0"),
        ("2 + 3 * 4", "14"),
        ("-(2 + 3) * 4", "-20"),
    ],
)
def test_safe_arithmetic_expression(expression, expected):
    assert calculate(CalculateInput(operation="expression", values=[expression])).result == expected


@pytest.mark.parametrize("expression", ["1/0", "__import__('os')", "(1+2", "1 2", ""])
def test_rejects_unsafe_or_invalid_expression(expression):
    with pytest.raises(ToolError):
        calculate(CalculateInput(operation="expression", values=[expression]))
