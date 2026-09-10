"""Tính toán có giới hạn: không eval, không shell, không biểu thức tùy ý."""

from decimal import Decimal, InvalidOperation, localcontext
from typing import Literal

from pydantic import BaseModel, Field

from app.auth.permissions import DRIVE_READ
from app.tools.contracts import ToolContext, ToolDefinition, ToolError


class CalculateInput(BaseModel):
    operation: Literal["sum", "mean", "min", "max", "subtract", "multiply", "divide", "percent"]
    values: list[str] = Field(min_length=1, max_length=1000)
    unit: str = Field(default="", max_length=40)


class CalculateOutput(BaseModel):
    result: str
    operation: str
    count: int
    unit: str
    explanation: str


def calculate(payload: CalculateInput) -> CalculateOutput:
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
                "Không đoán số thiếu. values là danh sách chuỗi số, percent=a/b*100."
            ),
            input_model=CalculateInput,
            output_model=CalculateOutput,
            handler=handler,
            required_permissions={DRIVE_READ},
            max_attempts=1,
        )
    ]
