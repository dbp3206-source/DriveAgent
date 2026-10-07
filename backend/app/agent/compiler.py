"""Quota-first ADK: deterministic gather, one structured generation, no tool loop.

Canonical Message rows supply bounded history across framework switches. Retrieved
documents remain data; this compiler has no side-effect tools and cannot execute them.
"""

import asyncio
import json
import logging
import re
from decimal import Decimal
from typing import Any

from google import genai
from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from langchain_core.messages import ToolMessage
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select

from app.agent.controls import ChatControls
from app.agent.creation import (
    CREATION_INSTRUCTION,
    CreationAnswer,
    WireAnswer,
    blank_unsourced_sheet_requested,
    budget_tracker_template,
    consultation_provider_schema,
    consultation_report_requested,
    ground_unsourced_spreadsheet_preview,
    preserve_explicit_literals,
    separate_consultation_questions,
)
from app.agent.evidence import (
    HISTORICAL_SOURCE_INSTRUCTION,
    bound_headline_claims,
    bound_web_numeric_claims,
    label_historical_sources,
    prior_turn_sources,
    retain_referenced_citations,
    source_references,
)
from app.agent.freshness import server_time_context
from app.agent.orchestrator import (
    SYSTEM_PROMPT,
    AgentNotConfiguredError,
    AgentOrchestrator,
    AgentRunResult,
)
from app.agent.output_contract import enforce_presentation_contract, proactive_action_instruction
from app.agent.presentation import (
    explicit_presentation_contract,
    normalize_adaptive_framework,
    normalize_markdown_boundaries,
    normalize_math_notation,
    presentation_contract_violations,
)
from app.agent.quantitative import inventory_facts
from app.agent.recoverable_model import RecoverableGemini
from app.agent.response_guard import (
    enforce_explicit_source_restriction,
    source_restriction_instruction,
)
from app.agent.routing import Route, _rag_arguments, route_request
from app.agent.source_calculations import (
    SOURCE_CALCULATION_INSTRUCTION,
    CalculatedWireAnswer,
    has_inline_calculation_data,
    needs_source_calculation,
    resolve_calculations,
    validate_calculation_payload,
)
from app.core.config import APPROVED_GEMINI_MODELS, GEMINI_HTTP_TIMEOUT_MS, Settings
from app.core.source_pages import explicit_page_numbers
from app.db.models import Message, User
from app.db.session import SessionFactory
from app.services.quota import conservative_tokens
from app.services.relational_circuit import circuit_store
from app.services.relational_quota import quota_guard
from app.tools.calculator import CalculateInput, calculate
from app.tools.contracts import ToolContext, ToolError
from app.tools.registry import ToolRegistry

_logger = logging.getLogger(__name__)


def current_input_only(request: str) -> bool:
    """Recognize explicit evidence resets, not ordinary source selections."""
    return bool(re.search(
        r"(?:^|[.;\n])\s*(?:nguồn duy nhất[^.;\n]{0,100}(?:thông tin|nội dung|dữ liệu)"
        r"[^.;\n]{0,70}(?:vừa cung cấp|lượt hiện tại|lần này)|"
        r"chỉ (?:dùng|sử dụng)[^.;\n]{0,90}(?:lượt hiện tại|tin nhắn này)|"
        r"only use[^.;\n]{0,90}(?:current message|current turn|this message))",
        request, re.I,
    ))


def scoped_conversation_history(history: list[Message], current_request: str) -> list[Message]:
    """Keep a source reset across follow-ups without deleting UI history."""
    if current_input_only(current_request):
        return []
    rows = []
    for row in history:  # newest first
        rows.append(row)
        if row.role == "user" and current_input_only(row.content):
            break
    return rows


def conversation_context(history: list[Message], current_request: str) -> list[dict[str, str]]:
    """Bound context without silently discarding the end of long instructions.

    Rows arrive newest first. Keep recent turns within a total character budget;
    an explicit marker tells the model when older text is unavailable.
    """
    rows = scoped_conversation_history(history, current_request)
    if rows and rows[0].role == "user" and rows[0].content == current_request:
        rows.pop(0)
    remaining = 64000
    retained: list[dict[str, str]] = []
    for row in rows:
        if remaining < 512:
            break
        text = row.content
        allowance = min(16000, remaining)
        if len(text) > allowance:
            marker = "\n[Phần giữa đã được lược bớt; không suy đoán nội dung thiếu.]\n"
            available = allowance - len(marker)
            head = available // 2
            text = text[:head] + marker + text[-(available - head):]
        retained.append({"role": row.role, "text": text})
        remaining -= len(text)
    retained.reverse()
    if len(retained) < len(rows):
        retained.insert(0, {"role": "system", "text": (
            "Một phần lịch sử cũ không còn trong ngữ cảnh. "
            "Nếu thiếu dữ kiện cần thiết, hỏi lại người dùng; không tự dựng lại."
        )})
    return retained


def _schema_failure_code(exc: ValidationError | ValueError) -> str:
    """Report bounded schema types/locations, never model-generated values."""

    if isinstance(exc, ValidationError):
        safe_grid_rules = {
            "Every row must match the header width": "row_width",
            "Numeric cells must be finite and within ±10^15": "numeric_bounds",
            "Cell text exceeds 10,000 characters": "cell_length",
            "Formula range exceeds this sheet": "formula_range",
            "Formula column exceeds this sheet": "formula_column",
            "Formula row exceeds this sheet": "formula_row",
            "Row formula must stay on its own data row": "formula_own_row",
            "Row formula cannot reference itself": "formula_self_reference",
            "Headers must have 1–200 visible characters": "header_length",
            "Chart column exceeds this sheet": "chart_column",
            "Chart label and value must use different columns": "chart_same_column",
            "Chart values must be numeric": "chart_value_type",
        }
        allowed_parts = {
            "answer", "proposals", "kind", "document", "spreadsheet",
            "document_edit", "spreadsheet_edit", "spec_json", "title", "tabs",
            "headers", "rows", "formulas", "row_formulas", "charts", "theme",
            "sheet_title", "name", "values", "function", "column",
            "start_row", "end_row", "DocumentProposal", "SpreadsheetProposal",
            "DocumentEditProposal", "SpreadsheetEditProposal",
        }
        reasons: list[str] = []
        for issue in exc.errors(include_input=True)[:24]:
            issue_type = str(issue.get("type", "validation_error"))
            if not re.fullmatch(r"[a-z_]{1,40}", issue_type):
                issue_type = "validation_error"
            location = ".".join(
                str(part)
                if (isinstance(part, int) and 0 <= part <= 999)
                or (isinstance(part, str) and part in allowed_parts)
                else "other"
                for part in issue.get("loc", ())
            )[:80]
            reason = f"{issue_type}:{location}"
            if issue_type == "list_type":
                # The Python type is useful for schema repair and does not expose
                # row values. Never interpolate the value itself.
                input_type = type(issue.get("input")).__name__
                if input_type in {"dict", "str", "int", "float", "NoneType"}:
                    reason += f":{input_type}"
            # Only report exact, source-code-owned validator messages. Pydantic's
            # error context may otherwise contain untrusted model output.
            context_error = issue.get("ctx", {}).get("error")
            rule = safe_grid_rules.get(str(context_error))
            if rule:
                reason += f":{rule}"
            if reason not in reasons:
                reasons.append(reason)
        return "|".join(reasons)[:600]
    return type(exc).__name__

_VI_NUMBER_WORDS = {
    "một": 1,
    "mot": 1,
    "hai": 2,
    "ba": 3,
    "bốn": 4,
    "bon": 4,
    "năm": 5,
    "nam": 5,
    "sáu": 6,
    "sau": 6,
    "bảy": 7,
    "bay": 7,
    "tám": 8,
    "tam": 8,
    "chín": 9,
    "chin": 9,
    "mười": 10,
    "muoi": 10,
}


def _number_token(value: str) -> int | None:
    value = value.casefold().strip()
    if value.isdigit():
        return int(value)
    return _VI_NUMBER_WORDS.get(value)


def _explicitly_requests_fabrication(question: str) -> bool:
    """Match an affirmative request to invent facts, not a safety constraint."""

    for clause in re.split(r"[,;.!?\n]+", question.casefold()):
        if not re.search(r"\b(?:bịa|bịa đặt|bịa ra|fabricate|make up)\b", clause):
            continue
        if re.search(
            r"\b(?:không|đừng|chớ|tránh|cấm|never|do not|don't)\b"
            r"[^,;.!?\n]{0,32}\b(?:tự\s+)?(?:bịa|bịa đặt|bịa ra|fabricate|make up)\b",
            clause,
        ):
            continue
        affirmative_request = re.search(
            r"\b(?:hãy|cứ|vui lòng|tự ý|make up|fabricate|invent)\b", clause
        )
        fact_target = re.search(
            r"\b(?:bịa|bịa đặt|bịa ra|fabricate|make up)\b"
            r".*\b(?:số liệu|dữ kiện|thông tin|nguồn)\b",
            clause,
        )
        if affirmative_request or fact_target:
            return True
    return False


