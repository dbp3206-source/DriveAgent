"""Public freshness policy. Private workspace text is never a web search query."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo


def needs_public_evidence(message: str) -> bool:
    text = message.casefold()
    # An explicit exclusion is not a request to search private workspace data.
    # Remove only standalone negative source clauses; other private references
    # remain in the guard below, so their contents cannot become web queries.
    source = r"(?:gmail|drive|calendar|local|lịch|bộ nhớ|memory)"
    text = re.sub(
        r"(?:^|[.!?;])\s*không\s+(?:đọc|dùng|truy cập|tìm trong)\s+"
        + source
        + r"(?:(?:\s*,\s*|\s+(?:hay|hoặc|và)\s+)" + source
        + r")*\s*(?=[.!?;]|,\s*không\s+ghi\b|$)",
        ".",
        text,
    )
    if re.search(
        r"\b(?:gmail|email|mail|drive|calendar|lịch của tôi|cuộc họp|local|"
        r"tài liệu|tệp|file|bộ nhớ|ghi nhớ|memory|skill)\b",
        text,
    ):
        return False
    if re.search(r"\b(?:giả lập|giả định|ví dụ|bài tập|hư cấu)\b", text):
        return False
    explicit = re.search(
        r"\b(?:hôm nay|hôm qua|ngày mai|mới nhất|hiện tại|gần đây|"
        r"today|yesterday|tomorrow|latest|currently)\b",
        text,
    )
    unstable = re.search(
        r"\b(?:lịch thi đấu|kết quả thi đấu|tỷ giá|giá cổ phiếu|thời tiết|"
        r"phiên bản mới|chính sách mới|đương nhiệm|ceo|tổng thống|thủ tướng)\b",
        text,
    )
    return bool(explicit or unstable)


def server_time_context(timezone: str = "Asia/Bangkok") -> dict[str, str]:
    return {"now": datetime.now(ZoneInfo(timezone)).isoformat(), "timezone": timezone}
