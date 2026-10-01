"""Validate explicit presentation requirements and requested action structure.

This guard is intentionally narrow.  It does not grade truth or silently embellish
answers.  It runs only when the user gave a measurable format contract, asks the
same approved Gemini model for a faithful rewrite, then validates the rewrite
again.  Tool evidence and citation markers are supplied as immutable text; no tool
or external write is available during repair.
"""

import asyncio
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from google import genai
from google.genai import errors, types

from app.agent.presentation import (
    explicit_presentation_contract,
    presentation_contract_violations,
)
from app.core.config import APPROVED_GEMINI_MODELS
from app.services.quota import QuotaGuard, conservative_tokens

_VIOLATION_LABELS = {
    "below_explicit_word_minimum": "ngắn hơn độ dài bạn yêu cầu",
    "above_explicit_word_maximum": "dài hơn độ dài bạn yêu cầu",
    "below_explicit_bullet_minimum": "chưa đủ số gạch đầu dòng",
    "below_explicit_numbered_step_minimum": "chưa đủ số bước",
    "below_explicit_heading_minimum": "chưa tách đủ các phần phân tích",
    "missing_explicit_markdown_table": "chưa có bảng Markdown đúng yêu cầu",
    "citation_markers_changed": "bản sửa có thể làm thay đổi trích dẫn",
    "numeric_claims_added": "bản sửa đã thêm số liệu không có trong bản gốc",
    "source_sections_dropped": "bản sửa bỏ mất phần chính của bản gốc",
    "rewrite_truncated": "bản sửa bị cắt trước khi hoàn thành",
    "missing_action_section": "chưa có phần hành động và ngưỡng kích hoạt đã yêu cầu",
    "numeric_comparison_inconsistent": "có phép so sánh số học không nhất quán",
}


def _best_effort_answer(answer: str, violations: list[str]) -> str:
    """Return useful content with an honest, compact format warning.

    Presentation constraints are secondary to preserving a valid answer.  A
    formatting miss must therefore remain visible and auditable, but must not
    turn a successful research/tool run into an empty HTTP error.
    """

    labels = [_VIOLATION_LABELS.get(item, item.replace("_", " ")) for item in violations]
    warning = "; ".join(dict.fromkeys(labels))
    return (
        f"{answer.rstrip()}\n\n"
        f"> **Lưu ý về định dạng:** Câu trả lời hữu ích đã được giữ lại, nhưng {warning}."
    )


def _truncate_at_sentence_boundary(text: str, max_words: int) -> str:
    """Honor a concise-only contract without cutting through a sentence.

    This fallback is intentionally restricted to citation-free answers whose only
    remaining violation is length. It removes trailing detail but never rewrites a
    fact, invents content, or hides a missing structural requirement.
    """

    sentences = [
        item.strip()
        for item in re.split(r"(?<=[.!?])\s+", text.strip())
        if item.strip()
    ]
    kept: list[str] = []
    for sentence in sentences:
        candidate = " ".join([*kept, sentence])
        if len(re.findall(r"\b\w+\b", candidate, flags=re.UNICODE)) > max_words:
            break
        kept.append(sentence)
    if kept:
        return " ".join(kept)
    words = re.findall(r"\S+", text.strip())
    return " ".join(words[:max_words]).rstrip(" ,;:") + "…"


