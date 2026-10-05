"""Bounded arithmetic for source-backed synthesis; no extra model loop or writes."""

import re

from pydantic import Field

from app.agent.creation import WireAnswer
from app.tools.calculator import CalculateInput, calculate
from app.tools.contracts import ToolContext

SOURCE_NUMERIC_FIDELITY_INSTRUCTION = (
    "Giữ nguyên phạm vi và tập mẫu của từng số liệu: nhóm được theo dõi, khảo sát "
    "hoặc lựa chọn không đại diện cho toàn ngành/toàn thị trường; giữ điều kiện chọn mẫu. "
    "Giữ đơn vị trong đúng phạm vi nguồn xác định, giới hạn đơn vị chưa rõ, "
    "kỳ số liệu, ngày nguồn và trạng thái dự báo/kế hoạch/ước tính/thực tế. "
    "Phép trừ có dấu phải giữ đúng thứ tự toán hạng; công thức hiển thị và dấu kết quả "
    "phải khớp biểu thức tính. Khi trình bày độ lớn chênh lệch dương, ghi rõ đó là "
    "độ lớn và đối tượng nào cao hơn/thấp hơn; không gán độ lớn dương cho phép trừ "
    "có kết quả âm. Không đổi thứ tự toán hạng, dấu, công thức hoặc phạm vi khi diễn đạt lại. "
    "Đây là yêu cầu bảo toàn nội dung; công cụ số học không xác minh phạm vi nguồn."
)

SOURCE_CALCULATION_INSTRUCTION = (
    "\nYêu cầu tính bằng công cụ: trả expressions gồm tối đa 12 biểu thức số "
    "chỉ dùng + - * / và ngoặc, mỗi biểu thức tối đa 300 ký tự. "
    "Chọn số từ dữ kiện đã đọc và thay đổi người dùng, tôn trọng bản sửa mới nhất. "
    "Nêu căn cứ, đơn vị, giả thuyết; không tự tạo đầu vào. "
    "Trước khi cộng/trừ hoặc so sánh, đối chiếu chỉ tiêu, kỳ, trạng thái dự báo/thực tế "
    "và đơn vị của từng đầu vào. Chỉ gắn đơn vị cho tổng/chênh lệch khi nguồn xác định "
    "đơn vị tương thích cho tất cả đầu vào; quy đổi phải nêu căn cứ. Nếu nguồn chưa "
    "xác định đơn vị của một đầu vào, chỉ trình bày phép tính trên các con số như nguồn, "
    "không gắn đơn vị suy đoán và nói rõ chưa thể xác nhận tổng/chênh lệch cùng đơn vị. "
    "Đơn vị đã xác định riêng cho một đầu vào vẫn được nêu tại đầu vào đó. "
    "Nếu nguồn xác định các đơn vị/kỳ không tương thích, không coi tổng/chênh lệch "
    "là một đại lượng có ý nghĩa; nêu giới hạn và chỉ tính các phần tương thích. "
    "Phân biệt % với điểm phần trăm; kết quả giữ trạng thái dự báo/kế hoạch/ước tính "
    "của đầu vào và nêu ngày nguồn nếu có. Công cụ chỉ kiểm tra số học, "
    "không xác minh đơn vị hay ý nghĩa dữ liệu. "
    + SOURCE_NUMERIC_FIDELITY_INSTRUCTION
    + " "
    "Trong answer thay mọi kết quả tính bằng {{calc:0}}, {{calc:1}}, ... "
    "theo chỉ số expressions. Mỗi biểu thức phải được tham chiếu. "
    "Không tự điền kết quả, không tuyên bố công cụ đã chạy; máy chủ sẽ tính "
    "và thay kết quả trước khi trả lời. proposals phải rỗng."
)


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
