"""Tính toán có giới hạn: không eval, không shell, không biểu thức tùy ý."""

import re
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation, localcontext
from typing import Literal

from pydantic import BaseModel, Field

from app.auth.permissions import DRIVE_READ
from app.tools.contracts import ToolContext, ToolDefinition, ToolError


class CalculateInput(BaseModel):
    operation: Literal[
        "sum", "mean", "min", "max", "subtract", "multiply", "divide", "percent", "expression",
        "expressions",
    ]
    values: list[str] = Field(min_length=1, max_length=1000)
    unit: str = Field(default="", max_length=40)


class CalculateOutput(BaseModel):
    result: str
    operation: str
    count: int
    unit: str
    explanation: str
    results: list[str] = Field(default_factory=list)


_EXPRESSION_TOKEN = re.compile(r"\s*(?:(\d+(?:\.\d+)?)|([()+\-*/]))")


def _expression_tokens(source: str) -> list[str]:
    if len(source) > 300:
        raise ToolError("Biểu thức quá dài.", code="expression_too_long")
    tokens: list[str] = []
    position = 0
    while position < len(source):
        match = _EXPRESSION_TOKEN.match(source, position)
        if not match:
            raise ToolError(
                "Biểu thức chỉ hỗ trợ số, ngoặc và + - * /.", code="invalid_expression"
            )
        tokens.append(match.group(1) or match.group(2))
        position = match.end()
    if not tokens or len(tokens) > 100:
        raise ToolError("Biểu thức trống hoặc quá phức tạp.", code="invalid_expression")
    return tokens


def _safe_expression(source: str) -> Decimal:
    """Evaluate a tiny arithmetic grammar without Python ``eval`` or code execution."""

    tokens = _expression_tokens(source)
    stream: Iterator[str] = iter(tokens)
    current: str | None = next(stream, None)

    def advance() -> str | None:
        nonlocal current
        old, current = current, next(stream, None)
        return old

    def factor() -> Decimal:
        if current in {"+", "-"}:
            sign = advance()
            value = factor()
            return value if sign == "+" else -value
        if current == "(":
            advance()
            value = expression()
            if current != ")":
                raise ToolError("Ngoặc trong biểu thức chưa khớp.", code="invalid_expression")
            advance()
            return value
        token = advance()
        if token is None or not re.fullmatch(r"\d+(?:\.\d+)?", token):
            raise ToolError("Thiếu số trong biểu thức.", code="invalid_expression")
        return Decimal(token)

    def term() -> Decimal:
        value = factor()
        while current in {"*", "/"}:
            operator = advance()
            right = factor()
            if operator == "/" and right == 0:
                raise ToolError("Không thể chia cho 0.", code="division_by_zero")
            value = value * right if operator == "*" else value / right
        return value

    def expression() -> Decimal:
        value = term()
        while current in {"+", "-"}:
            operator = advance()
            right = term()
            value = value + right if operator == "+" else value - right
        return value

    with localcontext() as ctx:
        ctx.prec = 28
        result = expression()
    if current is not None:
        raise ToolError("Biểu thức có ký hiệu thừa.", code="invalid_expression")
    if not result.is_finite() or abs(result.adjusted()) > 1000:
        raise ToolError("Kết quả vượt giới hạn tính toán.", code="number_too_large")
    return result


def calculate(payload: CalculateInput) -> CalculateOutput:
    if payload.operation == "expressions":
        if len(payload.values) > 16:
            raise ToolError("Mỗi lượt chỉ tính tối đa 16 biểu thức.", code="invalid_operands")
        results = [format(_safe_expression(value), "f") for value in payload.values]
        return CalculateOutput(
            result="; ".join(results), results=results, operation="expressions",
            count=len(results), unit=payload.unit,
            explanation="Kết quả theo đúng thứ tự biểu thức; dùng Decimal, không chạy mã tùy ý.",
        )
    if payload.operation == "expression":
        if len(payload.values) != 1:
            raise ToolError("Biểu thức cần đúng một chuỗi đầu vào.", code="invalid_operands")
        result = _safe_expression(payload.values[0])
        return CalculateOutput(
            result=format(result, "f"),
            operation="expression",
            count=1,
            unit=payload.unit,
            explanation="Tính theo thứ tự ngoặc, nhân/chia, cộng/trừ bằng Decimal.",
        )
    numbers = []
    for raw in payload.values:
        try:
            if len(raw) > 80:
                raise ValueError
            number = Decimal(raw)
            if not number.is_finite() or abs(number.adjusted()) > 100:
                raise ValueError
            numbers.append(number)
        except (InvalidOperation, ValueError) as exc:
            raise ToolError(
                "Chỉ nhận số hữu hạn; dùng dấu chấm cho phần thập phân.", code="invalid_number"
            ) from exc
    op = payload.operation
    if op in {"subtract", "divide", "percent"} and len(numbers) != 2:
        raise ToolError("Phép tính này cần đúng hai số.", code="invalid_operands")
    with localcontext() as ctx:
        ctx.prec = 28
        if op in {"divide", "percent"} and numbers[1] == 0:
            raise ToolError("Không thể chia cho 0.", code="division_by_zero")
        if op == "sum":
            result = sum(numbers)
        elif op == "mean":
            result = sum(numbers) / len(numbers)
        elif op == "min":
            result = min(numbers)
        elif op == "max":
            result = max(numbers)
        elif op == "subtract":
            result = numbers[0] - numbers[1]
        elif op == "multiply":
            result = Decimal(1)
            for number in numbers:
                result *= number
                if abs(result.adjusted()) > 1000:
                    raise ToolError("Kết quả vượt giới hạn tính toán.", code="number_too_large")
        else:
            result = numbers[0] / numbers[1] * (100 if op == "percent" else 1)
    return CalculateOutput(
        result=format(result, "f"),
        operation=op,
        count=len(numbers),
        unit="%" if op == "percent" else payload.unit,
        explanation="Tính bằng Decimal, tối đa 28 chữ số có nghĩa; percent = a/b×100.",
    )


async def handler(payload: CalculateInput, _context: ToolContext) -> CalculateOutput:
    return calculate(payload)


def calculator_tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="calculate",
            description=(
                "Tính tổng/trung bình/min/max/trừ/nhân/chia/tỷ lệ từ số đã biết. "
                "Hỗ trợ biểu thức số học an toàn bằng operation=expression và một chuỗi "
                "trong values. Không đoán số thiếu; percent=a/b*100."
                " Khi cần nhiều kết quả từ số có sẵn, dùng operation=expressions và "
                "values gồm tối đa 16 biểu thức độc lập để tính cùng một lượt."
            ),
            input_model=CalculateInput,
            output_model=CalculateOutput,
            handler=handler,
            required_permissions={DRIVE_READ},
            max_attempts=1,
        )
    ]
