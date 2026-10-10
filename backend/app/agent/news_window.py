"""Apply explicit recent-news calendar bounds without another model request.

Only independently cited, single-date items in a news section are relocated.
Explicit publication-date lists may share a trailing citation; that citation is
retained on each separated item. Requested-window framing is corrected separately.
Dates in comparisons, appointments, source titles and other sections stay intact.
This does not establish whether a date is a publication date or an event date.
"""

import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

_MARKER = re.compile(r"\[(?:S?\d+)(?:\s*[,;]\s*S?\d+)*\]", re.I)
_DATE = re.compile(r"(?<!\w)(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?!\w)")
_NEWS = re.compile(
    r"(?:tin(?:\s+tức)?\s+(?:gần đây|mới(?: đã xác minh)?|trong \d+ ngày(?: gần đây)?)"
    r"|thông tin cập nhật)(?:\s*\([^\n]*\))?", re.I,
)
_OTHER = re.compile(
    r"(?:tổng quan|quy mô|nhu cầu|cuộc hẹn|ghi chú|câu hỏi|nguồn|bối cảnh|"
    r"ngành|sản phẩm|trạng thái|liên hệ|bước tiếp theo)\b", re.I,
)
_DATE_TEXT = r"\d{1,2}[/.-]\d{1,2}[/.-]\d{4}"
_PUBLICATION = (
    rf"(?:ngày\s+đăng|đăng\s+ngày|ngày\s+công\s+bố|công\s+bố\s+ngày)"
    rf"\s*:?\s*{_DATE_TEXT}"
)
_TRAILING_REFS = re.compile(rf"(?P<refs>(?:{_MARKER.pattern}\s*)+)[.!]?\s*$", re.I)


def _correct_window_frame(line: str, start: date, end: date, *, heading: bool) -> str:
    """Correct the report's declared interval, never a dated event or comparison."""
    if heading:
        pattern = (
            rf"\(\s*(?:từ\s+)?(?:ngày\s+)?(?P<first>{_DATE_TEXT})\s+"
            rf"(?:đến|tới)\s+(?:ngày\s+)?(?P<last>{_DATE_TEXT})\s*\)"
        )
    else:
        pattern = (
            rf"^\s*(?:[-*]\s*)?(?:Trong|Xét|Với)\s+khoảng(?:\s+thời gian)?\s+"
            rf"từ\s+(?:ngày\s+)?(?P<first>{_DATE_TEXT})\s+(?:đến|tới)\s+"
            rf"(?:ngày\s+)?(?P<last>{_DATE_TEXT})(?=\s*[,;:])"
        )
    match = re.search(pattern, line, re.I)
    if not match:
        return line
    # An ordinary event range can also begin a paragraph. Require news/report
    # framing after the interval before replacing either boundary.
    if not heading and not re.search(
        r"^\s*[,;:]\s*(?:(?:các\s+)?(?:tin(?:\s+tức)?|thông tin|bài viết|thông báo)\b"
        r"|(?:chưa|không)\s+(?:có|tìm|ghi nhận|xác minh|đối chiếu)\b"
        r"|(?:trang(?:\s+web)?|nguồn|cổng\s+thông\s+tin)(?:\s+chính\s+thức)?\s+"
        r"(?:đã\s+)?(?:ghi\s+nhận|liệt\s+kê|tổng\s+hợp)\s+(?:các\s+)?"
        r"(?:tin(?:\s+tức)?|thông tin|bài viết|thông báo)\b)",
        line[match.end():], re.I,
    ):
        return line
    try:
        for raw in (match["first"], match["last"]):
            day, month, year = re.split(r"[/.-]", raw)
            date(int(year), int(month), int(day))
    except ValueError:
        return line
    return (
        line[:match.start("first")] + f"{start:%d/%m/%Y}"
        + line[match.end("first"):match.start("last")] + f"{end:%d/%m/%Y}"
        + line[match.end("last"):]
    )


def _shared_publication_items(
    line: str, citations: list[dict[str, Any]],
) -> tuple[str, list[str]] | None:
    """Separate an explicit publication list, retaining its shared attribution.

    Separators alone are not enough: every item must declare a publication date.
    This excludes event ranges, prose comparisons and unrelated dated clauses.
    """
    trailing = _TRAILING_REFS.search(line)
    if not trailing:
        return None
    refs_text = trailing["refs"].strip()
    refs = [int(n) for n in re.findall(r"\d+", refs_text)]
    if not refs or any(
        not 1 <= n <= len(citations) or citations[n - 1].get("evidence_kind") != "page_text"
        for n in refs
    ):
        return None
    body = line[:trailing.start()].rstrip()
    if _MARKER.search(body):
        return None
    first = re.search(_PUBLICATION, body, re.I)
    if not first:
        return None
    prefix = body[:first.start()]
    # A preceding introduction must end in a list colon, not a factual clause.
    if prefix.strip() and not re.search(r":\s*$", prefix) and prefix.strip() not in {"-", "*"}:
        return None
    parts = re.split(
        rf"[;,]\s*(?:và\s+)?(?={_PUBLICATION})", body[first.start():], flags=re.I,
    )
    if len(parts) < 2 or any(not re.match(_PUBLICATION, part, re.I) for part in parts):
        return None
    return prefix, [f"{part.strip().rstrip(' ,;.')} {refs_text}" for part in parts]