def _compact_markdown_sections(text: str, max_words: int) -> str:
    """Reduce verbose citation-free prose while preserving every section.

    Long business answers commonly place risks and next steps at the end. A
    naive tail cut meets the word count but silently deletes those deliverables.
    This compactor keeps headings, tables and code intact, then shortens prose
    proportionally inside each section without adding or rephrasing facts.
    """

    def count(value: str) -> int:
        return len(re.findall(r"\b\w+\b", value, flags=re.UNICODE))

    def shorten_fragment(value: str, budget: int) -> str:
        if count(value) <= budget:
            return value.strip()
        sentences = [
            item.strip()
            for item in re.split(r"(?<=[.!?])\s+", value.strip())
            if item.strip()
        ]
        kept: list[str] = []
        for sentence in sentences:
            candidate = " ".join([*kept, sentence])
            if count(candidate) > budget:
                break
            kept.append(sentence)
        if kept:
            return " ".join(kept)
        # An unfinished action loses its owner, condition or verification step.
        # Keep the complete sentence and let the bounded rewrite handle length.
        return value.strip()

    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    if count(text) <= max_words or not blocks:
        return text.strip()
    fixed_words = 0
    shrinkable: list[tuple[int, int]] = []
    for index, block in enumerate(blocks):
        block_words = count(block)
        is_heading = bool(re.fullmatch(r"#{1,6}\s+[^\n]+", block))
        is_table = "|" in block and bool(re.search(r"(?m)^\s*\|?\s*:?-{3,}", block))
        is_code = block.startswith("```") and block.endswith("```")
        if is_heading or is_table or is_code or block_words <= 18:
            fixed_words += block_words
        else:
            shrinkable.append((index, block_words))
    if not shrinkable:
        return _truncate_at_sentence_boundary(text, max_words)
    target = max(1, max_words - 8)
    adjustable_budget = max(1, target - fixed_words)
    adjustable_words = sum(words for _, words in shrinkable)
    ratio = min(1.0, adjustable_budget / adjustable_words)
    for index, block_words in shrinkable:
        budget = max(14, int(block_words * ratio))
        block = blocks[index]
        lines = block.splitlines()
        if all(re.match(r"^\s*(?:[-*]|\d+[.)])\s+", line) for line in lines if line.strip()):
            per_line = max(8, budget // max(1, len(lines)))
            shortened_lines = []
            for line in lines:
                marker = re.match(r"^(\s*(?:[-*]|\d+[.)])\s+)(.*)$", line)
                shortened_lines.append(
                    marker.group(1) + shorten_fragment(marker.group(2), per_line)
                    if marker else shorten_fragment(line, per_line)
                )
            blocks[index] = "\n".join(shortened_lines)
        else:
            blocks[index] = shorten_fragment(block, budget)
    compacted = "\n\n".join(blocks).strip()
    if count(compacted) > max_words:
        # A final small pass targets the largest prose block, still preserving
        # all headings and the end sections.
        excess = count(compacted) - max_words + 4
        candidates = sorted(shrinkable, key=lambda item: count(blocks[item[0]]), reverse=True)
        for index, _ in candidates:
            current = count(blocks[index])
            if current <= 18:
                continue
            reduction = min(excess, current - 14)
            blocks[index] = shorten_fragment(blocks[index], current - reduction)
            excess -= reduction
            if excess <= 0:
                break
        compacted = "\n\n".join(blocks).strip()
    return compacted


def _numeric_literals(text: str) -> set[str]:
    """Numbers in a format-only rewrite must already exist in the draft."""

    literals = re.findall(r"(?<!\w)\d+(?:[.,]\d+)*(?!\w)", text)
    normalized = set()
    for literal in literals:
        try:
            normalized.add(str(_comparison_value(literal).normalize()))
        except (InvalidOperation, ValueError):
            normalized.add(literal)
    return normalized


# Do not treat the numeric suffix/prefix in labels such as ``Day-1`` or
# ``7-day`` as an arithmetic operand.  Those labels commonly occur beside a
# real threshold ("Day-1 churn vượt 6%") and otherwise create a false 1 > 6
# contradiction.
_COMPARISON_NUMBER = r"(?<![\w/-])(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)(?![\w/-])"
_EXPLICIT_COMPARISON = re.compile(
    rf"(?P<left>{_COMPARISON_NUMBER})"
    r"(?P<context>[^\d\n.!?;]{0,48}?)"
    r"(?P<operator>vượt(?:\s+qua)?|lớn\s+hơn|cao\s+hơn|nhiều\s+hơn|"
    r"nhỏ\s+hơn|thấp\s+hơn|ít\s+hơn)"
    r"(?P<right_context>[^\d\n.!?;]{0,30}?)"
    rf"(?P<right>{_COMPARISON_NUMBER})",
    re.I,
)


def _comparison_value(raw: str) -> Decimal:
    # Vietnamese grouping uses periods and decimal commas. A single period
    # followed by fewer than three digits is also accepted as a decimal point.
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", raw):
        return Decimal(raw.replace(".", "").replace(",", "."))
    return Decimal(raw.replace(",", "."))


def _explicit_numeric_comparison_violations(answer: str) -> list[str]:
    """Catch only directly stated, same-scale numerical contradictions.

    This is not a general factuality grader. Avoid comparing figures with
    explicit different scale units (for example triệu versus nghìn), which
    would require unit conversion and domain context.
    """

    for match in _EXPLICIT_COMPARISON.finditer(answer):
        context = (match.group("context") + match.group("right_context")).lower()
        # A comma can introduce a different subject ("250 chiếc, phần đệm cao
        # hơn ... 590"). The second number can also be a delta, not a threshold.
        if "," in match.group("context") or re.search(
            r"\b(?:tới|thêm|là)\b", match.group("right_context"), re.I
        ):
            continue
        if re.search(r"\b(?:triệu|nghìn|ngàn|tỷ)\b", context):
            continue
        # A threshold sentence can place a count on the left and a duration on
        # the right ("18 trường hợp vượt ngưỡng 48 giờ"). Comparing 18 with 48
        # in that sentence is a dimensional error in the guard, not in the
        # answer. Only run arithmetic consistency checks when both operands
        # describe the same measurable dimension.
        left_window = answer[max(0, match.start() - 36):match.start("operator")].lower()
        right_window = answer[match.start("operator"):min(len(answer), match.end() + 24)].lower()
        dimension_patterns = {
            "count": (r"\b(?:trường\s+hợp|giao\s+dịch|đơn\s+vị|học\s+sinh|"
                      r"email|thư|tệp|file|chiếc|sản\s+phẩm)\b"),
            "time": r"\b(?:thời\s+gian|giây|phút|giờ|ngày|tuần|tháng|năm)\b",
            "rate": r"%|\b(?:phần\s+trăm|tỷ\s+lệ)\b",
            "money": r"\b(?:đồng|vnd|usd|eur|chi\s+phí|doanh\s+thu)\b",
        }
        left_dimensions = {
            name for name, pattern in dimension_patterns.items()
            if re.search(pattern, left_window, re.I)
        }
        right_dimensions = {
            name for name, pattern in dimension_patterns.items()
            if re.search(pattern, right_window, re.I)
        }
        if left_dimensions and right_dimensions and left_dimensions.isdisjoint(right_dimensions):
            continue
        left = _comparison_value(match.group("left"))
        right = _comparison_value(match.group("right"))
        operator = match.group("operator").lower()
        greater = operator.startswith(("vượt", "lớn", "cao", "nhiều"))
        if (greater and left <= right) or (not greater and left >= right):
            return ["numeric_comparison_inconsistent"]
    return []


def _major_headings(text: str) -> int:
    return len(re.findall(r"(?m)^\s{0,3}##\s+\S", text))


def _asks_for_action_triggers(user_message: str) -> bool:
    asks_for_actions = bool(
        re.search(r"\b(?:đề\s+xuất|khuyến\s+nghị)\s+hành\s+động\b", user_message, re.I)
    )
    asks_for_triggers = bool(re.search(r"\btrigger|ngưỡng\s+kích\s+hoạt\b", user_message, re.I))
    return asks_for_actions and asks_for_triggers


def proactive_action_instruction(user_message: str) -> str:
    """Put requested actions early so long analyses cannot crowd them out."""

    if not _asks_for_action_triggers(user_message):
        return ""
    return (
        "Ràng buộc đầu ra: sau kết luận ngắn, trình bày ngay mục "
        "`## Hành động và trigger` với các bullet nêu việc làm, điều kiện kích hoạt "
        "định lượng có cơ sở và cách kiểm chứng. Sau đó mới phân tích số liệu, giả định "
        "và rủi ro. Không dồn toàn bộ khuyến nghị xuống cuối vì có thể vượt giới hạn từ. "
        "Kiểm lại phép tính trước khi kết luận, phân biệt kết quả cơ sở với kịch bản "
        "trì hoãn/biến động; không gọi tồn dương là thiếu hàng. Với hành động có thời gian "
        "chờ, chỉ đề xuất nếu còn đủ thời gian tác động hoặc ghi rõ phụ thuộc và lựa chọn "
        "ứng phó ngắn hạn. Tránh khẳng định tuyệt đối về an toàn. "
        "Không bịa ngưỡng khi dữ liệu chưa đủ."
        " Không mặc định có kho phụ trợ, nhà cung cấp thay thế, quyền duyệt hoặc ngân sách "
        "khi nguồn chưa xác nhận. Mỗi lựa chọn phụ thuộc nguồn lực chưa biết phải ghi rõ "
        "'nếu có/được duyệt' và điều kiện về thời gian đến; không biến phương án có điều kiện "
        "thành hành động chắc chắn thực hiện được."
    )


def _explicit_action_violations(user_message: str, answer: str) -> list[str]:
    """Check a narrowly explicit business deliverable, not general truth."""

    if not _asks_for_action_triggers(user_message):
        return []
    action_headings = list(re.finditer(
        r"(?m)^\s{0,3}#{1,3}\s*(?:\d+[.)]\s*)?"
        r"(?:đề\s+xuất|khuyến\s+nghị|hành\s+động|action|recommendation)[^\n]*$",
        answer,
        re.I,
    ))
    for action_heading in action_headings:
        heading_level = len(re.match(r"\s*(#{1,3})", action_heading.group()).group(1))
        following = answer[action_heading.end():]
        next_peer_heading = re.search(
            rf"(?m)^\s{{0,3}}#{{1,{heading_level}}}\s+\S", following
        )
        action_section = following[:next_peer_heading.start()] if next_peer_heading else following
        bullets = re.findall(
            r"(?ms)^\s*(?:[-*]|\d+[.)])\s+(.+?)(?=^\s*(?:[-*]|\d+[.)])\s+|\Z)",
            action_section,
        )
        if any(
            re.search(r"\b(?:trigger|ngưỡng|khi|nếu|dưới|trên)\b", bullet, re.I)
            and re.search(r"(?<!\w)\d+(?:[.,]\d+)*(?!\w)", bullet)
            for bullet in bullets
        ):
            return []
    return ["missing_action_section"]


async def enforce_presentation_contract(
    *,
    client: genai.Client,
    quota: QuotaGuard,
    user_message: str,
    answer: str,
    model_name: str,
    fallback_model: str,
    records: list[dict[str, Any]],
    verified_calculations: dict[str, Any] | None = None,
) -> str:
    """Return a validated rewrite, or a clearly labelled best-effort draft."""

    numeric_violations = _explicit_numeric_comparison_violations(answer)
    if numeric_violations:
        records.append(
            {
                "stage": "output_contract",
                "status": "degraded",
                "violations": numeric_violations,
                "repair_calls": 0,
                "reason": "explicit_numeric_comparison_inconsistent",
            }
        )
        return _best_effort_answer(answer, numeric_violations)

    contract = explicit_presentation_contract(user_message)
    if not contract.active:
        # An actionable decision can be explicitly requested without a word
        # count or table. Do not mark a missing deliverable as completed just
        # because there is no measurable formatting contract, and do not spend
        # an extra provider call merely to repair it.
        action_violations = _explicit_action_violations(user_message, answer)
        if not action_violations:
            return answer
        records.append(
            {
                "stage": "output_contract",
                "status": "degraded",
                "violations": action_violations,
                "repair_calls": 0,
                "reason": "explicit_action_missing_without_format_contract",
            }
        )
        return _best_effort_answer(answer, action_violations)
    initial = presentation_contract_violations(answer, contract)
    initial.extend(_explicit_action_violations(user_message, answer))
    if not initial:
        records.append(
            {
                "stage": "output_contract",
                "status": "success",
                "contract": contract.instruction(),
                "repair_calls": 0,
            }
        )
        return answer
    if (
        initial == ["above_explicit_word_maximum"]
        and contract.min_words is not None
        and contract.max_words is not None
        and contract.max_words >= 200
        and not re.findall(r"\[(\d+)\]", answer)
    ):
        compacted = _compact_markdown_sections(answer, contract.max_words)
        if (not presentation_contract_violations(compacted, contract)
                and _numeric_literals(compacted) == _numeric_literals(answer)):
            records.append(
                {
                    "stage": "output_contract",
                    "status": "corrected_locally",
                    "contract": contract.instruction(),
                    "initial_violations": initial,
                    "repair_calls": 0,
                    "reason": "section_preserving_compaction",
                }
            )
            return compacted

    target_length = ""
    measured_words = len(re.findall(r"\b\w+\b", answer, flags=re.UNICODE))
    if contract.min_words is not None and contract.max_words is not None:
        midpoint = (contract.min_words + contract.max_words) // 2
        # Aiming at the midpoint gives the rewrite room on both sides; asking
        # merely for the upper bound made smaller Flash models routinely drift
        # 15–25% over it when tables were also requested.
        target_length = (
            f"Hard length target: aim for about {midpoint} words and count the visible "
            f"answer before returning it; stay between {contract.min_words} and "
            f"{contract.max_words} words."
        )
    elif contract.max_words is not None:
        target_length = (
            f"Hard length target: aim for fewer than {contract.max_words} words and count "
            "the visible answer before returning it."
        )
    prompt = json.dumps(
        {
            "task": (
                "Rewrite the draft in Vietnamese so it meets the explicit presentation "
                "contract. Preserve every fact, qualification, code literal and citation "
                "marker exactly; do not add facts, sources, actions or citations. Return "
                "only the revised Markdown answer. The explicit contract is a hard gate, "
                "not a suggestion. For a depth request, expand by explaining the relevant "
                "mechanism, evidence, consequences, limitations and practical implications "
                "that are already supported by the draft/source. Do not pad, repeat ideas, "
                "or invent missing facts or numerical examples. You may include exact results "
                "from verified_calculations when supplied, preserving their assumptions and units. "
                "Preserve every substantive "
                "section, especially the final recommendations; shorten repetition within "
                "each section rather than dropping the end of the answer. Complete the "
                "entire response before stopping. If the user explicitly requests "
                "actionable recommendations with quantitative triggers, retain their "
                "action section and concrete bullet conditions near the beginning."
            ),
            "explicit_contract": contract.instruction(),
            "depth_requirements": list(contract.depth_guidance),
            "length_control": target_length,
            "measured_draft_words": measured_words,
            "words_needed_to_minimum": max(0, (contract.min_words or 0) - measured_words),
            "revision_guidance": (
                "The server measured the draft, not the model. If short, explain additional "
                "supported mechanisms, assumptions, trade-offs and verification steps to reach "
                "the midpoint, not merely the minimum. Allocate space to each requested section. "
                "Do not repeat calculations as prose padding. Where resources or permissions "
                "are not verified, retain or add explicit conditional qualifications; never "
                "invent their availability. If evidence cannot support the requested depth, "
                "state that limitation rather than inventing facts."
            ),
            "user_request_untrusted": user_message,
            "draft_answer_untrusted": answer,
            "verified_calculations": verified_calculations,
        },
        ensure_ascii=False,
    )
    try:
        await asyncio.to_thread(
            quota.reserve,
            "flash",
            conservative_tokens(prompt, 6144),
        )
    except Exception as exc:
        if (
            initial == ["above_explicit_word_maximum"]
            and contract.max_words is not None
            and not re.findall(r"\[(\d+)\]", answer)
        ):
            shortened = _truncate_at_sentence_boundary(answer, contract.max_words)
            if not presentation_contract_violations(shortened, contract):
                records.append(
                    {
                        "stage": "output_contract",
                        "status": "corrected_locally",
                        "contract": contract.instruction(),
                        "initial_violations": initial,
                        "repair_calls": 0,
                        "reason": type(exc).__name__,
                    }
                )
                return shortened
        records.append(
            {
                "stage": "output_contract",
                "status": "degraded",
                "contract": contract.instruction(),
                "violations": initial,
                "repair_calls": 0,
                "reason": type(exc).__name__,
            }
        )
        return _best_effort_answer(answer, initial)
    used_model = model_name
    try:
        response = await client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=6144,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
    except errors.APIError as exc:
        effective_fallback = fallback_model
        if effective_fallback == model_name:
            effective_fallback = next(
                (candidate for candidate in sorted(APPROVED_GEMINI_MODELS)
                 if candidate != model_name),
                "",
            )
        if exc.code not in {404, 429, 500, 502, 503, 504} or not effective_fallback:
            records.append(
                {
                    "stage": "output_contract",
                    "status": "failed",
                    "violations": initial,
                    "repair_calls": 1,
                    "provider_code": exc.code,
                }
            )
            return _best_effort_answer(answer, initial)
        try:
            # A fallback is a second real provider call. Never bypass the
            # free-tier reservation simply because the first call failed.
            await asyncio.to_thread(
                quota.reserve,
                "flash",
                conservative_tokens(prompt, 6144),
            )
        except Exception as quota_exc:
            records.append(
                {
                    "stage": "output_contract",
                    "status": "degraded",
                    "contract": contract.instruction(),
                    "violations": initial,
                    "repair_calls": 1,
                    "provider_code": exc.code,
                    "fallback_blocked_by": type(quota_exc).__name__,
                }
            )
            return _best_effort_answer(answer, initial)
        used_model = effective_fallback
        try:
            response = await client.aio.models.generate_content(
                model=effective_fallback,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=6144,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
        except errors.APIError as fallback_exc:
            records.append(
                {
                    "stage": "output_contract",
                    "status": "degraded",
                    "contract": contract.instruction(),
                    "violations": initial,
                    "repair_calls": 2,
                    "provider_code": fallback_exc.code,
                }
            )
            return _best_effort_answer(answer, initial)

    candidate = (response.text or "").strip()
    remaining = (
        presentation_contract_violations(candidate, contract)
        if candidate else initial.copy()
    )
    if candidate:
        remaining.extend(_explicit_action_violations(user_message, candidate))
        remaining.extend(_explicit_numeric_comparison_violations(candidate))
    original_markers = re.findall(r"\[(\d+)\]", answer)
    candidate_markers = re.findall(r"\[(\d+)\]", candidate)
    if original_markers != candidate_markers:
        remaining.append("citation_markers_changed")
    permitted_numbers = _numeric_literals(answer)
    if verified_calculations:
        permitted_numbers |= _numeric_literals(json.dumps(verified_calculations))
    if _numeric_literals(candidate) - permitted_numbers:
        remaining.append("numeric_claims_added")
    if _major_headings(answer) >= 2 and _major_headings(candidate) < _major_headings(answer):
        remaining.append("source_sections_dropped")
    candidates = getattr(response, "candidates", None) or []
    if (
        candidates
        and getattr(candidates[0], "finish_reason", None) == types.FinishReason.MAX_TOKENS
    ):
        remaining.append("rewrite_truncated")
    if (
        remaining == ["above_explicit_word_maximum"]
        and contract.max_words is not None
        and not candidate_markers
    ):
        shortened = _truncate_at_sentence_boundary(candidate, contract.max_words)
        shortened_violations = presentation_contract_violations(shortened, contract)
        if not shortened_violations:
            records.append(
                {
                    "stage": "output_contract",
                    "status": "corrected_locally",
                    "contract": contract.instruction(),
                    "initial_violations": initial,
                    "repair_calls": 1,
                    "model": used_model,
                }
            )
            return shortened
    if remaining:
        records.append(
            {
                "stage": "output_contract",
                "status": "degraded",
                "contract": contract.instruction(),
                "violations": remaining,
                "repair_calls": 1,
                "model": used_model,
            }
        )
        # A rewrite that changed citation markers is less trustworthy than the
        # original. Otherwise the repaired candidate is the most useful draft,
        # even when it misses a soft presentation requirement by a small margin.
        unsafe_rewrite = {
            "citation_markers_changed",
            "numeric_claims_added",
            "source_sections_dropped",
            "rewrite_truncated",
            "numeric_comparison_inconsistent",
            "missing_action_section",
        }
        best_draft = answer if unsafe_rewrite.intersection(remaining) else candidate or answer
        return _best_effort_answer(best_draft, remaining)
    records.append(
        {
            "stage": "output_contract",
            "status": "corrected",
            "contract": contract.instruction(),
            "initial_violations": initial,
            "repair_calls": 1,
            "model": used_model,
        }
    )
    return candidate
