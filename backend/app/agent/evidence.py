"""Stable per-turn source numbers, independent from a document's chunk index."""

import json
import re
from typing import Any

HISTORICAL_SOURCE_INSTRUCTION = (
    "Nguồn đã đọc trong cuộc trò chuyện này, chưa xác minh lại. "
    "Chỉ dùng khi tiếp nối dữ kiện cũ; không coi là thông tin mới. "
    "Phân biệt dữ kiện có trong đoạn nguồn, đính chính hoặc giả thuyết của người dùng, "
    "và kết quả tính toán. Đính chính mới được ưu tiên nhưng không trở thành dữ kiện "
    "của tài liệu cũ: ghi rõ 'theo đính chính của bạn', không gắn tham chiếu tài liệu "
    "cho giá trị chỉ có trong lời người dùng. Với số tính ra, nêu công thức và nguồn "
    "của đầu vào; không nói tài liệu trực tiếp ghi kết quả nếu đoạn nguồn không có. "
    "Tách riêng các mục 'Dữ kiện từ nguồn đã đọc', 'Giả thuyết bạn thay đổi' và "
    "'Kết quả tính toán'. Chỉ mục dữ kiện nguồn dùng tham chiếu tài liệu. "
    "Mục giả thuyết và câu nhắc giả thuyết chưa được kiểm chứng không được gắn "
    "tham chiếu tài liệu, vì tài liệu không xác nhận thay đổi của người dùng. "
    "Nhắc rõ nguồn cũ chưa được kiểm tra lại trong lượt này. "
    "Số tham chiếu giữ nguyên, không tự tạo số hoặc đổi nguồn."
)


def context_only_followup(request: str) -> bool:
    return bool(re.search(
        r"không\s+đọc\s+thêm\s+nguồn|chỉ\s+dùng\s+ngữ\s+cảnh|"
        r"chỉ\s+(?:dùng|sử\s+dụng)\s+(?:nội\s+dung|thông\s+tin|dữ\s+kiện|nguồn)"
        r"[^.!?;\n]{0,100}(?:đã\s+đọc|đã\s+có)"
        r"[^.!?;\n]{0,60}(?:cuộc\s+trò\s+chuyện|hội\s+thoại|phiên)\s+này",
        request, re.I
    ))


def prior_turn_sources(rows: list[Any], request: str) -> list[dict[str, Any]]:
    """Reuse a bounded source snapshot only for an explicit context-only follow-up.

    The caller must load owner/session-scoped rows newest first. This does not
    fetch a document or establish freshness; it preserves the exact prior mapping.
    """
    if not context_only_followup(request):
        return []
    for row in rows:
        if row.role != "assistant":
            continue
        try:
            sources = json.loads(row.citations_json or "[]")
        except (TypeError, ValueError):
            continue
        if not sources:
            continue
        if not isinstance(sources, list) or len(sources) > 12:
            return []
        required = {"file_id", "file_name", "chunk_index", "snippet", "score"}
        if any(not isinstance(item, dict) or not required <= item.keys()
               or not isinstance(item["snippet"], str) or len(item["snippet"]) > 10000
               for item in sources):
            return []
        return sources
    return []


