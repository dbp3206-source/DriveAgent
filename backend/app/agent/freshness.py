"""Public freshness policy. Private workspace text is never a web search query."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from app.agent.intent import explicit_source_exclusions


def needs_public_evidence(message: str) -> bool:
    text = message.casefold()
    if "web" in explicit_source_exclusions(message):
        return False
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
    source = (
        r"(?:(?:tài\s+liệu|tệp|file)\s+(?:riêng|cá\s+nhân|nội\s+bộ|local)|"
        r"gmail|drive|calendar|local|lịch|bộ nhớ|memory)"
    )
    text = re.sub(
        r"(?:^|[.!?;,])\s*không\s+(?:(?:đọc|dùng|truy cập|tìm trong)\s+)?"
        + source
        + r"(?:(?:\s*,\s*|\s+(?:hay|hoặc|và)\s+)" + source
        + r")*\s*(?=[.!?;]|,\s*không\s+ghi\b|$)",
        ".",
        text,
    )
    # A product name in official public documentation is a topic, not a
    # request to read the user's workspace. Mask only that topic clause;
    # private references elsewhere still veto transmission to web search.
    requested_web = re.search(
        r"\b(?:tìm(?: kiếm)?|tra cứu|đọc|kiểm tra|tìm hiểu)\s+"
        r"(?:(?:trên|bằng|qua|nguồn|thông tin|từ)\s+){0,2}"
        r"(?:web|internet|nguồn công khai)\b", text,
    )
    if requested_web:
        clauses = re.split(r"([.!?;\n])", text)
        for index in range(0, len(clauses), 2):
            clause = clauses[index]
            if re.search(
                r"\b(?:tài liệu|hướng dẫn|documentation)\s+"
                r"(?:api\s+)?(?:chính thức|công khai|official|public)\b", clause,
            ) and not re.search(
                r"\b(?:của tôi|của chúng tôi|nội bộ|khách hàng|đính kèm|"
                r"đã (?:chọn|tải|gửi)|vừa (?:nhập|tải))\b", clause,
            ):
                clauses[index] = re.sub(
                    r"\b(?:google\s+)?(?:drive|gmail|calendar)\b", "dịch vụ", clause,
                )
        text = "".join(clauses)
    if re.search(
        r"\b(?:gmail|email|mail|drive|calendar|lịch của tôi|cuộc họp|local|"
        r"bộ nhớ|ghi nhớ|memory|skill)\b|"
        r"\b(?:tài liệu|tệp|file)\s+(?:riêng|cá nhân|nội bộ|khách hàng|"
        r"của tôi|của chúng tôi|đã (?:chọn|tải|gửi)|đính kèm|"
        r"mới (?:chỉnh sửa|nhất)|gần đây|vừa (?:nhập|tải))\b|"
        r"\b[\w.-]+\.(?:pdf|docx|xlsx|csv|md|txt)\b|"
        r"https://(?:docs|drive|mail)\.google\.com/",
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
    return bool(explicit or unstable or selected_public_source or requested_web)


def server_time_context(timezone: str = "Asia/Bangkok") -> dict[str, str]:
    return {
        "now": datetime.now(ZoneInfo(timezone)).isoformat(),
        "timezone": timezone,
        "usage_policy": (
            "Đây chỉ là đồng hồ máy chủ để hiểu hôm nay/hôm qua/ngày mai. "
            "Không thay ngày giờ cuộc hẹn, hạn chót hoặc sự kiện trong hội thoại bằng đồng hồ này. "
            "Khi người dùng nhắc lại theo ngữ cảnh hiện tại, giữ dữ kiện hội thoại sau "
            "đính chính mới nhất; không hiểu ngữ cảnh hiện tại là yêu cầu đọc đồng hồ. "
            "Nếu không xác định được ngày giờ của sự kiện thì hỏi lại, không dùng giờ máy chủ."
        ),
    }
