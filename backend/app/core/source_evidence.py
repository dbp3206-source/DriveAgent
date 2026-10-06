"""Bounded verbatim page evidence retained across conversation turns."""

PROMINENT_LINES_LABEL = (
    "Các dòng chữ cỡ lớn trên trang (tách theo vị trí và cỡ chữ; "
    "không tự xác định đây là tên báo cáo):"
)


def page_evidence_excerpt(text: str, *, plain_limit: int = 500) -> str:
    """Keep the page opening and its observed typography, never infer a title.

    The PDF extractor appends this block after native text/tables. A prefix-only
    citation loses it in followups. Preserve that actual block within 4,000
    characters, not the full page or a previous model-generated answer.
    """
    marker = text.find(PROMINENT_LINES_LABEL)
    if marker < 0:
        return text[:plain_limit]
    opening = text[:min(marker, plain_limit, 3000)].rstrip()
    typography_budget = max(0, 4000 - len(opening) - (2 if opening else 0))
    typography = text[marker:marker + typography_budget].rstrip()
    # Do not accidentally inherit typography/text from a following page.
    typography = typography.split("<!-- page:", 1)[0].rstrip()
    return "\n\n".join(part for part in (opening, typography) if part)[:4000]