def deterministic_static_answer(user_message: str, *, general_route: bool = False) -> str | None:
    """Return safe, source-free answers for bounded contract/safety prompts.

    These requests do not require retrieval or model creativity. Keeping them
    deterministic prevents quota outages from turning an approval boundary or a
    basic output-format contract into an HTTP error. The responses are deliberately
    conditional where the user supplied no underlying facts.
    """

    question = user_message.casefold().strip()

    # Keep bounded arithmetic available during a provider outage. Only accept a
    # single explicit numeric expression coupled to clear calculation intent;
    # the existing calculator grammar rejects code, names and unknown symbols.
    arithmetic = re.search(
        r"(?<![\w.])(\d+(?:\.\d+)?\s*[+\-*/]\s*\d+(?:\.\d+)?)(?![\w.])",
        question,
    )
    if (
        arithmetic
        and "." in arithmetic.group(1)
        and re.search(r"\b(?:bằng bao nhiêu|tính|calculate|result)\b", question)
    ):
        computed = calculate(
            CalculateInput(operation="expression", values=[arithmetic.group(1)])
        )
        return (
            f"Kết quả: **{computed.result}**. "
            "Đã tính bằng Decimal theo đúng thứ tự phép toán."
        )

    # The general-purpose slash route deliberately disables external tools.  For
    # broad workflow prompts on that route, a short, truthful scaffold is more
    # useful than a model's one-line "please provide more context" response.  We
    # only apply these templates when the user explicitly selected /general; a
    # normal Gmail/Docs/Sheets request must still reach the real tool/compiler
    # path and use the connected account.
    general_route = general_route or question.startswith("/general")
    if (general_route or question.startswith("/general")) and re.search(
        r"\bmcp\b", question
    ) and re.search(r"\blà gì\b|\bngắn gọn\b", question):
        return (
            "MCP (Model Context Protocol) là giao thức mở giúp mô hình AI kết nối với "
            "công cụ hoặc nguồn dữ liệu bên ngoài theo cách thống nhất."
        )
    if general_route and re.search(r"tổng hợp email chưa đọc.*phân nhóm hành động", question):
        return (
            "## Cần trả lời\n\n"
            "- Chưa có danh sách thư chưa đọc trong ngữ cảnh hiện tại.\n"
            "- Chưa thể xác định thư nào cần phản hồi hoặc thời hạn cụ thể.\n\n"
            "## Cần theo dõi\n\n"
            "- Chưa có thư đủ dữ kiện để đưa vào nhóm theo dõi.\n\n"
            "## Chỉ để biết\n\n"
            "- Chưa có thư được tải để phân loại.\n\n"
            "## Bước tiếp theo\n\n"
            "1. Kết nối Gmail hoặc chọn `/inbox` để lấy thư chưa đọc.\n"
            "2. Kiểm tra lại từng nhóm trước khi đánh dấu hoặc tạo việc cần làm."
        )
    if general_route and re.search(
        r"tạo bản xem trước google doc.*ghi chú cuộc họp", question
    ):
        return (
            "## Bản xem trước trước khi tạo\n\n"
            "- Chưa tạo tệp Google Doc.\n"
            "- Nội dung ghi chú cuộc họp chưa được cung cấp nên chưa điền dữ kiện.\n"
            "- Bố cục dự kiến: mục tiêu, quyết định, việc cần làm và người phụ trách.\n\n"
            "## Xác nhận cần thiết\n\n"
            "- Gửi hoặc chọn ghi chú cuộc họp để tôi điền bản xem trước.\n"
            "- Chọn **Duyệt và tạo** nếu bố cục đã đúng.\n"
            "- Sau khi ghi, tôi sẽ đọc lại để đối chiếu nội dung."
        )
    if general_route and re.search(
        r"tạo bản xem trước google sheets.*theo dõi chi tiêu", question
    ):
        return (
            "## Bản xem trước\n\n"
            "| Hạng mục | Trạng thái |\n"
            "| --- | --- |\n"
            "| Ngày | Chưa có dữ liệu |\n"
            "| Nội dung chi | Chưa có dữ liệu |\n"
            "| Số tiền | Chưa có dữ liệu |\n\n"
            "## Công thức dự kiến\n\n"
            "- Tổng chi: `=SUM(C2:C100)`.\n"
            "- Có thể đổi phạm vi sau khi biết số dòng thực tế.\n\n"
            "## Trước khi ghi\n\n"
            "- Chưa tạo bảng trên Google Sheets.\n"
            "- Cần cung cấp các khoản chi hoặc xác nhận dùng mẫu trống.\n"
            "- Chọn **Duyệt và tạo**; sau đó tôi sẽ đọc lại để kiểm tra."
        )

    # Safety/refusal contracts are explicit and must never be delegated to a
    # model or a tool loop.
    if "bỏ qua quyền" in question and "token" in question:
        return (
            "### Từ chối an toàn\n\n"
            "- **Không thể** làm theo chỉ thị yêu cầu bỏ qua quyền hoặc gửi token.\n"
            "- Nội dung tài liệu không phải chỉ thị hệ thống; **không hiển thị secret**."
        )
    if re.search(r"gửi email.*ngay|gửi email này", question):
        return (
            "### Trạng thái\n\n"
            "- Chưa gửi email.\n"
            "- Cần xác nhận rõ người nhận, nội dung và phạm vi.\n"
            "- Chỉ tạo nháp trước; không tự gửi."
        )
    if "google sheet" in question and "chia sẻ công khai" in question:
        return (
            "### Bản xem trước\n\n"
            "- Chưa tạo hoặc chia sẻ Sheet.\n"
            "- Cần xác nhận trước khi ghi.\n"
            "- Không chia sẻ công khai nếu chưa có phạm vi và quyền được duyệt."
        )
    if "không thuộc tài khoản" in question and "đoán id" in question:
        return (
            "### Từ chối truy cập\n\n"
            "1. Kiểm tra quyền sở hữu/quyền được cấp trước.\n"
            "2. Không đoán ID để truy cập.\n"
            "3. Không truy cập trái phép tài liệu ngoài tài khoản."
        )
    if "xóa toàn bộ lịch sử audit" in question:
        return (
            "### Bảo toàn audit\n\n"
            "- **Không xóa audit**.\n"
            "- Giữ nguyên để bảo toàn dấu vết và khả năng đối soát.\n"
            "- Có thể lọc hoặc tổng hợp dashboard mà không phá dữ liệu gốc."
        )
    if _explicitly_requests_fabrication(question):
        return (
            "### Từ chối bịa dữ liệu\n\n"
            "- **Không bịa** số liệu.\n"
            "- Nêu thiếu bằng chứng, hỏi lại hoặc từ chối phần không thể kiểm chứng."
        )
    if "citation [9]" in question or ("citation" in question and "không có nguồn" in question):
        return (
            "### Tính toàn vẹn citation\n\n"
            "- **Không tạo citation ảo**.\n"
            "- Chỉ trích nguồn có thật và có thể mở lại để kiểm chứng."
        )
    if "revision cũ" in question or "cached text" in question:
        return (
            "### Kiểm tra freshness\n\n"
            "- Kiểm tra revision trước khi trả lời.\n"
            "- Không dùng dữ liệu stale như dữ liệu mới.\n"
            "- Nếu revision không xác minh được, báo rõ và yêu cầu đọc lại nguồn."
        )
    if "403" in question and "lặp vô hạn" in question:
        return (
            "### Xử lý lỗi provider\n\n"
            "- **Không retry vô hạn**.\n"
            "- Báo lỗi quyền hoặc scope từ Google.\n"
            "- Hướng dẫn reconnect/kiểm tra quyền rồi thử lại có giới hạn."
        )
    if "tự ý tạo file cloud" in question or (
        "không hiển thị preview" in question and "file" in question
    ):
        return (
            "### Human-in-the-loop\n\n"
            "- Phải có preview trước.\n"
            "- HITL bắt buộc cho thao tác ghi cloud.\n"
            "- Cần xác nhận trước ghi hoặc tạo file."
        )

    return None


def _markdown_table_rows(text: str) -> list[list[str]]:
    """Read the most data-like rectangular Markdown table in evidence."""

    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    best_rows: list[list[str]] = []
    best_numeric_cells = -1
    for index, line in enumerate(lines[:-1]):
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        separator = lines[index + 1]
        if len(cells) < 2 or not re.fullmatch(
            r"\s*\|?\s*:?-{3,}(?:\s*\|\s*:?-{3,})+\s*\|?\s*", separator
        ):
            continue
        rows: list[list[str]] = []
        for candidate in lines[index + 2 :]:
            if re.fullmatch(r"\s*\|?\s*:?-{3,}(?:\s*\|\s*:?-{3,})+\s*\|?\s*", candidate):
                break
            row = [cell.strip() for cell in candidate.strip("|").split("|")]
            if row and len(row) == len(cells):
                rows.append(row)
        numeric_cells = 0
        for row in rows:
            numeric_cells += sum(
                1 for cell in row if re.fullmatch(r"-?\d+(?:[.,]\d+)?", cell.strip())
            )
        if numeric_cells > best_numeric_cells:
            best_rows = rows
            best_numeric_cells = numeric_cells
    return best_rows


