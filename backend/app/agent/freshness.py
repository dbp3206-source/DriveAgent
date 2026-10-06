"""Public freshness policy. Private workspace text is never a web search query."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo


def needs_public_evidence(message: str) -> bool:
    text = message.casefold()
    # "Latest" may refer to the user's current conversation state, not public
    # news. Never send a reformulation/correction of that state to web search.
    # Keep the guard specific to preserving conversation state: a question
    # about the current economic context must still require public evidence.
    if re.search(
        r"\b(?:giữ|giữ nguyên|giữ lại|tiếp nối|dựa trên|theo|nhắc lại)\s+(?:nguyên\s+)?"
        r"(?:bối cảnh|ngữ cảnh|bản nháp|câu trả lời|yêu cầu|cuộc trò chuyện)\s+"
        r"(?:mới nhất|hiện tại|vừa rồi|trước đó)\b",
        text,
    ):
        return False
    # An explicit exclusion is not a request to search private workspace data.
    # Remove only standalone negative source clauses; other private references
    # remain in the guard below, so their contents cannot become web queries.
    source = r"(?:tài\s+liệu\s+local|gmail|drive|calendar|local|lịch|bộ nhớ|memory)"
    text = re.sub(
        r"(?:^|[.!?;,])\s*không\s+(?:(?:đọc|dùng|truy cập|tìm trong)\s+)?"
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
        r"cập nhật|today|yesterday|tomorrow|latest|currently)\b",
        text,
    )
    unstable = re.search(
        r"\b(?:lịch thi đấu|kết quả thi đấu|tỷ giá|giá cổ phiếu|thời tiết|"
        r"phiên bản mới|chính sách mới|đương nhiệm|ceo|tổng thống|thủ tướng)\b",
        text,
    )
    selected_public_source = bool(
        re.search(r"https://[^\s<>]+", text)
        and re.search(r"\b(?:kiểm nguồn|đọc nguồn|kiểm chứng|xác minh|đọc trang)\b", text)
        and not re.search(r"\b(?:không|đừng)\s+(?:đọc|dùng|truy cập|tìm)\s+web\b", text)
    )
    return bool(explicit or unstable or selected_public_source)


def server_time_context(timezone: str = "Asia/Bangkok") -> dict[str, str]:
    return {"now": datetime.now(ZoneInfo(timezone)).isoformat(), "timezone": timezone}
