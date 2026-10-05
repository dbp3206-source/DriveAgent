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
    if not has_evidence or output != "chat":
        return False
    # Match arithmetic requests, not the "tổng" in "tổng hợp" or the
    # "tính" in "tính năng". Keep the existing evidence/output gates so
    # broader wording still uses only the bounded source calculation route.
    aggregate_term = r"(?:tổng\b(?!\s+hợp\b)|chênh\s+lệch|hiệu\s+số)"
    arithmetic_term = (
        r"(?:" + aggregate_term + r"|"
        r"(?:điểm\s+)?phần\s+trăm|t[ỷỉ]\s+(?:lệ|số)|"
        r"tốc\s+độ\s+tăng\s+trưởng|mức\s+(?:tăng|giảm)|"
        r"trung\s+bình|bình\s+quân)"
    )
    computing_verb = r"(?:tính(?:\s+(?:toán|lại))?|cộng|trừ|nhân|chia|xác\s+định)"
    # Percentages and ratios may already be reported in a source. Merely
    # asking what they are must not force new arithmetic without a compute verb.
    arithmetic_request = (
        r"\b" + computing_verb + r"\s+" + arithmetic_term + r"\b|"
        r"\bcho\s+biết\s+" + aggregate_term + r"\b|"
        r"\b" + aggregate_term + r"\b[^.!?\n]{0,80}\bbao\s+nhiêu\b"
    )
    explicit_tool_request = (
        r"\b(?:tính(?:\s+lại)?\s+bằng\s+công\s+cụ|"
        r"(?:gọi|dùng|sử dụng)\s+(?:công\s+cụ\s+)?calculate)\b"
    )
    prohibition = (
        r"\b(?:không(?!\s+chỉ\b)|đừng|chớ|tránh)\s+"
        r"(?:(?:cần|phải|được|nên|thể)\s+)*"
        r"(?:" + computing_verb + r"|gọi|dùng|sử\s+dụng|cho\s+biết)\b"
    )
    # Negation applies to its clause, so a separate positive calculation
    # request still runs ("không tính tổng; tính chênh lệch").
    clauses = re.split(
        r"[.!?;,\n]+|\b(?:nhưng|còn|sau\s+đó|mà)\b|"
        r"\bvà\s+(?=(?:hãy\s+)?(?:không|đừng|" + computing_verb + r")\b)",
        request, flags=re.I,
    )
    return any(
        not re.search(prohibition, clause, re.I)
        and re.search(explicit_tool_request + "|" + arithmetic_request, clause, re.I)
        for clause in clauses
    )


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
