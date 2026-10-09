"""Stable per-turn source numbers, independent from a document's chunk index."""

import json
import re
from datetime import date
from typing import Any

HISTORICAL_SOURCE_INSTRUCTION = (
    "Nguồn đã đọc trong cuộc trò chuyện này, chưa xác minh lại. "
    "Chỉ dùng khi tiếp nối dữ kiện cũ; không coi là thông tin mới. "
    "Phân biệt dữ kiện có trong đoạn nguồn, đính chính hoặc giả thuyết của người dùng, "
    "và kết quả tính toán. Đính chính mới được ưu tiên nhưng không trở thành dữ kiện "
    "của tài liệu cũ: ghi rõ 'theo đính chính của bạn', không gắn tham chiếu tài liệu "
    "cho giá trị chỉ có trong lời người dùng. Chỉ gọi một giá trị là đính chính hoặc "
    "'Giả thuyết bạn thay đổi' khi người dùng nêu rõ dữ kiện cũ sai, yêu cầu sửa/thay "
    "bằng giá trị mới, hoặc đưa một giá trị mới như dữ kiện cần ghi nhận. Không được "
    "ép mục giả thuyết vào mọi lượt tiếp nối nguồn. Các yêu cầu kiểm tra lại, đối chiếu, "
    "lọc dữ kiện, chọn cách trình bày, chỉ lấy phần tiêu đề chính, hoặc không ghép tên "
    "các mục nội dung là thao tác kiểm tra/trình bày; gọi kết quả là 'Kết quả kiểm tra' "
    "hoặc 'Cách trình bày theo yêu cầu', không gán cho người dùng một đính chính hay "
    "giả thuyết. Khi xác định tên tài liệu, giữ nguyên khối tên báo cáo như nguồn đã "
    "đọc, kể cả phụ đề hợp lệ nằm ở dòng kế tiếp; phân biệt tên riêng với nhãn loại "
    "hoặc chuyên mục. Nếu yêu cầu chỉ lấy phần tiêu đề chính thì áp dụng đúng phạm vi "
    "đó, nhưng không ghép tiêu đề với tên mục nội dung, không suy đoán, không tự đặt "
    "tên PDF. Nếu đoạn nguồn không đủ để phân biệt các phần này, nói rõ chưa đủ bằng "
    "chứng và không chọn tên thay người dùng. Với số tính ra, nêu công thức và nguồn "
    "của đầu vào; không nói tài liệu "
    "trực tiếp ghi kết quả nếu đoạn nguồn không có. "
    "Tách riêng các mục 'Dữ kiện từ nguồn đã đọc' và 'Kết quả tính toán' khi chúng "
    "thực sự có trong câu trả lời; chỉ thêm mục 'Giả thuyết bạn thay đổi' khi điều kiện "
    "đính chính ở trên được đáp ứng. Chỉ mục dữ kiện nguồn dùng tham chiếu tài liệu. "
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


def compact_web_evidence(payload: Any, citations: list[dict[str, Any]]) -> Any:
    """Avoid repeating an identical web excerpt beside its canonical reference.

    Keep every source, date and nonidentical excerpt; no retrieval or source
    boundary changes. Non-web portions of mixed-tool payloads stay untouched.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        return payload
    refs = {item.get("file_id"): (index, item.get("snippet"))
            for index, item in enumerate(citations, 1) if item.get("evidence_kind")}
    sources = []
    for source in payload["sources"]:
        if isinstance(source, dict) and source.get("tool") == "web_research":
            sources.append({
                **source, "data": compact_web_evidence(source.get("data"), citations),
            })
            continue
        ref = refs.get(source.get("url")) if isinstance(source, dict) else None
        if ref and ref[1] and source.get("evidence_excerpt") == ref[1]:
            sources.append({
                **{key: value for key, value in source.items() if key != "evidence_excerpt"},
                "evidence_reference": ref[0],
            })
        else:
            sources.append(source)
    return {**payload, "sources": sources}


def bound_web_numeric_claims(
    answer: str, citations: list[dict[str, Any]], *, request: str = "",
) -> tuple[str, int]:
    """Reject missing literal numbers in cited web-page claims, without a model call.

    This is a necessary evidence check, not semantic validation of units, entities
    or dates. It never borrows a number from an uncited source or a headline.
    Local-source calculations and bibliography titles are outside this boundary.
    A whole-sentence search limitation may retain only a period explicitly asked
    for by the user; remove its false web attribution instead. Never exempt a
    paragraph merely because it contains a negation or a requested number.
    """
    marker = re.compile(r"\[(\s*S?\d+(?:\s*[,;]\s*S?\d+)*\s*)\]", re.I)
    window = r"(?P<days>\d{1,3})\s+ngày\s+(?:gần\s+đây|vừa\s+qua|qua)"
    requested_days = {match["days"] for match in re.finditer(
        rf"(?<!\w){window}\b", request, re.I,
    )}
    news_limit = re.compile(
        r"\s*(?:[-*]\s+)?Chưa\s+xác\s+minh\s+được\s+"
        r"(?:tin(?:\s+(?:mới|tức))?|thông\s+tin\s+cập\s+nhật)\s+trong\s+"
        + window
        + r"(?:\s+(?:từ|trong)\s+(?:các\s+)?nguồn\s+đã\s+(?:đọc|dẫn))?\s*[.!]?\s*",
        re.I,
    )

    def numbers(text: str) -> set[str]:
        text = re.sub(r"https?://\S+", "", text)
        # A translated date or English ordinal is the same evidenced value,
        # not a new numerical fact. Expand only complete, valid dated spans;
        # a bare month name must not grant an arbitrary numeric claim.
        months = {name.casefold(): index for index, name in enumerate((
            "January", "February", "March", "April", "May", "June", "July",
            "August", "September", "October", "November", "December",
        ), 1)}
        month_pattern = "(?:" + "|".join(months) + ")"
        dates = []
        patterns = (
            rf"\b(?P<m>{month_pattern})\s+(?P<d>\d{{1,2}})\s*,?\s+(?P<y>\d{{4}})\b",
            rf"\b(?P<d>\d{{1,2}})\s+(?P<m>{month_pattern})\s+(?P<y>\d{{4}})\b",
            rf"\b(?P<m>{month_pattern})\s+(?P<d>\d{{1,2}})\s+(?:to|through|until)\s+"
            rf"(?P<end_m>{month_pattern})\s+(?P<end_d>\d{{1,2}})\s*,?\s+(?P<y>\d{{4}})\b",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.I):
                try:
                    value = date(int(match['y']), months[match['m'].casefold()], int(match['d']))
                    dated_span = [f"{value.day}/{value.month}/{value.year}"]
                    if match.groupdict().get('end_m'):
                        value = date(int(match['y']), months[match['end_m'].casefold()],
                                     int(match['end_d']))
                        dated_span.append(f"{value.day}/{value.month}/{value.year}")
                    dates.extend(dated_span)
                except ValueError:
                    continue

        def numeric_date(match: re.Match) -> str:
            try:
                value = date(int(match[3]), int(match[2]), int(match[1]))
                return f"{value.day}/{value.month}/{value.year}"
            except ValueError:
                return match.group()

        text = re.sub(r"(?<!\w)(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?!\w)", numeric_date, text)
        text = re.sub(r"(?<!\w)(\d+)(?:st|nd|rd|th)(?!\w)", r"\1", text, flags=re.I)
        text += " " + " ".join(dates)
        values = set()
        for value in re.findall(r"(?<!\w)\d+(?:[.,]\d+)*(?!\w)", text):
            if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", value):
                value = re.sub(r"[.,]", "", value)
            else:
                value = value.replace(",", ".")
            values.add(value)
        return values

    result: list[str] = []
    affected = 0
    bibliography = False
    for line in answer.splitlines():
        if line.lstrip().startswith("#"):
            bibliography = bool(re.match(r"^#+\s*(?:nguồn|tài liệu tham khảo)\s*$", line, re.I))
            result.append(line)
            continue
        indices = list(dict.fromkeys(
            int(number) for match in marker.finditer(line)
            for number in re.findall(r"\d+", match[1])
        ))
        selected = [citations[index - 1] for index in indices if 1 <= index <= len(citations)]
        if (bibliography or not selected or len(selected) != len(indices)
                or any(source.get("evidence_kind") != "page_text"
                       or not source.get("snippet") for source in selected)):
            result.append(line)
            continue
        plain = marker.sub("", line)
        limitation = news_limit.fullmatch(plain)
        if limitation and limitation["days"] in requested_days:
            result.append(re.sub(r"\s+([.!])", r"\1", plain).rstrip())
            affected += 1
            continue
        claims = numbers(plain)
        supported = set().union(*(numbers(str(source["snippet"])) for source in selected))
        if claims <= supported:
            result.append(line)
            continue
        affected += 1
        refs = ", ".join(str(index) for index in indices)
        result.append(
            "Chưa đủ bằng chứng trong nguồn đã dẫn để xác nhận số liệu "
            f"của nhận định này [{refs}]."
        )
    return "\n".join(result), affected


def bound_headline_claims(answer: str, citations: list[dict[str, Any]]) -> tuple[str, int]:
    """Render headline evidence as metadata, never inferred events or page facts.

    A title alone cannot establish a launch, price change, appointment or event
    date. Apply after synthesis/rewrites so prose cannot upgrade evidence type.
    Shared-citation claims are conservatively replaced too: a page citation
    beside a headline is not proof that the page supports the news claim.
    Separately cited sentences keep their own evidence boundary.
    """
    marker = re.compile(r"\[(\s*S?\d+(?:\s*[,;]\s*S?\d+)*\s*)\]", re.I)
    corrected = []
    affected = 0
    emitted_headlines: set[int] = set()
    segments: list[str] = []
    for original_line in answer.splitlines():
        line_indices = [int(number) for match in marker.finditer(original_line)
                        for number in re.findall(r"\d+", match[1])]
        if any(1 <= index <= len(citations)
               and citations[index - 1].get("evidence_kind") == "headline"
               for index in line_indices):
            # Split only at an explicit citation followed by sentence punctuation.
            # Never split decimals, URLs, uncited clauses or a shared [1, 2] claim.
            segments.extend(re.split(r"(?<=\][.!?])\s+(?=[^\W\d_])", original_line))
        else:
            segments.append(original_line)
    for line in segments:
        indices = list(dict.fromkeys(
            int(number) for match in marker.finditer(line)
            for number in re.findall(r"\d+", match[1])
        ))
        headlines = [index for index in indices if 1 <= index <= len(citations)
                     and citations[index - 1].get("evidence_kind") == "headline"]
        if not headlines:
            corrected.append(line)
            continue
        affected += 1
        for index in headlines:
            if index in emitted_headlines:
                continue
            emitted_headlines.add(index)
            source = citations[index - 1]
            title = re.sub(r"[\r\n]+", " ", str(source.get("file_name") or "Chưa có tiêu đề"))
            # Neutralize Markdown metacharacters; title remains quoted source data.
            title = re.sub(r"([\\`*_{}\[\]<>])", r"\\\1", title)
            published = str(source.get("published_at") or "")
            date = published[:10] if re.match(r"^\d{4}-\d{2}-\d{2}(?:T|$)", published) else (
                "chưa xác minh"
            )
            corrected.append(
                f'- Tiêu đề nguồn: “{title}”; ngày đăng: {date} [{index}]. '
                "Chỉ đọc tiêu đề, chưa đọc toàn văn; "
                "ngày sự kiện và nội dung chi tiết chưa xác minh."
            )
    return "\n".join(corrected), affected


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
        "Nguồn cũ chưa được đọc hoặc kiểm tra lại trong lượt này; các giá trị bạn "
        "bổ sung và kết quả tính toán không tự trở thành dữ kiện của tài liệu."
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
    # Web summaries use [S1] while other tools use [1]. Both identify the
    # same server evidence slot: renumber them together, including source
    # definitions, so a mixed-format answer cannot leave its bibliography
    # pointing at the pre-renumbering source order.
    citation_pattern = re.compile(
        r"(?<!\!)\[(\s*S?\d+(?:\s*[,;]\s*S?\d+)*\s*)\](?!\()", re.I
    )
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
