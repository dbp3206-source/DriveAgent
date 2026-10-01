"""Repeatable evaluation slices that do not spend quota or touch user data.

The course material separates final task success, trajectory quality, RAG quality,
human feedback and regression testing. This module intentionally labels its small
offline suite as a *routing regression*, not as an overall product score.
"""

import json
import re
from pathlib import Path
from typing import Any

from app.agent.response_guard import categorical_claim_lines
from app.agent.routing import route_request

EVAL_ROOT = Path(__file__).resolve().parents[2] / "evals"
GOLDEN_ROUTES = EVAL_ROOT / "golden_routes.json"
GOLDEN_OUTPUTS = EVAL_ROOT / "golden_output_quality.json"
GOLDEN_CONTRACTS = EVAL_ROOT / "golden_answer_contracts.json"


def classify_answer_intent(question: str) -> str:
    """Classify only for QA rubric selection, never for production routing."""

    value = question.casefold()
    email_markers = ("email", "hộp thư", "gmail", "thư chưa đọc")
    if any(marker in value for marker in email_markers):
        if any(
            marker in value
            for marker in (
                "tổng hợp",
                "phân loại",
                "triage",
                "cần trả lời",
                "cần theo dõi",
                "bản tin",
            )
        ):
            return "email_digest"
        if any(
            marker in value
            for marker in ("liệt kê", "danh sách", "gần đây", "mới nhất", "recent")
        ):
            return "email_list"
    rules = (
        ("compare", ("so sánh", "khác nhau", "nên chọn", "ưu nhược")),
        ("howto", ("hướng dẫn", "từng bước", "làm thế nào", "cách ")),
        ("plan", ("lên kế hoạch", "lập kế hoạch", "lộ trình", "roadmap")),
        ("diagnosis", ("lỗi", "không hoạt động", "chẩn đoán", "vì sao")),
        ("summary", ("tóm tắt", "ý chính", "đúc kết")),
        ("study", ("cheatsheet", "ôn tập", "giải thích", "ví dụ")),
    )
    for intent, markers in rules:
        if any(marker in value for marker in markers):
            return intent
    return "direct" if len(value.split()) <= 12 else "general"


def _has_markdown_table(answer: str) -> bool:
    lines = answer.splitlines()
    return any(
        "|" in lines[index - 1]
        and re.fullmatch(r"\s*\|?\s*:?-{3,}.*", line)
        for index, line in enumerate(lines[1:], start=1)
    )


_NUMBER_TOKEN = re.compile(
    r"(?<!\w)(?<![+-])(?<!\d[.,/])(?P<number>[+-]?\d+(?:[.,/]\d+)*)(?!\w)(?![.,/]\d)"
)


def _canonical_decimal_token(value: str) -> str:
    """Treat comma and dot as equivalent decimal separators for locale output.

    Fractions and multi-separator values remain exact because their meaning can be
    ambiguous (for example thousands grouping versus multiple decimal components).
    """

    if "/" in value:
        return value
    unsigned = value[1:] if value[:1] in {"+", "-"} else value
    if unsigned.count(",") + unsigned.count(".") != 1:
        return value
    return value.replace(",", ".")


def _fact_spans(text: str, fact: str) -> list[tuple[int, int]]:
    """Find whole-word facts; numeric facts must match a complete number token.

    Plain substring checks let an expected ``4`` match ``14`` and ``cat`` match
    ``concatenate``.  Numeric tokenization also rejects partial decimal/fraction
    matches such as ``4`` inside ``4,5`` or ``4/5``.
    """

    value = " ".join(fact.split())
    if not value:
        return []
    if re.fullmatch(r"[+-]?\d+(?:[.,/]\d+)*", value):
        expected_number = _canonical_decimal_token(value)
        return [
            match.span("number")
            for match in _NUMBER_TOKEN.finditer(text)
            if _canonical_decimal_token(match.group("number")) == expected_number
        ]

    terms = value.split()
    # Markdown emphasis/code delimiters are presentation, not semantic text.
    # Accept them between terms while preserving original offsets for the
    # same-line citation check (for example ``từ `1` đến `14```).
    separator = r"(?:\s|[*_`])+"
    pattern = re.compile(
        r"(?<!\w)" + separator.join(re.escape(term) for term in terms) + r"(?!\w)",
        re.IGNORECASE,
    )
    return [match.span() for match in pattern.finditer(text)]