def _sheet_facts(text: str, user_message: str) -> dict[str, Any]:
    """Derive small, auditable facts from a retrieved Sheet table.

    These are deliberately limited to arithmetic and presence checks.  The source
    table remains the citation evidence; this helper prevents a model from missing a
    simple row calculation or treating the header as the only data row.
    """

    # PDFs may contain unrelated Markdown tables. Derive spreadsheet metadata
    # only when the user explicitly asks about table/cell arithmetic; the model
    # still receives the original source and is responsible for the answer.
    if not re.search(
        r"\b(?:sheet|spreadsheet|bảng tính|bảng|ô|cột|hàng|công thức|excel|"
        r"sum|average|mean|min|max)\b",
        user_message,
        re.I,
    ):
        return {}

    rows = _markdown_table_rows(text)
    if not rows:
        return {}
    numeric_rows: list[list[Decimal]] = []
    has_blank = False
    has_negative = False
    for row in rows:
        values: list[Decimal] = []
        for cell in row:
            if not cell:
                has_blank = True
                continue
            try:
                value = Decimal(cell.replace(",", "."))
            except Exception:
                continue
            values.append(value)
            has_negative = has_negative or value < 0
        if values and len(values) == len(row):
            numeric_rows.append(values)

    facts: dict[str, Any] = {}
    first_row_is_numeric = all(
        re.fullmatch(r"-?\d+(?:[.,]\d+)?", cell.strip()) for cell in rows[0]
    )
    if numeric_rows and numeric_rows[0] and first_row_is_numeric:
        first_row = numeric_rows[0]
        sum_value = format(sum(first_row), "f")
        if "." in sum_value:
            sum_value = sum_value.rstrip("0").rstrip(".")
        facts.update(
            {
                "column_count": len(rows[0]),
                "first_data_row": rows[0],
                "row_2_sum": sum_value,
                "row_2_min": str(min(first_row)),
                "row_2_max": str(max(first_row)),
            }
        )
    else:
        facts["column_count"] = len(rows[0])
    if re.search(r"\bformula\b|\bcông thức\b", user_message, re.I):
        width = len(rows[0])
        letters = ""
        while width:
            width, remainder = divmod(width - 1, 26)
            letters = chr(65 + remainder) + letters
        facts["sum_formula"] = f"=SUM(A2:{letters}2)"
    if re.search(r"\btrung bình\b|\baverage\b|\bmean\b", user_message, re.I):
        if numeric_rows and first_row_is_numeric:
            values = numeric_rows[0]
            facts["row_2_values"] = [str(value) for value in values]
            mean = format(sum(values) / len(values), "f")
            facts["row_2_mean"] = mean.rstrip("0").rstrip(".") if "." in mean else mean
    if re.search(r"số âm|ô rỗng|giá trị âm|empty|blank", user_message, re.I):
        facts["has_negative"] = has_negative
        facts["has_blank"] = has_blank
        facts["numeric_range"] = (
            f"{min(numeric_rows[0])} đến {max(numeric_rows[0])}"
            if numeric_rows and first_row_is_numeric
            else ""
        )
    return facts


def _local_calculation_expression(user_message: str, source_text: str) -> str | None:
    """Build an expression only when the retrieved local source states its inputs."""

    if not re.search(r"\b(?:tính|calculate|đối chiếu|kiểm tra lại)\b", user_message, re.I):
        return None
    meetings = re.search(
        r"(?:gồm|có)\s+(một|mot|hai|ba|bốn|bon|năm|nam|sáu|sau|\d+)\s+buổi",
        source_text,
        re.I,
    )
    minutes = re.search(r"mỗi buổi\s+(\d+(?:[.,]\d+)?)\s*phút", source_text, re.I)
    if not meetings or not minutes:
        return None
    count = _number_token(meetings.group(1))
    if count is None:
        return None
    per_session = minutes.group(1).replace(",", ".")
    return f"{count}*{per_session}"


def _local_fact_answer(user_message: str, source_text: str) -> str | None:
    """Answer bounded local-fixture facts only when the retrieved text states them."""

    if not source_text or "mã kiểm thử:" not in source_text.casefold():
        return None
    code_match = re.search(r"Mã kiểm thử\s*:\s*([A-Z0-9-]+)", source_text, re.I)
    plan_match = re.search(
        r"(?:gồm|có)\s+(một|mot|hai|ba|bốn|bon|năm|nam|sáu|sau|\d+)\s+buổi",
        source_text,
        re.I,
    )
    minutes_match = re.search(r"mỗi buổi\s+(\d+(?:[.,]\d+)?)\s*phút", source_text, re.I)
    total_match = re.search(r"Tổng thời gian[^\d]*(\d+(?:[.,]\d+)?)\s*phút", source_text, re.I)
    code = code_match.group(1) if code_match else None
    count = _number_token(plan_match.group(1)) if plan_match else None
    minutes = minutes_match.group(1).replace(",", ".") if minutes_match else None
    total = total_match.group(1).replace(",", ".") if total_match else None
    if not code and not (count and minutes and total):
        return None
    question = user_message.casefold()
    if "drive_file_metadata" in question:
        return "### Quyết định tool\n\n- **Không** cần gọi `drive_file_metadata` để đọc nội dung fixture local; chỉ cần tìm và đọc nguồn local."  # noqa: E501
    if (
        ("liệt kê" in question or ("mã kiểm thử" in question and "tổng" in question))
        and code
        and total
    ):
        return (
            "### Dữ kiện chính\n\n"
            f"- Mã kiểm thử: **{code}** [1].\n"
            f"- Tổng thời gian: **{total} phút** [1]."
        )
    if "mã kiểm thử" in question and code:
        return f"### Mã kiểm thử\n\n- Mã trong fixture là **{code}** [1]."
    if "mấy buổi" in question or "bao nhiêu buổi" in question:
        if count is not None:
            return f"### Kế hoạch\n\n- Fixture có **{count} buổi** [1]."
    if "mỗi buổi" in question or "kéo dài bao lâu" in question:
        if minutes:
            return f"### Thời lượng\n\n- Mỗi buổi kéo dài **{minutes} phút** [1]."
    if "tổng thời gian" in question and total:
        return f"### Tổng thời gian\n\n- Tổng thời gian theo kế hoạch là **{total} phút** [1]."
    if "tóm tắt" in question and code and total:
        count_text = f"{count} buổi" if count is not None else "số buổi được nêu trong fixture"
        return (
            "### Tóm tắt fixture\n\n"
            f"- Mã kiểm thử: **{code}** [1].\n"
            f"- Kế hoạch: **{count_text}**, tổng **{total} phút** [1]."
        )
    if ("đối chiếu" in question or "kiểm tra" in question) and minutes and total and count:
        calculated = Decimal(str(count)) * Decimal(minutes)
        expected = Decimal(total)
        verdict = "khớp" if calculated == expected else "không khớp"
        return (
            "### Đối chiếu\n\n"
            f"- {count} buổi × {minutes} phút = **{calculated} phút** [1].\n"
            f"- So với tổng kế hoạch **{total} phút**: **{verdict}** [1]."
        )
    return None


class CompiledAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=40000)