def news_window_context(
    request: str, timezone: str = "Asia/Bangkok", *, today: date | None = None,
) -> dict[str, Any] | None:
    matches = list(re.finditer(
        r"\b(?:tin(?: tức)?|thông tin cập nhật)\s+(?:trong\s+)?"
        r"(?P<days>\d{1,3})\s+ngày\s+(?:gần đây|vừa qua|qua)\b", request, re.I,
    ))
    if len(matches) != 1:
        return None
    match = matches[0]
    if re.search(r"(?:không|đừng)\s+(?:tìm|đọc|lấy|cần)\s*$", request[:match.start()], re.I):
        return None
    days = int(match["days"])
    if not 1 <= days <= 366:
        return None
    end = today or datetime.now(ZoneInfo(timezone)).date()
    start = end - timedelta(days=days - 1)
    return {
        "days": days, "start_date": start.isoformat(), "end_date": end.isoformat(),
        "timezone": timezone,
        "instruction": (
            f"Mục tin gần đây chỉ xét từ {start:%d/%m/%Y} đến {end:%d/%m/%Y}, "
            "gồm hai ngày đầu/cuối. Tách mốc ngoài khoảng sang bối cảnh có ngày rõ ràng. "
            "Phân biệt ngày đăng với ngày sự kiện; không coi ngày tải trang là ngày tin."
        ),
    }


def bound_recent_news(
    answer: str, citations: list[dict[str, Any]], *, request: str,
    timezone: str = "Asia/Bangkok", today: date | None = None,
) -> tuple[str, int]:
    window = news_window_context(request, timezone, today=today)
    if not window or not any(c.get("evidence_kind") == "page_text" for c in citations):
        return answer, 0
    start, end = date.fromisoformat(window["start_date"]), date.fromisoformat(window["end_date"])
    result: list[str] = []
    outside: list[str] = []
    in_news = False
    news_has_content = False
    affected = 0
    frame_changed = False

    def flush() -> None:
        if outside:
            if not news_has_content:
                result.append(
                    "Bản tổng hợp này chưa có mục đã đối chiếu trong khoảng ngày yêu cầu."
                )
            result.extend([
                "", f"### Mốc ngoài khoảng {start:%d/%m/%Y}–{end:%d/%m/%Y}", "",
                "Các mục dưới đây có mốc ngày ngoài khoảng yêu cầu; chỉ dùng làm bối cảnh.",
                *outside, "",
            ])
            outside.clear()

    for line in answer.splitlines():
        heading = re.sub(r"^\s*(?:#{1,6}\s*|\d+[.)]\s*)", "", line).strip(" *:")
        is_news = bool(_NEWS.fullmatch(heading))
        is_heading = is_news or line.lstrip().startswith("#") or (
            len(heading) <= 100 and not _MARKER.search(line) and bool(_OTHER.match(heading))
            and not re.search(r"[.!?]$", heading)
        )
        if is_heading:
            flush()
            in_news = is_news
            news_has_content = False
        if in_news:
            corrected = _correct_window_frame(line, start, end, heading=is_news)
            frame_changed = frame_changed or corrected != line
            line = corrected
        if not in_news or is_heading or not _MARKER.search(line):
            result.append(line)
            continue
        # A separator after a citation marks an independently attributed item.
        # Never split a date range or an uncited comparison into unrelated facts.
        shared = _shared_publication_items(line, citations)
        prefix = shared[0] if shared else ""
        parts = shared[1] if shared else re.split(
            r"(?<=\])\s*[,;]\s*(?:và\s+)?|(?<=\])\.\s+(?=\S)", line,
        )
        kept: list[str] = []
        moved: list[str] = []
        for part in parts:
            refs = [int(n) for marker in _MARKER.findall(part) for n in re.findall(r"\d+", marker)]
            selected = [citations[n - 1] for n in refs if 1 <= n <= len(citations)]
            raw_dates = _DATE.findall(re.sub(r"https?://\S+", "", part))
            try:
                dates = {date(int(y), int(m), int(d)) for d, m, y in raw_dates}
            except ValueError:
                dates = set()
            if (len(dates) == 1 and refs and len(selected) == len(refs)
                    and all(c.get("evidence_kind") == "page_text" for c in selected)
                    and not start <= next(iter(dates)) <= end):
                # Remove a list introduction's recency claim when relocating it.
                text = re.sub(
                    r"^\s*(?:[-*]\s*)?(?:Các\s+.{0,100}?\s+bao gồm\s+|(?:và|cùng)\s+)",
                    "", part, flags=re.I,
                ).strip().rstrip(" ,;.")
                moved.append(f"- {text}.")
            else:
                kept.append(part)
        if not moved:
            result.append(line)
            news_has_content = news_has_content or bool(line.strip())
            continue
        affected += len(moved)
        outside.extend(moved)
        if kept:
            result.append(prefix + "; ".join(kept).rstrip(" ,;.") + ".")
            news_has_content = True
    flush()
    if not affected and not frame_changed:
        return answer, 0
    return "\n".join(result).rstrip(), affected