def _contains_fact(text: str, fact: str) -> bool:
    return bool(_fact_spans(text, fact))


def _line_citation_indices(text: str, span: tuple[int, int]) -> list[int]:
    start = text.rfind("\n", 0, span[0]) + 1
    end = text.find("\n", span[1])
    line = text[start:] if end == -1 else text[start:end]
    return [
        int(item)
        for match in re.finditer(r"\[(\s*\d+(?:\s*[,;]\s*\d+)*\s*)\]", line)
        for item in re.findall(r"\d+", match.group(1))
    ]


def _line_has_citation(text: str, span: tuple[int, int], citation_index: int) -> bool:
    return citation_index in _line_citation_indices(text, span)


def _check_claim_citations(
    answer: str,
    citations: list[dict[str, Any]],
    expectations: list[dict[str, Any]],
) -> list[str]:
    """Check answer-key claim/source bindings, not semantic entailment.

    A binding may fix a 1-based citation index, or bind by source/page when the
    model assigns dynamic reference numbers. Literal snippet facts are still
    weaker than human semantic entailment review.
    """

    failures: list[str] = []
    for item in expectations:
        if not isinstance(item, dict):
            failures.append("invalid_citation_expectation")
            continue
        claim = item.get("claim")
        claim_any = item.get("claim_any")
        evidence_fact = item.get("evidence_fact")
        evidence_fact_any = item.get("evidence_fact_any")
        citation_index = item.get("citation_index")
        expected_page = item.get("page_number")
        expected_file_id = item.get("file_id")
        expected_file_name = item.get("file_name")
        claim_options = claim_any if isinstance(claim_any, list) else [claim]
        evidence_options = (
            evidence_fact_any if isinstance(evidence_fact_any, list) else [evidence_fact]
        )
        if (
            not claim_options
            or not all(isinstance(value, str) and value.strip() for value in claim_options)
            or not evidence_options
            or not all(isinstance(value, str) and value.strip() for value in evidence_options)
            or (citation_index is not None and (
                not isinstance(citation_index, int)
                or isinstance(citation_index, bool)
                or citation_index < 1
            ))
            or (expected_page is not None and (
                not isinstance(expected_page, int)
                or isinstance(expected_page, bool)
                or expected_page < 1
            ))
            or not any(
                isinstance(value, str) and value.strip()
                for value in (expected_file_id, expected_file_name)
            )
        ):
            failures.append("invalid_citation_expectation")
            continue

        claim_spans = [
            span for option in claim_options for span in _fact_spans(answer, option)
        ]
        if not claim_spans:
            failures.append("citation_claim_missing")
            continue
        indices = list(dict.fromkeys(
            index
            for span in claim_spans
            for index in _line_citation_indices(answer, span)
        ))
        if citation_index is not None:
            indices = [index for index in indices if index == citation_index]
        if not indices:
            failures.append("citation_claim_marker_missing")
            continue
        valid_indices = [index for index in indices if 1 <= index <= len(citations)]
        if not valid_indices:
            failures.append("invalid_citation_reference")
            continue
        matching = [
            citations[index - 1] for index in valid_indices
            if (not expected_file_id or citations[index - 1].get("file_id") == expected_file_id)
            and (
                not expected_file_name
                or citations[index - 1].get("file_name") == expected_file_name
            )
            and (expected_page is None or citations[index - 1].get("page_number") == expected_page)
        ]
        if not matching:
            failures.append("citation_source_mismatch")
            continue
        if not any(
            isinstance(citation.get("snippet"), str)
            and any(_contains_fact(citation["snippet"], option) for option in evidence_options)
            for citation in matching
        ):
            failures.append("citation_evidence_fact_missing")
    return list(dict.fromkeys(failures))


