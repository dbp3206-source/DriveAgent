"""Stable per-turn source numbers, independent from a document's chunk index."""

import re
from typing import Any


def source_references(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # chunk_index is a position inside the document, NOT the displayed [n] reference.
    return [{"reference": index, **citation} for index, citation in enumerate(citations, start=1)]


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

    answer = _align_explicit_page_markers(answer, citations)
    valid_order: list[int] = []
    citation_pattern = re.compile(r"(?<!\!)\[(\s*\d+(?:\s*[,;]\s*\d+)*\s*)\](?!\()")
    for match in citation_pattern.finditer(answer):
        for num_str in re.findall(r"\d+", match.group(1)):
            number = int(num_str)
            if 1 <= number <= len(citations) and number not in valid_order:
                valid_order.append(number)
    if not valid_order:
        if auto_reference and citations:
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
