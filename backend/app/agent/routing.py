"""Small, conservative routes. Ambiguous text is not interpreted as a write command."""

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.agent.freshness import needs_public_evidence


@dataclass(frozen=True)
class Route:
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    direct: bool = False
    read_match: bool = False
    sources: tuple["Route", ...] = ()
    clarification: str | None = None
    required_sources: tuple[str, ...] = ()


_EXPLICIT_FILE_ID = re.compile(
    r"(?:\bID\b|file[_ ]?id)\s*[:=]?\s*([A-Za-z0-9_-]{10,200})",
    re.I,
)


def extract_explicit_file_id(message: str) -> str | None:
    """Return a user-supplied Drive id, when the request names one explicitly.

    A source id is an execution constraint, not ordinary prose.  Keeping the
    parser in the routing module lets both automatic routing and slash-selected
    RAG use the same source-locking contract without duplicating regexes.
    """

    match = _EXPLICIT_FILE_ID.search(message)
    return match[1] if match else None


def _rag_arguments(message: str) -> dict[str, Any]:
    """Build bounded RAG arguments and lock retrieval to an explicit source.

    Six chunks is enough for a short note but too narrow for a long PDF with
    tables and page-aware evidence.  An explicit verified file id removes the
    cross-file ambiguity, so we can safely return a larger evidence window.
    """

    file_id = extract_explicit_file_id(message)
    arguments: dict[str, Any] = {
        "query": message[:2000],
        "limit": 12 if file_id else 8,
    }
    if file_id:
        arguments["file_ids"] = [file_id]
    return arguments


def _gmail_positive_scope(message: str) -> str:
    """Do not turn an explicitly removed filter into a positive Gmail filter."""
    return re.sub(
        r"\b(?:không|bỏ|gỡ)\s+(?:giới hạn|lọc theo|lọc|chỉ lấy)\b[^.;!?\n]*",
        " ",
        message,
        flags=re.I,
    )


def _gmail_query_from_request(message: str, *, timezone: str = "Asia/Bangkok") -> str:
    """Translate explicit sender, subject, status and date filters to Gmail search."""

    message = _gmail_positive_scope(message)
    terms: list[str] = []
    sender = re.search(
        r"\b(?:người gửi(?: là)?|của|từ|from)\s+(.+?)"
        r"(?=[,;]|\s+(?:về|có\s+tiêu\s+đề|tiêu\s+đề|chủ\s+đề|subject|ngày|trong|hôm)\b|$)",
        message,
        re.I,
    )
    if sender:
        value = sender[1].strip(" \t\r\n\"'“”")
        if value and not re.match(r"^(?:tôi|mình|me)\b", value, re.I):
            value = re.sub(r"[^\w.@+-]+", " ", value, flags=re.UNICODE).strip()
            if value:
                terms.append(f'from:"{value}"')

    subject = re.search(
        r"\b(?:về|chủ\s+đề|có\s+tiêu\s+đề|tiêu\s+đề|subject)\s+"
        r"(?:là\s+)?[\"'“]?(.+?)[\"'”]?"
        r"(?=\s+(?:của|từ|người\s+gửi|ngày|trong|hôm)\b|$)",
        message,
        re.I,
    )
    if subject is None:
        subject = re.search(
            r"\b(?:email|mail|thư)\s+[\"'“]([^\"'”]{2,120})[\"'”]",
            message,
            re.I,
        )
    if subject:
        value = subject[1].strip(" \t\r\n\"'“”.,;:")
        value = re.sub(r"^(?:chủ\s+đề|subject)\s+", "", value, flags=re.I)
        value = re.sub(r'[\r\n"\\]+', " ", value)[:120].strip()
        if value:
            terms.append(f'subject:"{value}"')

    explicit_date = re.search(
        r"\b(?:ngày\s+)?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?\b",
        message,
        re.I,
    )
    if explicit_date:
        day, month = int(explicit_date[1]), int(explicit_date[2])
        year = int(explicit_date[3]) if explicit_date[3] else date.today().year
        try:
            selected = date(year, month, day)
        except ValueError:
            selected = None
        if selected and not explicit_date[3] and selected > date.today():
            selected = selected.replace(year=selected.year - 1)
        if selected:
            zone = ZoneInfo(timezone)
            start = datetime.combine(selected, time.min, zone)
            end = datetime.combine(selected + timedelta(days=1), time.min, zone)
            # Gmail interprets YYYY/MM/DD as midnight PST. Epoch boundaries
            # preserve the application's configured local day instead.
            terms.extend((f"after:{int(start.timestamp())}", f"before:{int(end.timestamp())}"))

    recent = re.search(r"\b(?:trong|qua)\s+(\d{1,2})\s+(ngày|tuần|tháng)\b", message, re.I)
    if recent:
        count = int(recent[1])
        unit = {"ngày": "d", "tuần": "d", "tháng": "d"}[recent[2].casefold()]
        multiplier = {"ngày": 1, "tuần": 7, "tháng": 30}[recent[2].casefold()]
        if 1 <= count <= 365:
            terms.append(f"newer_than:{count * multiplier}{unit}")

    if re.search(r"\b(?:chưa\s+đọc|chưa xem|unread)\b", message, re.I):
        terms.append("is:unread")
    elif re.search(r"\b(?:đã\s+đọc|đã xem|read)\b", message, re.I):
        terms.append("is:read")
    return " ".join(terms)