def evaluate_text_answer(
    question: str,
    answer: str,
    citations: list[dict[str, Any]] | None = None,
    *,
    expected_facts: list[str] | None = None,
    expected_fact_groups: list[list[str]] | None = None,
    forbidden_terms: list[str] | None = None,
    expected_claim_citations: list[dict[str, Any]] | None = None,
    min_words: int | None = None,
    max_words: int | None = None,
    require_citations: bool = False,
    forbid_uncited_categorical_claims: bool = False,
    required_sections: list[str] | None = None,
    require_markdown_table: bool = False,
    min_bullets: int | None = None,
    min_numbered_steps: int | None = None,
) -> dict[str, Any]:
    """Score observable output qualities with explicit, optional hard checks.

    The original rubric only measured typography-like signals.  That is useful for
    feedback, but it must never certify a wrong answer.  Callers that have an answer
    key can now provide ``expected_facts`` and ``forbidden_terms``; those checks are
    intentionally literal/conservative and are reported separately from style
    dimensions.  A model answer without an answer key remains ``not fully verified``.
    """

    citations = citations or []
    intent = classify_answer_intent(question)
    text = answer.strip()
    words = re.findall(r"\b\w+\b", text, flags=re.UNICODE)
    headings = re.findall(r"(?m)^#{1,4}\s+\S", text)
    bullets = re.findall(r"(?m)^\s*[-*]\s+\S", text)
    numbered = re.findall(r"(?m)^\s*\d+[.)]\s+\S", text)
    checkboxes = re.findall(r"(?m)^\s*[-*]\s+\[[ xX]\]\s+\S", text)
    markers = [
        int(value)
        for group in re.findall(r"\[(\s*\d+(?:\s*[,;]\s*\d+)*\s*)\]", text)
        for value in re.findall(r"\d+", group)
    ]
    issues: list[str] = []
    hard_failures: list[str] = []

    heading_texts = [
        match.group(1).strip()
        for match in re.finditer(r"(?m)^#{1,4}\s+(.+?)\s*$", text)
    ]

    if not text:
        hard_failures.append("empty_answer")
    if min_words is not None and len(words) < min_words:
        hard_failures.append("below_minimum_word_count")
        issues.append(f"Câu trả lời cần ít nhất {min_words} từ theo answer key.")
    if max_words is not None and len(words) > max_words:
        hard_failures.append("above_maximum_word_count")
        issues.append(f"Câu trả lời cần tối đa {max_words} từ theo answer key.")
    missing_facts = [fact for fact in (expected_facts or []) if not _contains_fact(text, fact)]
    missing_facts.extend(
        " / ".join(group)
        for group in (expected_fact_groups or [])
        if not any(_contains_fact(text, option) for option in group)
    )
    if missing_facts:
        hard_failures.append("missing_expected_fact")
        issues.append("Thiếu dữ kiện bắt buộc: " + ", ".join(missing_facts))
    forbidden_hits = [term for term in (forbidden_terms or []) if _contains_fact(text, term)]
    if forbidden_hits:
        hard_failures.append("forbidden_claim")
        issues.append("Có claim bị cấm theo answer key: " + ", ".join(forbidden_hits))
    missing_sections = [
        section
        for section in (required_sections or [])
        if not any(_contains_fact(heading, section) for heading in heading_texts)
    ]
    if missing_sections:
        hard_failures.append("missing_required_section")
        issues.append("Thiếu phần bắt buộc: " + ", ".join(missing_sections))
    if require_markdown_table and not _has_markdown_table(text):
        hard_failures.append("missing_required_table")
        issues.append("Answer key yêu cầu bảng Markdown nhưng output chưa có bảng hợp lệ.")
    if min_bullets is not None and len(bullets) < min_bullets:
        hard_failures.append("below_minimum_bullet_count")
        issues.append(f"Answer key yêu cầu ít nhất {min_bullets} bullet rõ ràng.")
    if min_numbered_steps is not None and len(numbered) < min_numbered_steps:
        hard_failures.append("below_minimum_numbered_step_count")
        issues.append(f"Answer key yêu cầu ít nhất {min_numbered_steps} bước đánh số.")
    uncited_categorical_lines = (
        categorical_claim_lines(text)
        if forbid_uncited_categorical_claims and not citations
        else []
    )
    if uncited_categorical_lines:
        hard_failures.append("uncited_categorical_claim")
        issues.append(
            "Có nhận định xếp hạng hoặc khẳng định tuyệt đối nhưng không có citation."
        )

    task_fit = 20
    if intent == "compare" and not _has_markdown_table(text):
        task_fit -= 7
        issues.append("Câu trả lời so sánh chưa có bảng đối chiếu ngắn.")
    if intent == "howto" and len(numbered) < 2:
        task_fit -= 8
        issues.append("Hướng dẫn chưa có các bước đánh số rõ ràng.")
    if intent == "plan" and len(numbered) + len(checkboxes) < 2:
        task_fit -= 8
        issues.append("Kế hoạch chưa thể hiện mốc việc hoặc checklist.")
    if intent == "diagnosis" and not any(
        term in text.casefold()
        for term in ("bằng chứng", "kiểm tra", "nguyên nhân", "giả thuyết")
    ):
        task_fit -= 8
        issues.append("Chẩn đoán chưa tách bằng chứng, kiểm tra hoặc nguyên nhân.")
    if intent in {"summary", "study"} and not (headings or len(bullets) >= 2):
        task_fit -= 6
        issues.append("Nội dung học/tóm tắt chưa được tách thành các ý dễ quét.")
    if intent == "email_digest":
        value = text.casefold()
        if not any(term in value for term in ("cần trả lời", "cần theo dõi", "chỉ để biết")):
            task_fit -= 7
            issues.append("Tổng hợp email chưa tách nhóm hành động rõ ràng.")
        event_times = re.findall(r"thời gian sự kiện\s*:\s*([^\n]+)", value)
        deadlines = re.findall(r"deadline\s*:\s*([^\n]+)", value)
        if any(
            re.search(r"\b\d{1,2}[:h]\d{2}\b", event)
            and any(
                set(re.findall(r"\b\d{1,2}[:h]\d{2}\b", event))
                & set(re.findall(r"\b\d{1,2}[:h]\d{2}\b", deadline))
                for deadline in deadlines
            )
            for event in event_times
        ):
            task_fit -= 10
            issues.append("Giờ diễn ra sự kiện có thể đã bị gắn nhầm thành deadline.")

    structure = 20
    if intent in {
        "general", "compare", "howto", "plan", "diagnosis", "summary", "study", "email_digest"
    }:
        if len(words) >= 100 and not headings:
            structure -= 5
            issues.append("Câu trả lời dài nhưng chưa có tiêu đề phân cấp.")
        if len(words) >= 80 and not (bullets or numbered or _has_markdown_table(text)):
            structure -= 5
            issues.append("Câu trả lời dài nhưng chưa có cấu trúc để quét nhanh.")
    if intent == "direct" and len(words) > 180:
        structure -= 6
        issues.append("Câu hỏi trực tiếp đang nhận câu trả lời dài quá mức cần thiết.")
    if len(headings) > 8:
        structure -= 3
        issues.append("Quá nhiều tiêu đề làm nội dung bị phân mảnh.")

    readability = 15
    if not text:
        readability = 0
        issues.append("Câu trả lời trống.")
    if re.search(r"\$[^$]+\$|\\\(|\\\[", text):
        readability -= 4
        issues.append("Có cú pháp LaTeX mà giao diện hiện không dựng được.")
    if any(re.search(r"(?<=\S)[ \t]{3,}(?=\S)", line) for line in text.splitlines()):
        readability -= 2
        issues.append("Có khoảng trắng thừa làm lỗi nhịp trình bày.")
    if len(max(text.splitlines() or [""], key=len)) > 500:
        readability -= 3
        issues.append("Có đoạn quá dài, khó đọc trên màn hình nhỏ.")

    actionability = 15
    if intent in {"howto", "plan", "diagnosis"} and not any(
        term in text.casefold()
        for term in ("kiểm tra", "hoàn thành", "tiếp theo", "nếu ", "checklist")
    ):
        actionability -= 6
        issues.append("Thiếu cách kiểm tra kết quả hoặc bước tiếp theo.")

    grounding = 25
    citation_failures: list[str] = []
    citation_expectations = expected_claim_citations or []
    if require_citations and not citations:
        grounding -= 25
        hard_failures.append("missing_required_citation")
        issues.append("Answer key yêu cầu citation nhưng output không có evidence.")
    if citations:
        if not markers:
            grounding -= 12
            hard_failures.append("missing_citation_marker")
            issues.append("Có evidence đính kèm nhưng câu trả lời không gắn citation marker.")
        elif not all(1 <= marker <= len(citations) for marker in markers):
            grounding -= 20
            hard_failures.append("invalid_citation_reference")
            issues.append("Có citation marker không trỏ tới evidence hợp lệ.")
        elif not citation_expectations:
            grounding -= 12
            issues.append(
                "Citation marker hợp lệ về số thứ tự, nhưng chưa được đối chiếu với answer key."
            )
    if require_citations and citations and not citation_expectations:
        hard_failures.append("citation_claim_bindings_missing")
        issues.append(
            "Answer key yêu cầu citation nhưng chưa khai báo claim–source binding cần kiểm tra."
        )
    if citation_expectations:
        citation_failures = _check_claim_citations(text, citations, citation_expectations)
        hard_failures.extend(citation_failures)
        if citation_failures:
            issues.append(
                "Claim, citation marker, file nguồn hoặc fact trong snippet không khớp answer key."
            )

    style = 5
    if re.search(r"(?i)\b(unlock|revolutionize|seamless|next[- ]gen|supercharge)\b", text):
        style -= 2
        issues.append("Có cụm marketing sáo rỗng không giúp làm rõ nội dung.")

    dimensions = {
        "task_fit": max(0, task_fit),
        "structure": max(0, structure),
        "readability": max(0, readability),
        "actionability": max(0, actionability),
        "grounding_integrity": max(0, grounding),
        "style": max(0, style),
    }
    score = sum(dimensions.values())
    if hard_failures:
        score = min(score, 59)
    has_answer_key_constraints = bool(
        expected_facts
        or expected_fact_groups
        or forbidden_terms
        or min_words is not None
        or max_words is not None
        or forbid_uncited_categorical_claims
        or required_sections
        or require_markdown_table
        or min_bullets is not None
        or min_numbered_steps is not None
    )
    if citation_expectations:
        citation_status = (
            "answer_key_binding_checked" if not citation_failures else "binding_failed"
        )
    elif citations:
        citation_status = "unverified" if require_citations else "marker_only_unverified"
    else:
        citation_status = "missing" if require_citations else "not_required"
    verification_status = (
        "unverified_required_citation"
        if require_citations and not citation_expectations
        else "answer_key_constraints_checked"
        if has_answer_key_constraints or citation_expectations
        else "presentation_only"
    )

    return {
        "intent": intent,
        "score": score,
        "passed": score >= 80 and not hard_failures,
        "dimensions": dimensions,
        "issues": issues,
        "hard_failures": hard_failures,
        "fact_checks": {
            "checked": has_answer_key_constraints,
            "missing_expected_facts": missing_facts,
            "forbidden_hits": forbidden_hits,
            "uncited_categorical_lines": uncited_categorical_lines,
            "missing_required_sections": missing_sections,
        },
        "verification": {
            "status": verification_status,
            "citation_status": citation_status,
            "citation_failures": citation_failures,
            "semantic_entailment_checked": False,
        },
        "scope": "observable_output_quality_not_factual_correctness",
    }


