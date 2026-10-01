"""Fail-closed guards for explicit answer constraints.

Prompts are guidance, not enforcement.  When a user explicitly rejects
unsourced claims, this module redacts a small, auditable set of unsupported
claims while preserving Markdown structure.  It deliberately does not try to
judge general truth or silently invent softer evidence.
"""

import re

_SOURCE_RESTRICTION = re.compile(
    r"(?:không|đừng|khong|dung).*?"
    r"(?:claim|khẳng\s*định|khang\s*dinh|số\s*liệu|so\s*lieu|con\s*số|con\s*so)"
    r".*?(?:nguồn|nguon|dẫn\s*chứng|dan\s*chung)"
    r"|(?:nếu|neu)\s+(?:không|khong)\s+(?:có|co)\s+(?:nguồn|nguon)",
    re.IGNORECASE,
)

_CATEGORICAL_CLAIM = re.compile(
    r"(?:"
    r"\b(?:cao|thấp|tốt|xấu)\b"
    r"|(?:rất|rat)\s+hiệu\s+quả"
    r"|hiệu\s+quả\s+(?:cao|thấp|vượt\s+trội)"
    r"|(?:bền\s+vững|ben\s+vung)"
    r"|dễ\s+quên\s+nhanh"
    r"|chống\s+lại\s+hiện\s+tượng\s+quên"
    r"|(?:ảo\s+tưởng|ao\s+tuong)\s+năng\s+lực"
    r"|(?:khoa\s+học\s+chứng\s+minh|nghiên\s+cứu\s+cho\s+thấy)"
    r"|(?:active\s+recall|spaced\s+repetition|truy\s+xuất\s+chủ\s+động|lặp\s+lại\s+ngắt\s+quãng)"
    r"|(?:tiếp\s+thu|tiep\s+thu|tiếp\s+nhận|tiep\s+nhan)\s+(?:thụ\s+động|thu\s+dong)"
    r"|(?:nhớ\s+(?:sâu|lâu)|nho\s+(?:sau|lau))"
    r"|(?:dễ|de)\s+(?:dẫn\s+đến|dan\s+den|khiến|khien)"
    # Generic verbs such as "giúp" or "hỗ trợ" are not claims by themselves.
    # Matching them alone used to erase harmless operational guidance such as
    # "giúp chia lịch học".  Guard only when the verb is tied to a scientific
    # or performance outcome that actually needs evidence.
    r"|(?:giúp|giup|hỗ\s+trợ|ho\s+tro|thúc\s+đẩy|thuc\s+day|tối\s+ưu|toi\s+uu)\s+"
    r"(?:trí\s+nhớ|tri\s+nho|khả\s+năng\s+ghi\s+nhớ|kha\s+nang\s+ghi\s+nho|"
    r"hiệu\s+quả\s+học|hieu\s+qua\s+hoc|khả\s+năng\s+tiếp\s+thu|kha\s+nang\s+tiep\s+thu)"
    r"|(?:tối\s+ưu|toi\s+uu)(?:\s+hóa|\s+hoa)?\s+thời\s+gian"
    r"|(?:tăng|tang|cải\s+thiện|cai\s+thien)\s+(?:khả\s+năng|kha\s+nang|hiệu\s+quả|hieu\s+qua|tính|tri\s+nhớ|tri\s+nho)"
    r"|(?:phát\s+huy|phat\s+huy)\s+(?:hiệu\s+quả|hieu\s+qua|tác\s+dụng|tac\s+dung)"
    r"|(?:buộc|buoc)\s+(?:não|nao)\s+bộ"
    r"|(?:đứt\s+gãy|dut\s+gay)\s+(?:bối\s+cảnh|boi\s+canh)"
    r"|(?:rèn\s+luyện|ren\s+luyen)\s+(?:khả\s+năng|kha\s+nang)"
    r"|(?:củng\s+cố|cung\s+co)\s+(?:khả\s+năng|kha\s+nang)"
    r")",
    re.IGNORECASE,
)

_CITATION_MARKER = re.compile(r"\[\d+\]")
_LIST_PREFIX = re.compile(r"^(?P<prefix>\s*(?:[-*+]\s+|\d+[.)]\s+))(?P<body>.*)$")
_LABEL_PREFIX = re.compile(
    r"^(?P<label>(?:Ưu\s+điểm|Nhược\s+điểm|Lợi\s+ích|Hạn\s+chế|Kết\s+luận)\s*:\s*)",
    re.IGNORECASE,
)