def _gmail_requested_count(message: str) -> int | None:
    match = re.search(r"\b(\d{1,2})\s+(?:email|mail|thư)\b", message, re.I)
    return min(max(int(match[1]), 1), 20) if match else None


def _gmail_full_read_route(
    message: str, *, query: str = "", timezone: str = "Asia/Bangkok"
) -> Route:
    """Read message bodies, not list snippets, for synthesis requests."""

    message = _gmail_positive_scope(message)
    requested = _gmail_requested_count(message)
    today = bool(re.search(r"\b(?:hôm nay|ngày hôm nay|today)\b", message, re.I))
    sender_name: str | None = None
    sender_filter = re.search(r'(?<!\S)from:"([^\"]+)"', query)
    if sender_filter:
        candidate = sender_filter[1]
        # Gmail's quoted from: search is order-sensitive for display names.
        # The connected sender may be "Bảo Phúc Đinh" while the user says
        # "Đinh Bảo Phúc". Search the remaining scope, then verify the full
        # display name against each retrieved header in either order.
        if "@" not in candidate and (
            len(candidate.split()) >= 3 or re.search(r"\bngười\s+gửi(?:\s+là)?\b", message, re.I)
        ):
            sender_name = candidate
            query = (query[: sender_filter.start()] + query[sender_filter.end() :]).strip()
    arguments: dict[str, Any] = {
        "query": query or ("after:0" if sender_name else "in:inbox"),
        "max_results": requested or (20 if today else 10),
    }
    if sender_name:
        arguments["sender_name"] = sender_name
    if today:
        arguments["day_scope"] = "today"
    if timezone != "Asia/Bangkok":
        arguments["timezone"] = timezone
    return Route("gmail_read_matching_messages", arguments)


