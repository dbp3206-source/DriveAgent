"""Small, shared intent boundaries used before routing and tool selection."""

import re

SOURCE_NAMES = {
    "gmail": r"(?:gmail|e-?mail|mail|hộp\s+thư)",
    "drive": r"(?:google\s+drive|drive)",
    "local": r"(?:(?:tài\s+liệu|tệp|file)\s+local|local(?:\s+files?)?)",
    "memory": r"(?:bộ\s+nhớ|memory)",
    "calendar": r"(?:google\s+calendar|calendar|lịch(?:\s+hẹn)?|cuộc\s+hẹn)",
    "web": r"(?:web|internet|website|trang\s+web|nguồn\s+công\s+khai)",
}
_SOURCE = re.compile(
    "|".join(rf"(?P<{name}>\b{pattern}\b)" for name, pattern in SOURCE_NAMES.items()), re.I
)
_DENIAL = re.compile(
    r"\b(?:không|khong|đừng|chưa|no|do\s+not|don't|dont|without)\s+"
    r"(?:(?:trực\s+tiếp|directly|truy\s+cập|truy\s+cap|dùng|sử\s+dụng|dung|"
    r"đọc|doc|mở|lấy|lay|tra\s+cứu|tra\s+cuu|tìm(?:\s+kiếm)?|tim\s+kiem|"
    r"access|accessing|use|using|read|reading|open|search|query|fetch|look\s+up)\s+){0,4}",
    re.I,
)
_SEPARATOR = re.compile(r"\s*(?:[,/]|\b(?:hay|hoặc|và|or|and)\b)\s*", re.I)
_QUANTIFIER = re.compile(r"(?:(?:cả|tất\s+cả|các|mọi|hai|ba|bốn|\d+|any|all|the)\s+)*", re.I)


def explicit_source_exclusions(message: str) -> frozenset[str]:
    """Only a read denial followed by a source/list denies source access.

    A result condition (``không có lịch``), a write denial (``không tạo lịch``)
    or a later positive clause must not become a read prohibition.
    """
    excluded: set[str] = set()
    for denial in _DENIAL.finditer(message):
        position = _QUANTIFIER.match(message, denial.end()).end()
        while source := _SOURCE.match(message, position):
            excluded.add(source.lastgroup or "")
            separator = _SEPARATOR.match(message, source.end())
            if not separator:
                break
            position = separator.end()
    return frozenset(excluded)


def workspace_creation_requested(message: str) -> bool:
    """Require a concrete output action, not a verb somewhere before a topic."""
    artifact = r"(?:(?:google|gg)\s+)?(?:docs?|sheets?|documents?|tài\s+liệu|bảng\s+tính)"
    action = re.compile(
        r"\b(?:tạo|soạn|lưu|xuất|chuyển|sửa|chỉnh\s+sửa|create|edit|save|export)\s+"
        r"(?:(?:một|bản|thành|sang|vào|a|an|the|as|to|in|new)\s+){0,3}"
        + artifact + r"\b", re.I,
    )
    export_result = re.compile(
        r"\b(?:lưu|xuất|chuyển|save|export|convert)\s+"
        r"(?:bản\s+nháp|nội\s+dung|kết\s+quả|báo\s+cáo|draft|result|report)\s+"
        r"(?:này\s+|đã\s+chọn\s+)?(?:thành|sang|vào|as|to|in)\s+"
        + artifact + r"\b", re.I,
    )
    for clause in re.split(r"[.;!?\n]|\b(?:nhưng|but)\b", message, flags=re.I):
        positive = re.sub(
            r"\b(?:không|đừng|chưa|do\s+not|don't|never)\s+"
            r"(?:tạo|soạn|làm|sửa|chỉnh sửa|lưu|chuyển|xuất|create|edit|save|put|export)"
            r"\b[^,]*", " ", clause, flags=re.I,
        )
        if action.search(positive) or export_result.search(positive):
            return True
    return False