def source_references(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # chunk_index is a position inside the document, NOT the displayed [n] reference.
    return [{"reference": index, **citation} for index, citation in enumerate(citations, start=1)]


def label_historical_sources(answer: str, citations: list[dict[str, Any]]) -> str:
    """Present reused sources as context, never as newly validated claim support.

    A snapshot preserves provenance but cannot prove that a new user hypothesis
    is supported by an old document. Keep the selected mapping in a separate,
    explicitly limited source line rather than implying sentence-level validation.
    This does not change the answer's facts or perform another provider call.
    """
    if not citations:
        return answer
    single = r"\[\s*\d+(?:\s*[,;]\s*\d+)*\s*\](?!\()"
    marker = re.compile(r"(?<!\!)" + single + r"(?:\s*[,;]\s*" + single + r")*")
    cleaned = marker.sub("", answer)
    cleaned = re.sub(r"[ \t]+([,.;:!?])", r"\1", cleaned)
    cleaned = cleaned.strip()
    refs = ", ".join(f"[{index}]" for index in range(1, len(citations) + 1))
    return (
        f"{cleaned}\n\nNguồn ngữ cảnh đã đọc ở lượt trước: {refs}. "
        "Chưa đọc hoặc kiểm tra lại trong lượt này. Các nguồn này không xác nhận "
        "giả thuyết mới của bạn hoặc kết quả tính toán mới."
    )


def _align_explicit_page_markers(
    answer: str, citations: list[dict[str, Any]]
) -> str:
    """Correct an unambiguous inline PDF page/reference mismatch.

    Gemini occasionally writes ``(Trang 3) ... [1]`` even though reference 1 is
    another page from the same PDF.  Rewriting arbitrary citations would invent
    semantic support, so this guard acts only when the line names exactly one page,
    contains exactly one single-source marker, and the evidence list contains exactly
    one citation for that page.  Ambiguous multi-file/page cases are left untouched.
    """

    page_targets: dict[int, list[int]] = {}
    for index, citation in enumerate(citations, start=1):
        page = citation.get("page_number")
        if isinstance(page, int) and not isinstance(page, bool) and page > 0:
            page_targets.setdefault(page, []).append(index)

    page_pattern = re.compile(r"(?i)\b(?:trang|page)\s*(\d+)\b")
    marker_pattern = re.compile(r"(?<!\!)\[\s*(\d+)\s*\](?!\()")
    corrected: list[str] = []
    for line in answer.splitlines(keepends=True):
        pages = list(dict.fromkeys(int(value) for value in page_pattern.findall(line)))
        markers = list(marker_pattern.finditer(line))
        if len(pages) != 1 or len(markers) != 1:
            corrected.append(line)
            continue
        targets = page_targets.get(pages[0], [])
        if len(targets) != 1:
            corrected.append(line)
            continue
        marker = markers[0]
        old_index = int(marker.group(1))
        if old_index < 1 or old_index > len(citations):
            corrected.append(line)
            continue
        old_page = citations[old_index - 1].get("page_number")
        if old_page == pages[0]:
            corrected.append(line)
            continue
        corrected.append(line[: marker.start()] + f"[{targets[0]}]" + line[marker.end() :])
    return "".join(corrected)


def retain_referenced_citations(
    answer: str, citations: list[dict[str, Any]], *, auto_reference: bool = False
) -> tuple[str, list[dict[str, Any]]]:
    """Return only evidence explicitly cited by a generated answer.

    Retrieval candidates are not automatically supporting sources. The model receives
    stable ``[n]`` references, then this boundary removes unused candidates and renumbers
    the remaining markers so the rendered source list cannot imply unsupported evidence.
    Direct tool responses may still return their source without using this filter.
    """

    # Models frequently put the page label inside the reference. Normalize
    # only when the stated page matches that exact source; never invent support.
    invalid_page_reference = False

    def normalize_page_reference(match: re.Match[str]) -> str:
        nonlocal invalid_page_reference
        number, page = int(match.group(1)), int(match.group(2))
        if 1 <= number <= len(citations) and citations[number - 1].get("page_number") == page:
            return f"[{number}] (trang {page})"
        invalid_page_reference = True
        return ""

    answer = re.sub(r"\[(\d+)\s*,\s*(?:trang|page)\s+(\d+)\]",
                    normalize_page_reference, answer, flags=re.I)
    answer = _align_explicit_page_markers(answer, citations)
    valid_order: list[int] = []
    citation_pattern = re.compile(r"(?<!\!)\[(\s*\d+(?:\s*[,;]\s*\d+)*\s*)\](?!\()")
    for match in citation_pattern.finditer(answer):
        for num_str in re.findall(r"\d+", match.group(1)):
            number = int(num_str)
            if 1 <= number <= len(citations) and number not in valid_order:
                valid_order.append(number)
    if not valid_order:
        if auto_reference and citations and not invalid_page_reference:
            # A model can answer correctly from a tool result yet omit the
            # server-provided marker. Do not silently discard verified evidence:
            # append a neutral source line instead of pretending every sentence
            # has been semantically proven. The UI still renders clickable
            # citation cards, and human review can inspect the exact snippet.
            marker = "[" + ", ".join(str(index) for index in range(1, len(citations) + 1)) + "]"
            suffix = f"\n\nNguồn đã kiểm tra: {marker}"
            return answer.rstrip() + suffix, citations
        # A model can reuse numeric markers remembered from an earlier ADK turn even
        # when the current turn did not gather any evidence. Never render those as
        # if the server had verified them.
        return citation_pattern.sub("", answer), []

    mapping = {old: new for new, old in enumerate(valid_order, start=1)}

    def replace(match: re.Match[str]) -> str:
        content = match.group(1)
        numbers = [int(n) for n in re.findall(r"\d+", content)]
        valid_in_group: list[int] = []
        for n in numbers:
            if n in mapping:
                mapped = mapping[n]
                if mapped not in valid_in_group:
                    valid_in_group.append(mapped)
        if not valid_in_group:
            # Drop out-of-range references instead of leaving a clickable-looking
            # marker with no corresponding source in the response payload.
            return ""
        return f"[{', '.join(str(n) for n in valid_in_group)}]"

    renumbered = citation_pattern.sub(replace, answer)
    # Models sometimes append the same inline reference twice ("[1]. [1]")
    # after already placing it next to the claim. Collapse only adjacent,
    # identical single-source markers; repeated references in later sentences
    # remain untouched and grouped multi-source citations are never rewritten.
    adjacent_duplicate = re.compile(r"\[(\d+)\]([.,;:]*)\s+\[\1\]")
    while adjacent_duplicate.search(renumbered):
        renumbered = adjacent_duplicate.sub(r"[\1]\2", renumbered)
    return renumbered, [citations[number - 1] for number in valid_order]