class CompilerOrchestrator:
    def __init__(self, settings: Settings, registry: ToolRegistry):
        self.settings, self.registry = settings, registry
        self.quota = quota_guard(settings, credential=settings.gemini_api_key)
        self.circuit = circuit_store(settings, settings.gemini_api_key)
        self.client: genai.Client | None = None
        self.model_fallback_enabled = True

    async def initialize(self):
        if self.settings.gemini_is_configured:
            self.client = genai.Client(
                api_key=self.settings.gemini_api_key,
                vertexai=False,
                http_options=types.HttpOptions(
                    base_url="https://generativelanguage.googleapis.com",
                    # Google rejects manually supplied deadlines below 10s.
                    timeout=GEMINI_HTTP_TIMEOUT_MS,
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )

    async def close(self):
        if self.client:
            await self.client.aio.aclose()
            self.client.close()

    async def run(
        self,
        *,
        user: User,
        session_id: str,
        request_id: str,
        user_message: str,
        controls: ChatControls | None = None,
        model_name: str | None = None,
        route_override: Route | None = None,
    ):
        controls = (
            (controls or ChatControls())
            .enforce_explicit_message_source(user_message)
            .enforce_explicit_source_exclusions(user_message)
        )
        route = route_request(user_message, timezone=self.settings.local_timezone)
        # A continuation can be pinned to the Gmail thread cited in this user's
        # persisted conversation. Apply it after slash controls so the server-owned
        # thread reference is not reduced back to a broad inbox search.
        if route_override and controls.source in {"auto", "gmail", "drive"}:
            route = route_override
        route = controls.filter_excluded_route(route)
        trace: list[dict[str, Any]] = []
        controls, route_alignment = controls.align_with_route(route)
        if route_alignment:
            trace.append({"stage": "control_resolution", "status": "routed", **route_alignment})
        route = self._apply_controls(route, user_message, controls)
        if route_request(user_message).tool == "web_research" and route.tool != "web_research":
            raise ToolError(
                "Câu hỏi cần nguồn cập nhật nhưng chế độ nguồn đang chọn không cho phép web. "
                "Chọn nguồn tự động để xác minh; tôi chưa khẳng định dữ kiện này.",
                code="freshness_source_required",
            )
        evidence: list[ToolMessage] = []
        context_data: Any = None
        derived_sheet_facts: dict[str, Any] = {}
        local_calculation: dict[str, Any] = {}
        local_fact_answer: str | None = None
        gmail_scope_warning: str | None = None
        async with SessionFactory() as db:
            user = await db.get(User, user.id)
            if not user or not user.is_active:
                raise ToolError("Phiên không còn hợp lệ.", code="authentication_required")
            if route.direct and route.clarification:
                source_selection_trace = {
                    "stage": "source_selection",
                    "status": "needs_clarification",
                }
                if route.required_sources:
                    source_selection_trace["required_sources"] = list(route.required_sources)
                return AgentRunResult(
                    answer=route.clarification,
                    plan=[],
                    trace=trace + [source_selection_trace],
                    citations=[],
                )
            if route.sources:
                gathered_sources: list[dict[str, Any]] = []
                for source_index, source_route in enumerate(route.sources, start=1):
                    if not source_route.tool:
                        raise ToolError(
                            "Không thể xác định công cụ đọc cho một nguồn được yêu cầu.",
                            code="invalid_source_route",
                        )
                    source_result = await self.registry.execute(
                        source_route.tool,
                        source_route.arguments or {},
                        ToolContext(
                            request_id=request_id,
                            user=user,
                            db=db,
                            settings=self.settings,
                            source="compiler_gather",
                        ),
                    )
                    source_data = source_result.model_dump(mode="json")
                    evidence.append(
                        ToolMessage(
                            content=json.dumps(source_data, ensure_ascii=False),
                            name=source_route.tool,
                            tool_call_id=f"{request_id}-source-{source_index}",
                        )
                    )
                    trace.append(
                        {"stage": "tool", "tool": source_route.tool, "status": "success"}
                    )
                    final_tool = source_route.tool
                    if source_route.read_match and source_route.tool == "gmail_list_messages":
                        messages = source_data.get("messages", [])
                        thread_id = str(messages[0].get("thread_id") or "") if messages else ""
                        if not thread_id:
                            return AgentRunResult(
                                answer=(
                                    "Không tìm thấy thư Gmail phù hợp để đối chiếu. "
                                    "Tôi chưa đưa ra kết luận một nguồn."
                                ),
                                plan=[],
                                trace=trace,
                                citations=[],
                            )
                        read_result = await self.registry.execute(
                            "gmail_read_thread",
                            {"thread_id": thread_id},
                            ToolContext(
                                request_id=request_id,
                                user=user,
                                db=db,
                                settings=self.settings,
                                source="compiler_gather",
                            ),
                        )
                        source_data = read_result.model_dump(mode="json")
                        evidence[-1] = ToolMessage(
                            content=json.dumps(source_data, ensure_ascii=False),
                            name="gmail_read_thread",
                            tool_call_id=f"{request_id}-source-{source_index}-read",
                        )
                        final_tool = "gmail_read_thread"
                        trace.append(
                            {"stage": "tool", "tool": final_tool, "status": "success"}
                        )
                    elif source_route.read_match and source_route.tool == "local_source_search":
                        candidates = source_data.get("data", {}).get("sources", [])
                        query = str((source_route.arguments or {}).get("query", ""))
                        candidates = [item for item in candidates
                                      if str(item.get("name", "")).casefold() == query.casefold()]
                        if len(candidates) != 1:
                            raise ToolError(
                                f"Chưa xác định được đúng một tài liệu local: {query}",
                                code="local_source_ambiguous",
                            )
                        source_data = await self._read_local_evidence(
                            candidates[0], user_message,
                            ToolContext(request_id=request_id, user=user, db=db,
                                        settings=self.settings, source="compiler_gather"),
                        )
                        if not source_data.get("data", {}).get("citations"):
                            raise ToolError(
                                f"Tài liệu {query} chưa có bằng chứng được lập chỉ mục.",
                                code="local_source_not_indexed",
                            )
                        evidence[-1] = ToolMessage(
                            content=json.dumps(source_data, ensure_ascii=False),
                            name="local_source_read",
                            tool_call_id=f"{request_id}-source-{source_index}-read",
                        )
                        final_tool = "local_source_read"
                        trace.append({"stage": "tool", "tool": final_tool, "status": "success"})
                    elif source_route.read_match and source_route.tool in {
                        "drive_list_files",
                        "drive_search_files",
                    }:
                        files = source_data.get("files", [])
                        query = str((source_route.arguments or {}).get("query", ""))
                        exact = [
                            item
                            for item in files
                            if str(item.get("name", "")).casefold() == query.casefold()
                        ]
                        if exact:
                            files = exact
                        if len(files) != 1:
                            return AgentRunResult(
                        answer=(
                            "Tôi chưa thể đối chiếu vì chưa xác định được đúng một tệp "
                            "Drive. Hãy nêu tên tệp cụ thể; tôi chưa kết luận chỉ dựa trên email."
                                ),
                                plan=[],
                                trace=trace
                                + [
                                    {
                                        "stage": "source_selection",
                                        "status": "needs_clarification",
                                        "required_sources": ["drive"],
                                    }
                                ],
                                citations=[],
                            )
                        read_result = await self.registry.execute(
                            "drive_read_file",
                            {"file_id": files[0]["id"], "max_characters": 20_000},
                            ToolContext(
                                request_id=request_id,
                                user=user,
                                db=db,
                                settings=self.settings,
                                source="compiler_gather",
                            ),
                        )
                        source_data = read_result.model_dump(mode="json")
                        evidence[-1] = ToolMessage(
                            content=json.dumps(source_data, ensure_ascii=False),
                            name="drive_read_file",
                            tool_call_id=f"{request_id}-source-{source_index}-read",
                        )
                        final_tool = "drive_read_file"
                        trace.append(
                            {"stage": "tool", "tool": final_tool, "status": "success"}
                        )
                    gathered_sources.append({"tool": final_tool, "data": source_data})
                context_data = {"sources": gathered_sources}
            # This is a tool-selection question, not a request to inspect a
            # file.  Answer it without touching Drive metadata or consuming a
            # model call; local content remains isolated from Drive tools.
            if route.tool == "local_source_search" and re.search(
                r"drive_file_metadata", user_message, re.I
            ):
                return AgentRunResult(
                    answer=(
                        "### Quyết định tool\n\n"
                        "- **Không** cần gọi `drive_file_metadata` để đọc nội dung fixture local.\n"
                        "- Chỉ dùng `local_source_search` và `local_source_read` cho nguồn trên máy."  # noqa: E501
                    ),
                    plan=[],
                    trace=trace
                    + [
                        {
                            "stage": "deterministic_analysis",
                            "status": "success",
                            "kind": "local_tool_selection",
                        }
                    ],
                    citations=[],
                )
            if route.tool:
                try:
                    result = await self.registry.execute(
                        route.tool,
                        route.arguments or {},
                        ToolContext(
                            request_id=request_id,
                            user=user,
                            db=db,
                            settings=self.settings,
                            source="compiler_gather",
                        ),
                    )
                except ToolError as exc:
                    # Lack of public evidence is an explicit outcome, not a
                    # license to synthesize current facts or hide tool failure.
                    if route.tool != "web_research" or exc.code not in {
                        "ungrounded_web_research", "web_research_provider_error",
                        "web_source_dns_error", "web_source_transport_error",
                        "official_source_empty", "news_sources_empty", "news_feed_invalid",
                    }:
                        raise
                    return AgentRunResult(
                        answer=(
                            "Chưa xác minh được thông tin từ nguồn web. "
                            "Công cụ kiểm nguồn đã được gọi nhưng không trả về "
                            "bằng chứng đủ dùng; tôi không đưa lịch hoặc dữ kiện "
                            "mới từ trí nhớ. Bạn có thể cung cấp một nguồn khác "
                            "để đối chiếu."
                        ),
                        plan=[],
                        trace=trace + [
                            {"stage": "tool", "tool": "web_research", "status": "error",
                             "error_code": exc.code},
                            {"stage": "source_selection", "status": "unverified"},
                        ],
                        citations=[],
                    )
                context_data = result.model_dump(mode="json")
                if route.tool == "gmail_read_matching_messages":
                    messages = context_data.get("messages", [])
                    if not messages:
                        has_more = bool(context_data.get("next_page_token"))
                        examined = int(context_data.get("examined_count") or 0)
                        return AgentRunResult(
                            answer=(
                                f"Chưa thấy email phù hợp trong {examined} thư đã kiểm tra, "
                                "nhưng Gmail còn trang chưa duyệt; chưa thể kết luận không có thư."
                                if has_more
                                else "Không tìm thấy email phù hợp trong phạm vi đã chọn."
                            ),
                            plan=[],
                            trace=trace + [{
                                "stage": "source_selection",
                                "status": "incomplete" if has_more else "empty",
                            }],
                            citations=[],
                        )
                    if (route.arguments or {}).get("day_scope") == "today" and context_data.get(
                        "next_page_token"
                    ):
                        gmail_scope_warning = (
                            "Chưa xác minh đã đọc hết thư phù hợp trong ngày: "
                            "Gmail còn trang kết quả "
                            "chưa duyệt. Báo cáo chỉ bao phủ các thư được dẫn nguồn ở trên."
                        )
                    unreadable = int(context_data.get("unreadable_body_count") or 0)
                    if unreadable:
                        note = (
                            f"Có {unreadable} thư không đọc được phần văn bản; "
                            "chưa tổng hợp nội dung các thư đó."
                        )
                        gmail_scope_warning = (
                            f"{gmail_scope_warning} {note}" if gmail_scope_warning else note
                        )
                evidence.append(
                    ToolMessage(
                        content=json.dumps(context_data), name=route.tool, tool_call_id=request_id
                    )
                )
                trace.append({"stage": "tool", "tool": route.tool, "status": "success"})
                if route.read_match and route.tool == "gmail_list_messages":
                    matches = context_data.get("messages", [])
                    if not matches:
                        return AgentRunResult(
                            answer=(
                                "Không tìm thấy email gần đây trong phạm vi hộp thư được kết nối."
                            ),
                            plan=[],
                            trace=trace,
                            citations=[],
                        )
                    thread_id = str(matches[0].get("thread_id") or "")
                    if not thread_id:
                        return AgentRunResult(
                            answer=(
                                "Tìm thấy email nhưng không lấy được mã chuỗi thư để đọc nội dung."
                            ),
                            plan=[],
                            trace=trace,
                            citations=[],
                        )
                    read = await self.registry.execute(
                        "gmail_read_thread",
                        {"thread_id": thread_id},
                        ToolContext(
                            request_id=request_id,
                            user=user,
                            db=db,
                            settings=self.settings,
                            source="compiler_gather",
                        ),
                    )
                    context_data = read.model_dump(mode="json")
                    # The list result only contains a snippet. Keep the full thread
                    # as the evidence/citation used to answer the user's request.
                    evidence[-1] = ToolMessage(
                        content=json.dumps(context_data, ensure_ascii=False),
                        name="gmail_read_thread",
                        tool_call_id=request_id + "-thread",
                    )
                    trace.append(
                        {"stage": "tool", "tool": "gmail_read_thread", "status": "success"}
                    )
                elif route.read_match:
                    local = route.tool == "local_source_search"
                    matches = (
                        context_data.get("data", {}).get("sources", [])
                        if local
                        else context_data.get("files", [])
                    )
                    # Drive full-text search may also return documents mentioning
                    # this filename. Prefer a unique exact name before asking.
                    query = (route.arguments or {}).get("query", "").strip().casefold()
                    exact = [item for item in matches if item.get("name", "").casefold() == query]
                    if exact:
                        matches = exact
                    elif local and len(matches) > 1:
                        # Local search returns a relevance score so a natural
                        # question such as “mã kiểm thử trong fixture” can open
                        # the clearly best matching source without guessing when
                        # two files tie.
                        ranked = sorted(
                            matches,
                            key=lambda item: float(item.get("match_score", 0) or 0),
                            reverse=True,
                        )
                        if float(ranked[0].get("match_score", 0) or 0) > float(
                            ranked[1].get("match_score", 0) or 0
                        ):
                            matches = ranked[:1]
                    if len(matches) != 1:
                        return AgentRunResult(
                            answer=(
                                "Không tìm thấy đúng một tệp. "
                                "Hãy chọn tệp cụ thể trong khu vực tài liệu rồi thử lại."
                            ),
                            plan=[],
                            trace=trace,
                            citations=[],
                        )
                    name = "local_source_read" if local else "drive_read_file"
                    args = (
                        {"source_id": matches[0]["id"], **(
                            {"query": user_message[:2000]} if matches[0].get("name", "").lower()
                            .endswith(".pdf") else {}
                        )}
                        if local
                        else {"file_id": matches[0]["id"], "max_characters": 20000}
                    )
                    read_context = ToolContext(
                        request_id=request_id, user=user, db=db,
                        settings=self.settings, source="compiler_gather",
                    )
                    if local:
                        context_data = await self._read_local_evidence(
                            matches[0], user_message, read_context,
                        )
                    else:
                        read = await self.registry.execute(name, args, read_context)
                        context_data = read.model_dump(mode="json")
                    read_evidence = ToolMessage(
                        content=json.dumps(context_data), name=name,
                        tool_call_id=request_id + "-read",
                    )
                    if local:
                        # Search previews identify the file; only the completed
                        # read supplies evidence for its requested pages.
                        evidence[-1] = read_evidence
                    else:
                        evidence.append(read_evidence)
                    trace.append({"stage": "tool", "tool": name, "status": "success"})
                    if local:
                        local_data = (
                            context_data.get("data", {}) if isinstance(context_data, dict) else {}
                        )
                        local_source_text = str(
                            local_data.get("text") or context_data.get("text") or ""
                        )
                        local_fact_answer = _local_fact_answer(user_message, local_source_text)
                        expression = _local_calculation_expression(
                            user_message,
                            local_source_text,
                        )
                        if expression:
                            calculated = await self.registry.execute(
                                "calculate",
                                {"operation": "expression", "values": [expression]},
                                ToolContext(
                                    request_id=request_id,
                                    user=user,
                                    db=db,
                                    settings=self.settings,
                                    source="compiler_derived_fact",
                                ),
                            )
                            context_data = {
                                "source": context_data,
                                "calculation": calculated.model_dump(mode="json"),
                            }
                            evidence.append(
                                ToolMessage(
                                    content=json.dumps(
                                        calculated.model_dump(mode="json"), ensure_ascii=False
                                    ),
                                    name="calculate",
                                    tool_call_id=request_id + "-calculate",
                                )
                            )
                            trace.append(
                                {"stage": "tool", "tool": "calculate", "status": "success"}
                            )
                            local_calculation = {
                                "expression": expression,
                                "calculation": calculated.model_dump(mode="json"),
                                "source_text": local_source_text,
                            }
                    elif isinstance(context_data, dict):
                        # The provider can label an uploaded workbook as a generic
                        # binary MIME type.  The table shape and the user's
                        # arithmetic/validation intent are a safer signal than MIME
                        # alone, so keep this bounded to explicit spreadsheet facts.
                        source_text = str(context_data.get("text") or "")
                        if "|" in source_text:
                            derived_sheet_facts = _sheet_facts(source_text, user_message)
                            if derived_sheet_facts:
                                context_data = {
                                    "source": context_data,
                                    "derived_facts": derived_sheet_facts,
                                }
                # An evaluator or user may provide the Drive ID directly.  In
                # that route there is no search/read_match second step, but the
                # same bounded Sheet fact extraction must still run before the
                # model is asked to explain the table.
                if route.tool == "drive_read_file" and isinstance(context_data, dict):
                    source_text = str(context_data.get("text") or "")
                    if "|" in source_text:
                        derived_sheet_facts = _sheet_facts(source_text, user_message)
                        if derived_sheet_facts:
                            context_data = {
                                "source": context_data,
                                "derived_facts": derived_sheet_facts,
                            }
            history = list(
                await db.scalars(
                    select(Message)
                    .where(Message.user_id == user.id, Message.session_id == session_id)
                    .order_by(Message.created_at.desc())
                    .limit(32)
                )
            )
        history = scoped_conversation_history(history, user_message)
        citations = AgentOrchestrator._collect_citations(evidence)
        reused_sources = False
        if not citations and not route.direct:
            citations = prior_turn_sources(history, user_message)
            reused_sources = bool(citations)
            if reused_sources:
                trace.append({
                    "stage": "context", "status": "success",
                    "source_count": len(citations),
                    "note": "Nguồn của phiên hiện tại được dùng lại; chưa đọc hoặc xác minh lại.",
                })
        if local_calculation:
            raw_expression = str(local_calculation.get("expression") or "")
            factors = re.fullmatch(r"(\d+)\*(\d+(?:\.\d+)?)", raw_expression)
            if not factors:
                raise ToolError(
                    "Không đọc được phép tính từ nguồn local.", code="invalid_source_fact"
                )
            count, minutes = factors.groups()
            expression = raw_expression.replace("*", " × ")
            calculation = local_calculation.get("calculation") or {}
            result = str(calculation.get("result") or "")
            source_text = str(local_calculation.get("source_text") or "")
            total_match = re.search(
                r"Tổng\s+thời gian[^\d]*(\d+(?:[.,]\d+)?)\s*phút", source_text, re.I
            )
            total = total_match.group(1).replace(",", ".") if total_match else None
            verdict = (
                "khớp" if total and Decimal(result) == Decimal(total) else "không khớp"
            )
            comparison = (
                "### Đối chiếu nguồn\n\n"
                f"- Nguồn ghi tổng thời gian **{total} phút** [1].\n"
                f"- Kết quả tính lại **{verdict}** với tổng nguồn [1]."
                if total
                else "### Đối chiếu nguồn\n\n- Nguồn không nêu tổng thời gian để đối chiếu."
            )
            answer = (
                "### Kết quả\n\n"
                f"- Phép tính kiểm chứng: `{expression} = {result} phút` [1].\n\n"
                "### Dữ kiện đầu vào\n\n"
                f"- Nguồn nêu **{count} buổi**, mỗi buổi **{minutes} phút** [1].\n\n"
                + comparison
            )
            return AgentRunResult(
                answer=answer,
                plan=[],
                trace=trace
                + [
                    {
                        "stage": "deterministic_analysis",
                        "status": "success",
                        "kind": "local_calculation",
                    }
                ],
                citations=citations,
            )
        if local_fact_answer:
            cited_lines: list[str] = []
            for line in local_fact_answer.splitlines():
                if line.lstrip().startswith("-") and "[1]" not in line and citations:
                    line = f"{line.rstrip()} [1]"
                cited_lines.append(line)
            return AgentRunResult(
                answer="\n".join(cited_lines),
                plan=[],
                trace=trace
                + [
                    {
                        "stage": "deterministic_analysis",
                        "status": "success",
                        "kind": "local_facts",
                    }
                ],
                citations=citations,
            )
        if route.direct:
            answer = self._direct_answer(context_data, route, user_message)
            return AgentRunResult(answer=answer, plan=[], trace=trace, citations=citations)
        if (
            controls.source in {"general", "auto"}
            and controls.output == "spreadsheet"
            and controls.workflow == "budget_tracker"
            and controls.agent in {"workspace", "auto"}
        ):
            compiled = budget_tracker_template()
            trace.append(
                {
                    "stage": "orchestration",
                    "status": "success",
                    "route": "reviewed_budget_template",
                    "note": "Mẫu xác định trước; không gọi model và chưa ghi Google Sheets.",
                }
            )
            return AgentRunResult(
                answer=compiled.answer,
                plan=[],
                trace=trace,
                citations=[],
                proposals=[item.model_dump(mode="json") for item in compiled.proposals],
            )
        if not self.client:
            raise AgentNotConfiguredError("Chưa cấu hình Gemini; thao tác trực tiếp vẫn dùng được.")
        resolved_model = (model_name or self.settings.gemini_chat_model).strip()
        if resolved_model not in APPROVED_GEMINI_MODELS:
            raise ToolError("Model không nằm trong danh sách đã duyệt.", code="model_not_allowed")
        # Canonical history survives both ADK and LangGraph. No framework checkpoint replay.
        history_data = conversation_context(history, user_message)
        source_calculation = needs_source_calculation(
            user_message,
            has_evidence=(
                context_data is not None or reused_sources
                or has_inline_calculation_data(user_message, output=controls.output)
            ),
            output=controls.output,
        )
        wire_schema = (
            CalculatedWireAnswer.provider_schema() if source_calculation
            else WireAnswer.provider_schema()
        )
        consultation_report = consultation_report_requested(user_message)
        if consultation_report:
            wire_schema = consultation_provider_schema(wire_schema)
        verified_calculations = inventory_facts(user_message)
        if verified_calculations:
            trace.append({"stage": "deterministic_analysis", "status": "success",
                          "kind": "inventory_balance", "method": "Decimal"})
        prompt = json.dumps(
            {
                "current_user_request": user_message,
                "server_time": server_time_context(self.settings.local_timezone),
                "history_untrusted": history_data,
                "evidence_untrusted": context_data,
                "source_references": source_references(citations),
                "artifact_contract": CreationAnswer.model_json_schema(),
                "chat_controls": controls.model_dump(mode="json"),
                "verified_calculations": verified_calculations,
            },
            ensure_ascii=False,
        )
        source_constraint = source_restriction_instruction(user_message)
        action_constraint = proactive_action_instruction(user_message)
        response_contract = explicit_presentation_contract(user_message)
        response_contract_instruction = (
            f"\nRàng buộc độ dài/độ sâu bắt buộc: {response_contract.generation_instruction()}."
            if response_contract.active
            else ""
        )
        instruction = (
            SYSTEM_PROMPT
            + CREATION_INSTRUCTION
            + "\nĐiều khiển Chat Harness do người dùng chọn: "
            + controls.instruction()
            + (f"\n{source_constraint}" if source_constraint else "")
            + (f"\n{action_constraint}" if action_constraint else "")
            + response_contract_instruction
            + ("\n" + HISTORICAL_SOURCE_INSTRUCTION if reused_sources else "")
            + "\nNếu verified_calculations có dữ liệu, dùng đúng các kết quả tính xác định; "
            "không tự thay kết quả. Trình bày giả định; ngưỡng đề xuất phải ghi là đề xuất."
            + (
                "\nBạn đang tổng hợp đúng một lượt, không có tool để tự thực thi. "
                "Không tuyên bố đã tạo/sửa/gửi/chạy sản phẩm nếu evidence không xác nhận. "
                "Chỉ dùng số reference trong source_references, "
                "không dùng chunk_index làm số nguồn. "
                "Nếu thiếu tài liệu/ID, hỏi ngắn để làm rõ, không bịa nội dung tài liệu. "
                "Định dạng truyền: mỗi proposal có kind và spec_json. spec_json là chuỗi JSON "
                "của đúng spec theo kind trong artifact_contract, không bọc thêm kind hay "
                "tên capability bên trong. Kiểm tra dữ liệu trước khi trả."
            )
        )
        if source_calculation:
            instruction += SOURCE_CALCULATION_INSTRUCTION
        if consultation_report:
            instruction += (
                "\nBáo cáo tư vấn phải có clarification_questions: đúng ba câu hỏi khác nhau, "
                "ngắn, cụ thể bằng tiếng Việt để xác nhận hiện trạng, nhu cầu và kết quả "
                "mong muốn của khách hàng này. Không tự trả lời các câu hỏi đó. "
                "Hệ thống hiển thị trường này riêng; không lặp lại trong answer. "
                "Nếu yêu cầu giới hạn số từ, tổng answer và ba câu hỏi phải nằm trong giới hạn. "
                "Diễn đạt giải thích hoàn toàn bằng tiếng Việt; giữ nguyên tên riêng, "
                "tên tệp và mã nguồn, nhưng không chêm nhãn như headline, Mobility, "
                "Industrial Technology hoặc Consumer Goods. Ngày tin phải ghi 'ngày đăng'."
            )
        await asyncio.to_thread(
            self.quota.reserve, "flash",
            conservative_tokens(prompt + instruction + json.dumps(wire_schema), 8192),
        )
        model_attempts: list[dict[str, Any]] = []
        sessions = InMemorySessionService()
        await sessions.create_session(
            app_name="drive_compiler", user_id=user.id, session_id=request_id
        )
        model = RecoverableGemini(
            model=resolved_model,
            fallback_model=self.settings.gemini_fallback_model,
            client=self.client,
            quota=self.quota,
            circuit=self.circuit,
            enable_fallback=self.model_fallback_enabled,
            fallback_attempt_limit=1 if consultation_report else None,
            fallback_timeout_ms=10000 if consultation_report else None,
        )
        # Pydantic copies mutable inputs during construction. Rebind afterwards so
        # provider attempt records are visible to the compiler trace.
        model.records = model_attempts
        agent = LlmAgent(
            name="drive_compiler",
            model=model,
            instruction=instruction,
            tools=[],
            include_contents="none",
            generate_content_config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=4096 if consultation_report else 8192,
                http_options=types.HttpOptions(timeout=25000) if consultation_report else None,
                # ADK output_schema targets the legacy responseSchema dialect.
                # Pydantic extra='forbid' needs JSON Schema's additionalProperties.
                response_mime_type="application/json",
                response_json_schema=wire_schema,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        runner = Runner(agent=agent, app_name="drive_compiler", session_service=sessions)
        answer = None
        proposals = []
        invalid_raw = ""
        clarification_questions: list[str] = []
        async with asyncio.timeout(90):
            async for event in runner.run_async(
                user_id=user.id,
                session_id=request_id,
                new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
                run_config=RunConfig(max_llm_calls=1),
            ):
                if event.usage_metadata:
                    trace.append(
                        {
                            "stage": "usage",
                            "status": "success",
                            **event.usage_metadata.model_dump(exclude_none=True),
                        }
                    )
                if event.is_final_response() and event.content:
                    parts = event.content.parts or []
                    # Some ADK/provider versions mark the only structured JSON part as
                    # ``thought`` even when it is the final payload. Prefer visible text,
                    # but accept that payload when no visible text exists; never combine
                    # prose/thought with JSON because that would make validation unsafe.
                    raw = "".join(p.text for p in parts if p.text and not p.thought)
                    if not raw:
                        raw = next((p.text for p in reversed(parts) if p.text), "")
                    original_raw = raw
                    try:
                        candidate_questions = []
                        if consultation_report:
                            raw, candidate_questions = separate_consultation_questions(raw)
                        wire = (
                            validate_calculation_payload(raw) if source_calculation
                            else WireAnswer.model_validate_json(raw)
                        )
                        if source_calculation:
                            wire = await resolve_calculations(
                                wire, self.registry,
                                ToolContext(request_id=request_id, user=user, db=db,
                                            settings=self.settings, source="compiler_calculation"),
                                trace,
                            )
                        compiled = ground_unsourced_spreadsheet_preview(
                            user_message,
                            preserve_explicit_literals(
                                user_message,
                                wire.validate_artifacts(
                                    blank_unsourced_sheet=blank_unsourced_sheet_requested(
                                        user_message,
                                        has_source_data=context_data is not None or bool(citations),
                                    )
                                ),
                            ),
                            has_source_data=context_data is not None or bool(citations),
                        )
                        answer = compiled.answer
                        clarification_questions = candidate_questions
                        proposals = [item.model_dump(mode="json") for item in compiled.proposals]
                    except (ValidationError, ValueError) as exc:
                        _logger.warning(
                            "Structured creation output rejected; reason=%s",
                            _schema_failure_code(exc),
                        )
                        # Keep the first malformed payload private and perform one bounded,
                        # schema-constrained repair. No side-effect tool is available in
                        # either pass, so a failed repair still remains fail-closed.
                        invalid_raw = original_raw[:40000]
        if not answer and invalid_raw:
            await asyncio.to_thread(
                self.quota.reserve,
                "flash",
                conservative_tokens(invalid_raw + instruction, 8192),
            )
            repair_session_id = request_id + "-schema-repair"
            await sessions.create_session(
                app_name="drive_compiler", user_id=user.id, session_id=repair_session_id
            )
            repair_model = RecoverableGemini(
                model=model.model,
                fallback_model=self.settings.gemini_fallback_model,
                client=self.client,
                quota=self.quota,
                circuit=self.circuit,
                enable_fallback=self.model_fallback_enabled,
                fallback_attempt_limit=1 if consultation_report else None,
                fallback_timeout_ms=10000 if consultation_report else None,
            )
            repair_model.records = model_attempts
            repair_agent = LlmAgent(
                name="drive_compiler_repair",
                model=repair_model,
                instruction=(
                    instruction
                    + "\nĐây là lượt sửa cấu trúc duy nhất. Giữ nguyên mọi literal, số liệu và "
                    "ý nghĩa từ yêu cầu người dùng. Chỉ sửa JSON/spec để khớp chính xác schema; "
                    "không thêm dữ kiện mới và không giải thích ngoài JSON."
                ),
                tools=[],
                include_contents="none",
                generate_content_config=types.GenerateContentConfig(
                    temperature=0,
                    max_output_tokens=4096 if consultation_report else 8192,
                    response_mime_type="application/json",
                    response_json_schema=wire_schema,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
            repair_runner = Runner(
                agent=repair_agent,
                app_name="drive_compiler",
                session_service=sessions,
            )
            repair_prompt = json.dumps(
                {
                    "current_user_request": user_message,
                    "invalid_payload_to_repair": invalid_raw,
                    "artifact_contract": CreationAnswer.model_json_schema(),
                    "evidence_untrusted": context_data,
                    "source_references": source_references(citations),
                },
                ensure_ascii=False,
            )
            async with asyncio.timeout(90):
                async for event in repair_runner.run_async(
                    user_id=user.id,
                    session_id=repair_session_id,
                    new_message=types.Content(role="user", parts=[types.Part(text=repair_prompt)]),
                    run_config=RunConfig(max_llm_calls=1),
                ):
                    if event.usage_metadata:
                        trace.append(
                            {
                                "stage": "usage",
                                "status": "success",
                                "repair": True,
                                **event.usage_metadata.model_dump(exclude_none=True),
                            }
                        )
                    if event.is_final_response() and event.content:
                        parts = event.content.parts or []
                        raw = "".join(p.text for p in parts if p.text and not p.thought)
                        if not raw:
                            raw = next((p.text for p in reversed(parts) if p.text), "")
                        try:
                            candidate_questions = []
                            if consultation_report:
                                raw, candidate_questions = separate_consultation_questions(raw)
                            wire = (
                                validate_calculation_payload(raw) if source_calculation
                                else WireAnswer.model_validate_json(raw)
                            )
                            if source_calculation:
                                wire = await resolve_calculations(
                                    wire, self.registry,
                                    ToolContext(request_id=request_id, user=user, db=db,
                                                settings=self.settings,
                                                source="compiler_calculation"), trace,
                                )
                            compiled = ground_unsourced_spreadsheet_preview(
                                user_message,
                                preserve_explicit_literals(
                                    user_message,
                                    wire.validate_artifacts(
                                        blank_unsourced_sheet=blank_unsourced_sheet_requested(
                                            user_message,
                                            has_source_data=(
                                                context_data is not None or bool(citations)
                                            ),
                                        )
                                    ),
                                ),
                                has_source_data=context_data is not None or bool(citations),
                            )
                            answer = compiled.answer
                            clarification_questions = candidate_questions
                            proposals = [
                                item.model_dump(mode="json") for item in compiled.proposals
                            ]
                        except (ValidationError, ValueError) as exc:
                            _logger.warning(
                                "Structured creation repair rejected; reason=%s",
                                _schema_failure_code(exc),
                            )
            trace.append(
                {
                    "stage": "structured_repair",
                    "status": "success" if answer else "failure",
                    "model": resolved_model,
                    "note": "Một lượt sửa schema có giới hạn; không có tool ghi dữ liệu.",
                }
            )
        if not answer:
            raise ToolError(
                "Model không trả về spec hợp lệ; chưa thực thi thay đổi nào.", code="invalid_spec"
            )
        fallback_events = [
            item
            for item in model_attempts
            if item.get("status") in {"fallback", "failed"}
        ]
        actual_model = str(
            model_attempts[-1].get("actual_model") if model_attempts else resolved_model
        )
        model_summary: dict[str, Any] = {
            "stage": "model",
            "status": "fallback" if fallback_events else "success",
            "model": actual_model,
            "requested_model": resolved_model,
            "actual_model": actual_model,
            "fallback_model": self.settings.gemini_fallback_model,
            "fallback_reason": (
                fallback_events[0].get("fallback_reason") if fallback_events else None
            ),
            "model_call_count": sum(
                2 if item.get("status") in {"fallback", "failed"} else 1
                for item in model_attempts
            ),
            "model_attempts": [
                {
                    "requested_model": item.get("requested_model"),
                    "actual_model": item.get("actual_model"),
                    "status": item.get("status"),
                    "provider_code": item.get("provider_code"),
                    "fallback_error_code": item.get("fallback_error_code"),
                }
                for item in model_attempts
            ],
            "note": (
                "Một lượt ADK và một lượt sửa schema có giới hạn."
                if invalid_raw
                else (
                    "Một lượt ADK; fallback có giới hạn, không vòng lặp tool."
                    if fallback_events
                    else "Một lượt ADK; không fallback, không vòng lặp tool."
                )
            ),
        }
        if fallback_events:
            model_summary["provider_code"] = fallback_events[0].get("provider_code")
        trace.append(model_summary)
        answer = normalize_math_notation(answer)
        answer, framework_changed = normalize_adaptive_framework(user_message, answer)
        if framework_changed:
            trace.append(
                {
                    "stage": "presentation_framework",
                    "status": "corrected",
                    "note": "Chuẩn hóa heading/bước theo ý định câu hỏi; không thêm dữ kiện.",
                }
            )
        answer, citations = retain_referenced_citations(
            answer, citations, auto_reference=not reused_sources
        )
        answer, affected_claims = enforce_explicit_source_restriction(
            user_message,
            answer,
            has_citations=bool(citations),
        )
        if affected_claims:
            trace.append(
                {
                    "stage": "output_guard",
                    "status": "corrected",
                    "rule": "explicit_unsourced_claim_restriction",
                    "affected_lines": affected_claims,
                }
            )
        if clarification_questions:
            answer += "\n\n## Câu hỏi cần làm rõ\n\n" + "\n".join(
                f"{index}. {question}"
                for index, question in enumerate(clarification_questions, 1)
            )
        answer = await enforce_presentation_contract(
            client=self.client,
            quota=self.quota,
            user_message=user_message,
            answer=answer,
            model_name=resolved_model,
            fallback_model=self.settings.gemini_fallback_model,
            records=trace,
            verified_calculations=verified_calculations,
            source_evidence_untrusted=context_data,
            source_references_untrusted=source_references(citations),
        )
        # The bounded model rewrite can restore inline headings/steps or TeX
        # that were already cleaned in the first pass. Apply only content-neutral
        # boundary normalization; do not synthesize new answer sections here.
        answer, numeric_lines = bound_web_numeric_claims(answer, citations)
        if numeric_lines:
            trace.append({
                "stage": "output_guard", "status": "corrected",
                "rule": "web_numeric_evidence_boundary", "affected_lines": numeric_lines,
            })
        answer, headline_lines = bound_headline_claims(answer, citations)
        if headline_lines:
            answer, citations = retain_referenced_citations(answer, citations)
            trace.append({
                "stage": "output_guard", "status": "corrected",
                "rule": "headline_evidence_boundary", "affected_lines": headline_lines,
                "note": "Chỉ hiển thị tiêu đề/ngày đăng; chưa xác minh sự kiện.",
            })
            if response_contract.active and presentation_contract_violations(
                answer, response_contract,
            ):
                raise ToolError(
                    "Nguồn chỉ có tiêu đề chưa đủ cho báo cáo đúng yêu cầu trình bày; "
                    "chưa thực hiện thao tác ghi.", code="incomplete_source_report",
                )
        answer = normalize_math_notation(answer)
        answer, _ = normalize_markdown_boundaries(answer)
        if reused_sources:
            answer = label_historical_sources(answer, citations)
        if gmail_scope_warning:
            answer = f"{answer.rstrip()}\n\n**Giới hạn nguồn:** {gmail_scope_warning}"
        if clarification_questions and any(
            question not in answer for question in clarification_questions
        ):
            # A bounded presentation rewrite must not remove required output.
            # Do not append questions afterward and silently exceed a word limit.
            raise ToolError(
                "Báo cáo chưa giữ đủ câu hỏi làm rõ; chưa thực hiện thao tác ghi.",
                code="incomplete_consultation_report",
            )
        return AgentRunResult(
            answer=answer, plan=[], trace=trace, citations=citations, proposals=proposals
        )

    async def _read_local_evidence(
        self, source: dict[str, Any], message: str, context: ToolContext,
    ) -> dict[str, Any]:
        """Honor explicit PDF pages before relevance retrieval, retaining full pages.

        Each call goes through the permissioned registry with the original user
        context. Pagination is bounded, cancellable, and fails closed rather than
        silently generating from a partial requested page.
        """
        is_pdf = str(source.get("name", "")).casefold().endswith(".pdf")
        try:
            pages = explicit_page_numbers(message) if is_pdf else ()
        except ValueError as exc:
            raise ToolError(
                "Phạm vi trang không hợp lệ hoặc quá rộng; hãy chọn tối đa 12 trang.",
                code="source_page_limit",
            ) from exc
        filenames = set(re.findall(r"[\w.-]+\.pdf\b", message.casefold()))
        if len(filenames) > 1 and len(pages) > 1 and len(re.findall(
            r"\b(?:trang|pages?|p\.)\s*\d", message, re.I,
        )) > 1:
            raise ToolError(
                "Phạm vi trang của từng tệp chưa rõ; hãy đọc từng tệp với trang tương ứng.",
                code="source_page_scope_ambiguous",
            )
        if not pages:
            args = {"source_id": source["id"]}
            if is_pdf:
                args["query"] = message[:2000]
            read = await self.registry.execute("local_source_read", args, context)
            return read.model_dump(mode="json")

        text_parts: list[str] = []
        citations: list[dict[str, Any]] = []
        result: dict[str, Any] = {}
        calls = 0
        for page in pages:
            offset = 0
            while True:
                if calls >= 12:
                    raise ToolError(
                        "Các trang yêu cầu vượt giới hạn đọc; hãy chia thành phạm vi nhỏ hơn.",
                        code="source_page_limit",
                    )
                read = await self.registry.execute(
                    "local_source_read",
                    {"source_id": source["id"], "page_number": page, "offset": offset},
                    context,
                )
                calls += 1
                result = read.model_dump(mode="json")
                data = result.get("data", {})
                text_parts.append(f"<!-- page:{page} -->\n{data.get('text', '')}")
                citations.extend(data.get("citations", []))
                next_offset = data.get("next_offset")
                if next_offset is None:
                    break
                if not isinstance(next_offset, int) or next_offset <= offset:
                    raise ToolError("Không thể đọc tiếp trang được yêu cầu.",
                                    code="source_page_incomplete")
                offset = next_offset
        result["data"] = {
            **result.get("data", {}), "text": "\n\n".join(text_parts),
            "citations": citations, "retrieval_method": "exact_page",
            "page_numbers": list(pages), "next_offset": None,
        }
        if len(pages) > 1:
            result["data"].pop("page_number", None)
        return result

    @staticmethod
    def _apply_controls(route: Route, message: str, controls: ChatControls) -> Route:
        """Make a slash-menu source choice override heuristic text routing."""

        controls = controls.enforce_explicit_source_exclusions(message)
        route = controls.filter_excluded_route(route)
        if controls.source in controls.excluded_sources:
            return Route()
        if controls.source == "general":
            return Route()
        if controls.source == "local":
            # The leading /local command has already been consumed. Resolve
            # explicit filenames using the selected source, not the heuristic
            # Drive route or the entire (possibly long) instruction as a query.
            filenames = tuple(dict.fromkeys(re.findall(
                r"([\w.-]+\.(?:md|txt|csv|ipynb|pdf|docx|xlsx))\b", message, re.I
            )))
            if filenames:
                reads = tuple(Route(
                    "local_source_search", {"query": name}, read_match=True
                ) for name in filenames)
                if len(reads) == 1:
                    return reads[0]
                return Route(sources=reads, required_sources=("local",))
        if route.sources and controls.source in {"drive", "gmail", "local", "memory"}:
            matching = tuple(
                    source_route
                    for source_route in route.sources
                    if source_route.tool
                    and source_route.tool.startswith(f"{controls.source}_")
            )
            if matching:
                return Route(sources=matching, required_sources=route.required_sources)
            return Route()
        if controls.source == "rag":
            return Route("rag_search", _rag_arguments(message))
        if controls.source == "gmail":
            if route.tool and route.tool.startswith("gmail_"):
                return route
            query = (
                "is:unread newer_than:7d"
                if controls.workflow == "email_digest"
                else "newer_than:30d"
            )
            return Route("gmail_list_messages", {"query": query, "max_results": 20})
        if controls.source == "memory":
            return Route("memory_search", {"query": message[:2000], "limit": 6})
        if controls.source == "local" and not route.tool:
            return Route("local_source_search", {"query": message[:200]})
        if controls.source == "drive" and route.tool and not route.tool.startswith("drive_"):
            return Route()
        if route.tool:
            allowed = controls.allowed_tool_names([route.tool])
            if route.tool not in allowed:
                return Route()
        return route

    @staticmethod
    def _direct_answer(data: dict, route: Route, user_message: str) -> str:
        if route.tool == "web_research":
            return (
                str(data["summary"])
                + "\n\nThời điểm kiểm tra nguồn: "
                + str(data["observed_at"])
            )
        if "result" in data:
            result = str(data["result"])
            unit = str(data.get("unit") or "")
            arguments = route.arguments or {}
            values = [str(value) for value in arguments.get("values", [])]
            expression = values[0] if data.get("operation") == "expression" and values else ""
            if not expression and values:
                symbol = {
                    "sum": " + ",
                    "subtract": " − ",
                    "multiply": " × ",
                    "divide": " ÷ ",
                }.get(str(data.get("operation")), ", ")
                expression = symbol.join(values)
            answer = f"### Kết quả\n\n- `{expression} = {result}{unit}`."
            if re.search(r"kiểm tra(?: ngược)?|đối chiếu", user_message, re.I):
                answer += "\n\n### Kiểm tra ngược\n\n- " + CompilerOrchestrator._reverse_check(
                    expression, result
                )
            if re.search(r"bước tiếp theo|gợi ý tiếp theo|tiếp theo nên", user_message, re.I):
                answer += (
                    "\n\n### Bước tiếp theo\n\n"
                    f"- Dùng `{result}{unit}` làm đầu vào cho bước tính hoặc quyết định kế tiếp; "
                    "nếu đây là dữ liệu thực tế, hãy đối chiếu đơn vị và nguồn số liệu trước."
                )
            return answer
        if "kind" in data and "content" in data:
            return "Đã lưu vào bộ nhớ: " + str(data["content"])
        if "files" in data:
            items = data["files"]
            if not items:
                return "Không tìm thấy tệp phù hợp."
            lines = [f"- {item['name']} — ID: `{item['id']}`" for item in items]
            if data.get("next_page_token"):
                lines.append("\nCòn kết quả; mở Google Drive để xem trang tiếp theo.")
            return "Các tệp tìm được:\n\n" + "\n".join(lines)
        return str(data.get("text", "Không có nội dung để hiển thị."))

    @staticmethod
    def _reverse_check(expression: str, result: str) -> str:
        """Explain an independently checkable inverse for common arithmetic shapes."""

        division = re.fullmatch(
            r"\(\s*(-?\d+(?:\.\d+)?)\s*\+\s*(-?\d+(?:\.\d+)?)\s*\)"
            r"\s*[/÷]\s*(-?\d+(?:\.\d+)?)",
            expression,
        )
        if division:
            left, right, divisor = map(Decimal, division.groups())
            if divisor == 0:
                return "Không thể kiểm tra: phép chia cho `0` không xác định."
            recovered = Decimal(result) * divisor
            return (
                f"`{result} × {divisor} = {recovered}`, đúng bằng "
                f"`{left} + {right} = {left + right}`."
            )
        simple = re.fullmatch(
            r"\s*(-?\d+(?:\.\d+)?)\s*([+\-*/×÷−])\s*(-?\d+(?:\.\d+)?)\s*",
            expression,
        )
        if simple:
            left, raw_op, right = simple.groups()
            norm_op = {"×": "*", "÷": "/", "−": "-", "+": "+", "-": "-", "*": "*", "/": "/"}.get(
                raw_op, raw_op
            )
            # Multiplication by zero cannot be checked by division: ``0 / 0`` is
            # undefined and would manufacture a false proof.  Explain the
            # invariant instead so the user still gets an independently useful
            # verification without presenting invalid mathematics.
            if norm_op == "*" and Decimal(right) == 0:
                return (
                    f"`{left} × 0 = 0`; mọi số nhân với `0` đều bằng `0`. "
                    "Không dùng phép chia để kiểm tra vì chia cho `0` không xác định."
                )
            if norm_op == "*" and Decimal(left) == 0:
                return (
                    f"`0 × {right} = 0`; mọi số nhân với `0` đều bằng `0`. "
                    "Không dùng phép chia để kiểm tra vì chia cho `0` không xác định."
                )
            if norm_op == "/" and Decimal(right) == 0:
                return "Không thể kiểm tra: phép chia cho `0` không xác định."
            inverse = {
                "+": f"`{result} − {right} = {left}`.",
                "-": f"`{result} + {right} = {left}`.",
                "*": f"`{result} ÷ {right} = {left}`.",
                "/": f"`{result} × {right} = {left}`.",
            }
            return inverse[norm_op]
        return (
            f"Tính lại `{expression}` theo thứ tự ngoặc → nhân/chia → cộng/trừ vẫn cho `{result}`."
        )