def route_request(message: str, *, timezone: str = "Asia/Bangkok") -> Route:
    text = message.strip().rstrip(".?!")
    if needs_public_evidence(text):
        return Route("web_research", {"question": text[:800], "timezone": timezone}, direct=True)
    is_gmail_request = bool(re.search(r"\b(?:gmail|email|mail|hộp thư|thư chưa đọc)\b", text, re.I))
    is_drive_request = bool(re.search(r"\b(?:drive|docs?|tài liệu|tệp|file)\b", text, re.I))
    asks_to_compare_sources = bool(
        re.search(r"\b(?:đối chiếu|so sánh|kiểm tra khác biệt|tổng hợp cả|kết hợp)\b", text, re.I)
    )
    if is_gmail_request and is_drive_request and asks_to_compare_sources:
        gmail_source = Route(
            "gmail_list_messages",
            {"query": "in:inbox", "max_results": 1},
            read_match=True,
        )
        drive_file = re.search(
            r"\b(?:file|tệp|tài liệu|docs?)\s+[\"'“]?(.+?)[\"'”]?"
            r"(?=\s+(?:trong|ở|tại)\s+(?:google\s+)?drive\b|$)",
            text,
            re.I,
        )
        drive_clause = next(
            (
                clause
                for clause in re.split(r"\b(?:với|và|and)\b", text, flags=re.I)
                if re.search(r"\bdrive\b", clause, re.I)
            ),
            "",
        )
        explicit_drive_latest = bool(
            re.search(r"\b(?:gần nhất|mới nhất|mới sửa nhất)\b", drive_clause, re.I)
        )
        drive_query = drive_file[1].strip(" \t\r\n\"'“”.,;:") if drive_file else ""
        if re.match(r"^(?:trong|ở|tại)\s+(?:google\s+)?drive\b", drive_query, re.I):
            drive_query = ""
        if explicit_drive_latest and re.match(
            r"^(?:gần nhất|mới nhất|mới sửa nhất)\b", drive_query, re.I
        ):
            drive_source = Route(
                "drive_list_files", {"page_size": 1, "exclude_folders": True}, read_match=True
            )
        elif drive_file and drive_query:
            drive_source = Route(
                "drive_search_files",
                {"query": drive_query, "page_size": 10},
                read_match=True,
            )
        elif explicit_drive_latest:
            drive_source = Route(
                "drive_list_files", {"page_size": 1, "exclude_folders": True}, read_match=True
            )
        else:
            return Route(
                direct=True,
                clarification=(
                    "Để đối chiếu đủ cả hai nguồn, hãy cho biết tệp Drive cụ thể cần dùng "
                    "hoặc nói rõ muốn lấy tệp mới nhất. Tôi chưa kết luận chỉ dựa trên email."
                ),
                required_sources=("gmail", "drive"),
            )
        return Route(sources=(gmail_source, drive_source))
    if is_gmail_request and re.search(r"\b(?:tìm|tìm kiếm|search|lọc|lục)\b", text, re.I):
        query = _gmail_query_from_request(text, timezone=timezone)
        if query:
            asks_for_content = bool(
                re.search(
                    r"\b(?:tóm tắt|đọc|hiểu|nội dung|phân tích|giải thích|đào sâu)\b",
                    text,
                    re.I,
                )
            )
            if asks_for_content:
                return _gmail_full_read_route(text, query=query, timezone=timezone)
            return Route("gmail_list_messages", {"query": query, "max_results": 10})
    # Gmail reads must gather fresh evidence on every turn. Without this route an
    # ADK session may answer from an older tool result and emit stale source numbers.
    if re.search(r"\b(?:gmail|email|mail|hộp thư|thư chưa đọc)\b", text, re.I) and re.search(
        r"\b(?:liệt kê|tổng hợp|tóm tắt|đọc|hiểu|xem|kiểm tra|phân loại|"
        r"gần đây|mới nhất|gần nhất)\b",
        text,
        re.I,
    ):
        requested = _gmail_requested_count(text)
        asks_for_one_latest = requested is None and bool(
            re.search(
                r"(?:\b(?:gmail|email|mail|thư)\b.*\b(?:gần nhất|mới nhất|gần đây nhất)\b|"
                r"\b(?:gần nhất|mới nhất|gần đây nhất)\b.*\b(?:gmail|email|mail|thư)\b)",
                text,
                re.I,
            )
        )
        if asks_for_one_latest:
            asks_for_content = bool(
                re.search(r"\b(?:tóm tắt|đọc|hiểu|nội dung|phân tích|giải thích)\b", text, re.I)
            )
            return Route(
                "gmail_list_messages",
                # Do not silently turn “latest” into “latest in the last 30 days”.
                # The Gmail tool returns messages newest-first; limiting to the
                # inbox also avoids picking a sent message as the user's latest mail.
                {"query": "in:inbox", "max_results": 1},
                read_match=asks_for_content,
            )
        query = _gmail_query_from_request(text, timezone=timezone) or "in:inbox"
        asks_for_content = bool(
            re.search(
                r"\b(?:tóm tắt|tổng hợp|đọc|hiểu|nội dung|phân tích|giải thích)\b",
                text,
                re.I,
            )
        )
        if asks_for_content:
            return _gmail_full_read_route(text, query=query, timezone=timezone)
        return Route(
            "gmail_list_messages",
            {"query": query, "max_results": requested or 10},
        )
    # Explicit knowledge-source selection wins over filenames in that request.
    if re.search(r"(?:\brag(?:_search)?\b|đã (?:được )?lập chỉ mục)", text, re.I):
        return Route("rag_search", _rag_arguments(text))
    if re.search(r"(?:tóm tắt|đọc).*?(?:mới (?:chỉnh sửa|nhất)|gần (?:đây )?nhất)", text, re.I):
        return Route("drive_list_files", {"page_size": 1, "exclude_folders": True}, read_match=True)
    # A source ID supplied alongside a Drive filename disambiguates duplicate
    # names.  This is especially useful for audit fixtures and shared drives;
    # the server still verifies the current user's permission when reading it.
    explicit_drive_id = _EXPLICIT_FILE_ID.search(text)
    if explicit_drive_id and re.search(r"\b(?:drive|tệp|file|tài liệu)\b", text, re.I):
        return Route(
            "drive_read_file",
            {"file_id": explicit_drive_id[1], "max_characters": 120_000},
            # The requested object is already read; ``read_match`` is reserved
            # for list/search results that still need a second read step.
            read_match=False,
        )

    # Filename is explicit; never interpret arbitrary document prose as a tool directive.
    filenames = list(dict.fromkeys(re.findall(
        r"([\w.-]+\.(?:md|txt|csv|ipynb|pdf|docx|xlsx))\b", text, re.I
    )))
    filename = re.search(r"([\w.-]+\.(?:md|txt|csv|ipynb|pdf|docx|xlsx))\b", text, re.I)
    if filename and re.search(r"(?:local|import|trên máy)", text, re.I):
        if len(filenames) > 1:
            return Route(sources=tuple(
                Route("local_source_search", {"query": name}, read_match=True)
                for name in filenames
            ), required_sources=("local",))
        return Route("local_source_search", {"query": filename[1]}, read_match=True)
    local_terms = (
        r"\b(?:tài liệu local|file local|tệp local|trên máy|vừa import|"
        r"import local|trong local|fixture local|local fixture)\b"
    )
    if re.search(local_terms, text, re.I):
        # A generic question about the local fixture is a request to inspect
        # the user's imported local sources, not a literal full-text search for
        # the rest of the sentence.  An empty query lets the source tool list
        # candidates safely; the compiler still requires exactly one match.
        if not filename and re.search(r"\b(?:fixture local|local fixture)\b", text, re.I):
            query_val = ""
        else:
            query_val = (
                filename[1]
                if filename
                else re.sub(
                    r"\b(?:tài liệu local|file local|tệp local|trên máy|vừa import|import local|"
                    r"trong local|fixture local|local fixture|tôi|cho|xem|kiểm tra|đi|gì|lên)\b",
                    "",
                    text,
                    flags=re.I,
                ).strip()
            )
        return Route("local_source_search", {"query": query_val}, read_match=True)
    if re.fullmatch(
        r"(?:liệt kê|list)(?: các| tất cả)? (?:file|tệp|tài liệu)"
        r"(?: trên| trong)? (?:google )?drive(?: của tôi)?",
        text,
        re.I,
    ):
        return Route("drive_list_files", {"page_size": 50}, True)
    if re.fullmatch(r"tìm tài liệu học tập trong drive của tôi", text, re.I):
        return Route("drive_search_files", {"query": "học", "page_size": 50}, True)
    # Compound requests must gather the document before synthesis, not search for
    # the entire sentence as if it were a filename.
    if filename and re.search(
        r"(?:đọc|tóm tắt|phân tích|tạo|sửa|chỉnh sửa|read|summarize|edit)", text, re.I
    ):
        return Route("drive_search_files", {"query": filename[1], "page_size": 10}, read_match=True)
    named_read = re.fullmatch(
        r"(?:đọc|tóm tắt|phân tích)(?: nội dung)?(?: trong| của)? "
        r"(?:docs|tài liệu|file|tệp)\s+(.+?)(?: của tôi| trong (?:google )?drive)?",
        text,
        re.I,
    )
    if named_read and not re.fullmatch(
        r"(?:đọc file|read file)\s+[A-Za-z0-9_-]{10,200}", text, re.I
    ):
        return Route(
            "drive_search_files",
            {"query": named_read[1].strip('"“”'), "page_size": 10},
            read_match=True,
        )
    match = re.fullmatch(r"(?:tìm (?:file|tệp)(?: tên)?|search file)\s+(.+)", text, re.I)
    if match:
        return Route("drive_search_files", {"query": match[1].strip('"')[:500]}, True)
    match = re.fullmatch(r"(?:đọc file|read file)\s+([A-Za-z0-9_-]{10,200})", text, re.I)
    if match:
        return Route("drive_read_file", {"file_id": match[1], "max_characters": 12000}, True)
    if re.search(r"\b(?:rag|lập chỉ mục)\b", text, re.I):
        return Route("rag_search", _rag_arguments(text))
    if filename:
        return Route("drive_search_files", {"query": filename[1], "page_size": 10}, read_match=True)
    match = re.fullmatch(r"(?:ghi nhớ|lưu sở thích)(?: rằng| là)?\s*:?\s*(.+)", text, re.I)
    if match:
        return Route("memory_save", {"kind": "preference", "content": match[1]}, True)
    match = re.fullmatch(
        r"(?:tính|calculate)\s+(-?\d+(?:\.\d+)?)\s*(?:\+|cộng)\s*(-?\d+(?:\.\d+)?)", text, re.I
    )
    if match:
        return Route("calculate", {"operation": "sum", "values": [match[1], match[2]]}, True)
    # Explicit arithmetic requests can safely bypass an expensive ReAct loop.  The
    # calculator parses a tiny grammar and never passes the expression to eval/shell.
    expression = re.search(
        r"\b(?:tính|calculate)\s+((?:(?:\d+(?:[.,]\d+)?)|[()+*/\-]|cộng|trừ|nhân|chia|\s)+)",
        text,
        re.I,
    )
    if expression:
        value = expression[1].strip()
        value = re.sub(r"\bcộng\b", "+", value, flags=re.I)
        value = re.sub(r"\btrừ\b", "-", value, flags=re.I)
        value = re.sub(r"\bnhân\b", "*", value, flags=re.I)
        value = re.sub(r"\bchia\b", "/", value, flags=re.I)
        value = re.sub(r"(?<=\d),(?=\d)", ".", value)
        return Route("calculate", {"operation": "expression", "values": [value]}, True)
    if re.search(r"(?:bộ nhớ|sở thích|memory)", text, re.I):
        return Route("memory_search", {"query": text[:2000], "limit": 4})
    return Route()