def run_output_quality_regression(path: Path = GOLDEN_OUTPUTS) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = []
    for case in payload["cases"]:
        result = evaluate_text_answer(
            case["question"],
            case["answer"],
            case.get("citations"),
            expected_facts=case.get("expected_facts"),
            forbidden_terms=case.get("forbidden_terms"),
            expected_claim_citations=case.get("expected_claim_citations"),
            min_words=case.get("min_words"),
            require_citations=case.get("require_citations", False),
            forbid_uncited_categorical_claims=case.get(
                "forbid_uncited_categorical_claims", False
            ),
            required_sections=case.get("required_sections"),
            require_markdown_table=case.get("require_markdown_table", False),
            min_bullets=case.get("min_bullets"),
            min_numbered_steps=case.get("min_numbered_steps"),
        )
        expected_pass = case.get("expected_pass", True)
        candidate_passed = result["passed"]
        passed = (
            result["intent"] == case["expected_intent"]
            and case["min_score"] <= result["score"] <= case["max_score"]
            and candidate_passed is expected_pass
        )
        results.append(
            {
                "id": case["id"],
                **result,
                "candidate_passed": candidate_passed,
                "expected_candidate_passed": expected_pass,
                "passed": passed,
            }
        )
    passed_count = sum(item["passed"] for item in results)
    return {
        "suite": "deterministic-output-quality",
        "version": payload["version"],
        "scope": payload["purpose"],
        "passed": passed_count,
        "total": len(results),
        "pass_rate": round(passed_count / len(results), 4) if results else None,
        "cases": results,
    }