_GUARD_NOTE = (
    "> Tôi đã lược bỏ các nhận định cần bằng chứng nhưng chưa có nguồn trong lượt này. "
    "Bạn có thể cung cấp tài liệu hoặc cho phép tìm nguồn để bổ sung phần đánh giá đó."
)


def explicit_source_restriction(message: str) -> bool:
    """Return true only when the user clearly prohibits unsupported claims."""

    return bool(_SOURCE_RESTRICTION.search(message))


def source_restriction_instruction(message: str) -> str:
    """Return an explicit generation contract for a source-constrained request."""

    if not explicit_source_restriction(message):
        return ""
    return (
        "Ràng buộc bắt buộc về nguồn: nếu chưa thu được evidence từ tool trong lượt này, "
        "chỉ mô tả thao tác có thể quan sát và trade-off vận hành. Không khẳng định cơ chế "
        "nhận thức, tác động đến trí nhớ, mức hiệu quả hoặc xếp hạng. Với bảng so sánh, ưu "
        "tiên các hàng như cách thực hiện, bước chuẩn bị, dạng đầu vào và cách tự kiểm tra; "
        "bỏ hẳn tiêu chí không có bằng chứng thay vì tạo ô 'Chưa kết luận'. Phân biệt rõ "
        "gợi ý thử nghiệm với kết luận khoa học."
    )


def categorical_claim_lines(answer: str) -> list[str]:
    """List visible answer lines that contain a guarded categorical claim."""

    return [line for line in answer.splitlines() if _contains_guarded_claim(line)]


def _contains_guarded_claim(line: str) -> bool:
    """Ignore table row labels; they name criteria rather than assert outcomes."""

    if line.count("|") >= 2:
        cells = [cell for cell in line.split("|") if cell.strip()]
        return any(_CATEGORICAL_CLAIM.search(cell) for cell in cells[1:])
    return bool(_CATEGORICAL_CLAIM.search(line))


def _preserve_observable_prefix(line: str) -> str | None:
    """Keep a concrete action preceding an unsupported effect, if one exists.

    Returning ``None`` tells the caller to omit the whole assertion. This is
    preferable to rendering a table full of placeholder cells, which looked
    broken and offered no decision value to the user.
    """

    list_match = _LIST_PREFIX.match(line)
    if list_match:
        prefix = list_match.group("prefix")
        body = list_match.group("body")
        label_match = _LABEL_PREFIX.match(body)
        label = label_match.group("label") if label_match else ""
        claim = _CATEGORICAL_CLAIM.search(body)
        # Keep an observable action or a preceding operational trade-off, but
        # drop an unsupported effect clause introduced later in the sentence.
        if claim and claim.start() > len(label):
            before_claim = body[: claim.start()].rstrip()
            semicolon = before_claim.rfind(";")
            purpose = max(before_claim.rfind(" để"), before_claim.rfind(" nhằm"))
            boundary = max(semicolon, purpose)
            if boundary > len(label):
                preserved = before_claim[:boundary].rstrip(" ,;:-")
                if preserved:
                    return f"{prefix}{preserved}."
    return None


def enforce_explicit_source_restriction(
    message: str,
    answer: str,
    *,
    has_citations: bool,
) -> tuple[str, int]:
    """Redact unsupported claim lines when the user forbids unsourced claims.

    Ordinary requests are untouched. A risky line is kept only when it carries
    an inline citation marker that survived the server citation filter. Merely
    having a citation elsewhere in the answer is not sufficient. Returning the
    affected-line count lets the trace disclose the intervention.
    """

    if not explicit_source_restriction(message):
        return answer, 0

    kept: list[str] = []
    affected = 0
    for line in answer.splitlines():
        is_risky = _contains_guarded_claim(line)
        has_inline_citation = has_citations and bool(_CITATION_MARKER.search(line))
        if is_risky and not has_inline_citation:
            affected += 1
            # An unsupported comparison row is removed as one semantic unit;
            # replacing individual cells with warnings made otherwise useful
            # answers feel incomplete. For bullets, retain only a preceding
            # observable action/trade-off when it can be separated safely.
            preserved = None if line.count("|") >= 2 else _preserve_observable_prefix(line)
            if preserved:
                kept.append(preserved)
        else:
            kept.append(line)
    if not affected:
        return answer, 0

    cleaned = "\n".join(kept).strip()
    if not cleaned:
        cleaned = "Tôi chưa có đủ nguồn để đưa ra nhận định này."
    return f"{cleaned}\n\n{_GUARD_NOTE}", affected
