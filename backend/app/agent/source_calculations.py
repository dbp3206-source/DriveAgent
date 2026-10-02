"""Bounded arithmetic for source-backed synthesis; no extra model loop or writes."""

import re

from pydantic import Field

from app.agent.creation import WireAnswer
from app.tools.calculator import CalculateInput, calculate
from app.tools.contracts import ToolContext


class CalculatedWireAnswer(WireAnswer):
    expressions: list[str] = Field(min_length=1, max_length=12)

    @staticmethod
    def provider_schema() -> dict:
        schema = WireAnswer.provider_schema()
        schema["properties"]["expressions"] = {
            "type": "array", "minItems": 1, "maxItems": 12,
            "items": {"type": "string", "maxLength": 300},
        }
        schema["required"].append("expressions")
        return schema


def needs_source_calculation(request: str, *, has_evidence: bool, output: str) -> bool:
    return bool(has_evidence and output == "chat" and re.search(
        r"\b(?:tính(?:\s+lại)?\s+bằng\s+công\s+cụ|"
        r"(?:gọi|dùng|sử dụng)\s+(?:công\s+cụ\s+)?calculate)\b", request, re.I
    ))


def validate_calculation_payload(raw: str) -> CalculatedWireAnswer:
    wire = CalculatedWireAnswer.model_validate_json(raw)
    indices = set(re.findall(r"\{\{calc:(\d+)\}\}", wire.answer))
    remainder = re.sub(r"\{\{calc:\d+\}\}", "", wire.answer)
    if indices != {str(i) for i in range(len(wire.expressions))} or "{{calc" in remainder:
        raise ValueError("calculation_reference_mismatch")
    # Validate every expression before any tool executes. This parser cannot
    # run code, follow document instructions, or access external resources.
    calculate(CalculateInput(operation="expressions", values=wire.expressions))
    if wire.proposals:
        raise ValueError("calculation_chat_must_not_prepare_writes")
    return wire


async def resolve_calculations(wire, registry, context: ToolContext, trace: list) -> WireAnswer:
    result = await registry.execute(
        "calculate", {"operation": "expressions", "values": wire.expressions}, context
    )
    if len(result.results) != len(wire.expressions):
        raise ValueError("calculation_result_count_mismatch")
    answer = wire.answer
    for index, value in enumerate(result.results):
        answer = answer.replace("{{calc:" + str(index) + "}}", value)
    trace.append({"stage": "tool", "tool": "calculate", "status": "success"})
    return WireAnswer(answer=answer, proposals=[])