def run_answer_contract_benchmark(path: Path = GOLDEN_CONTRACTS) -> dict[str, Any]:
    """Validate curated reference answers against explicit observable contracts.

    This suite is deliberately not called a live-model benchmark. It proves that the
    release rubric can enforce the content and presentation contracts represented by
    the checked-in examples. A separate authenticated run is still required to score
    answers produced by Gemini, retrieval and Google Workspace tools.
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    coverage = {
        "answer_key_cases": 0,
        "citation_binding_cases": 0,
        "required_section_cases": 0,
        "table_cases": 0,
        "action_structure_cases": 0,
    }
    for case in payload["cases"]:
        has_answer_key = bool(
            case.get("expected_facts")
            or case.get("forbidden_terms")
            or case.get("expected_claim_citations")
            or case.get("required_sections")
            or case.get("require_markdown_table")
            or case.get("min_bullets") is not None
            or case.get("min_numbered_steps") is not None
        )
        if not has_answer_key:
            raise ValueError(f"Contract case {case['id']} has no enforceable answer key")
        coverage["answer_key_cases"] += 1
        coverage["citation_binding_cases"] += int(bool(case.get("expected_claim_citations")))
        coverage["required_section_cases"] += int(bool(case.get("required_sections")))
        coverage["table_cases"] += int(bool(case.get("require_markdown_table")))
        coverage["action_structure_cases"] += int(
            case.get("min_bullets") is not None
            or case.get("min_numbered_steps") is not None
        )
        result = evaluate_text_answer(
            case["question"],
            case["answer"],
            case.get("citations"),
            expected_facts=case.get("expected_facts"),
            forbidden_terms=case.get("forbidden_terms"),
            expected_claim_citations=case.get("expected_claim_citations"),
            min_words=case.get("min_words"),
            require_citations=case.get("require_citations", False),
            forbid_uncited_categorical_claims=case.get(
                "forbid_uncited_categorical_claims", False
            ),
            required_sections=case.get("required_sections"),
            require_markdown_table=case.get("require_markdown_table", False),
            min_bullets=case.get("min_bullets"),
            min_numbered_steps=case.get("min_numbered_steps"),
        )
        passed = (
            result["intent"] == case["expected_intent"]
            and result["passed"]
            and result["score"] >= case.get("min_score", 80)
        )
        results.append(
            {"id": case["id"], **result, "candidate_passed": result["passed"], "passed": passed}
        )
    passed_count = sum(item["passed"] for item in results)
    return {
        "suite": "reference-answer-contracts",
        "version": payload["version"],
        "scope": payload["purpose"],
        "passed": passed_count,
        "total": len(results),
        "pass_rate": round(passed_count / len(results), 4) if results else None,
        "coverage": coverage,
        "live_model_checked": False,
        "cases": results,
    }


def run_adversarial_mutation_regression() -> dict[str, Any]:
    """Exercise 160 deterministic hard negatives across evaluator failure modes.

    These generated mutations prove the release evaluator rejects known-bad
    candidates. They deliberately do *not* count as 160 live product answers.
    """

    cases: list[dict[str, Any]] = []

    def add(category: str, index: int, result: dict[str, Any], expected: str) -> None:
        cases.append(
            {
                "id": f"{category}-{index:03d}",
                "category": category,
                "expected_failure": expected,
                "hard_failures": result["hard_failures"],
                "passed": not result["passed"] and expected in result["hard_failures"],
            }
        )

    for index in range(1, 31):
        expected = str(10_000 + index)
        result = evaluate_text_answer(
            "Giá trị chính xác là gì?",
            f"Giá trị là {20_000 + index}.",
            expected_facts=[expected],
        )
        add("wrong_numeric", index, result, "missing_expected_fact")

    for index in range(1, 21):
        expected = f"{index},5"
        result = evaluate_text_answer(
            "Tỷ lệ chính xác là gì?",
            f"Tỷ lệ là {index}.",
            expected_facts=[expected],
        )
        add("partial_decimal", index, result, "missing_expected_fact")

    for index in range(1, 21):
        fact = f"MOC-BAT-BUOC-{index:02d}"
        result = evaluate_text_answer(
            "Nêu mã bắt buộc.",
            "Câu trả lời không chứa mã nguồn.",
            expected_facts=[fact],
        )
        add("missing_fact", index, result, "missing_expected_fact")

    for index in range(1, 16):
        forbidden = f"FORBIDDEN-{index:02d}"
        result = evaluate_text_answer(
            "Không được nêu kết luận bị cấm.",
            f"Kết luận là {forbidden}.",
            forbidden_terms=[forbidden],
        )
        add("forbidden_claim", index, result, "forbidden_claim")

    for index in range(1, 26):
        source_id = f"source-{index:02d}"
        claim = f"FACT-{index:02d}"
        result = evaluate_text_answer(
            "Trả lời từ nguồn và dẫn chứng.",
            f"Kết luận là {claim} [1].",
            [{"file_id": "wrong-source", "snippet": f"Có {claim}."}],
            require_citations=True,
            expected_claim_citations=[
                {
                    "claim": claim,
                    "citation_index": 1,
                    "file_id": source_id,
                    "evidence_fact": claim,
                }
            ],
        )
        add("wrong_citation_source", index, result, "citation_source_mismatch")

    for index in range(1, 16):
        result = evaluate_text_answer(
            "So sánh hai lựa chọn bằng bảng.",
            f"Lựa chọn A và B cần cân nhắc theo tình huống {index}.",
            require_markdown_table=True,
        )
        add("missing_table", index, result, "missing_required_table")

    for index in range(1, 16):
        result = evaluate_text_answer(
            "Lập kế hoạch có ba bước.",
            f"Chỉ có một đoạn mô tả kế hoạch {index}.",
            min_numbered_steps=3,
        )
        add("missing_steps", index, result, "below_minimum_numbered_step_count")

    for index in range(1, 11):
        result = evaluate_text_answer(
            "Trả lời đủ độ dài.",
            f"Quá ngắn {index}.",
            min_words=40,
        )
        add("too_short", index, result, "below_minimum_word_count")

    for index in range(1, 11):
        result = evaluate_text_answer(
            "So sánh nhưng không khẳng định tuyệt đối khi thiếu nguồn.",
            f"Phương án A luôn tốt nhất và hiệu quả nhất trong trường hợp {index}.",
            forbid_uncited_categorical_claims=True,
        )
        add("uncited_categorical", index, result, "uncited_categorical_claim")

    by_category: dict[str, dict[str, int]] = {}
    for case in cases:
        stats = by_category.setdefault(case["category"], {"passed": 0, "total": 0})
        stats["total"] += 1
        stats["passed"] += int(case["passed"])
    passed_count = sum(item["passed"] for item in cases)
    return {
        "suite": "adversarial-evaluator-mutations",
        "version": "1.0.0",
        "scope": (
            "Known-bad evaluator mutations only; not live model, retrieval, artifact, "
            "usability or end-to-end product accuracy."
        ),
        "passed": passed_count,
        "total": len(cases),
        "pass_rate": round(passed_count / len(cases), 4),
        "coverage": by_category,
        "cases": cases,
    }


def run_routing_regression(path: Path = GOLDEN_ROUTES) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = []
    for case in payload["cases"]:
        route = route_request(case["input"])
        passed = route.tool == case["expected_tool"] and route.direct == case["expected_direct"]
        results.append(
            {
                "id": case["id"],
                "passed": passed,
                "expected_tool": case["expected_tool"],
                "actual_tool": route.tool,
                "expected_direct": case["expected_direct"],
                "actual_direct": route.direct,
            }
        )
    passed_count = sum(item["passed"] for item in results)
    return {
        "suite": "deterministic-routing",
        "version": payload["version"],
        "scope": payload["purpose"],
        "passed": passed_count,
        "total": len(results),
        "pass_rate": round(passed_count / len(results), 4) if results else None,
        "cases": results,
    }
