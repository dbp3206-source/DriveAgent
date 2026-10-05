"""Parse numeric page constraints from a user's request, never retrieved text."""

import re
import unicodedata

MAX_EXPLICIT_PAGES = 12


def explicit_page_numbers(message: str) -> tuple[int, ...]:
    """Return physical PDF pages in request order, including lists and ranges.

    Only an explicit page label starts a constraint; bare numbers, dates, and
    filenames cannot choose a page. Broad ranges fail before expanding them.
    """
    text = "".join(
        char for char in unicodedata.normalize("NFD", message.casefold())
        if not unicodedata.combining(char)
    ).replace("đ", "d")
    clauses = re.finditer(
        r"\b(?:trang|pages?|p\.)\s*:?[ \t]*(?:(?:vat ly|pdf|so|thu|number)\s*)?"
        r"(?P<pages>\d+(?:(?:\s*(?:[-–—]|den|to)\s*\d+)"
        r"|(?:\s*(?:,|va|and|&)\s*\d+))*)"
        r"(?!\d|[./]\d)",
        text,
    )
    pages: list[int] = []
    for clause in clauses:
        prefix = text[:clause.start()]
        if re.search(
            r"(?:khong (?:doc|dung|lay|xem)|bo qua|ngoai tru|exclude|except|"
            r"do not (?:read|use)|don't (?:read|use))\s*(?:pdf\s*)?$", prefix,
        ):
            continue
        for group in re.split(r"\s*(?:,|\bva\b|\band\b|&)\s*", clause["pages"]):
            bounds = re.split(r"\s*(?:[-–—]|\bden\b|\bto\b)\s*", group)
            start, end = int(bounds[0]), int(bounds[-1])
            if start < 1 or end < start or end - start >= MAX_EXPLICIT_PAGES:
                raise ValueError("Invalid or excessive explicit page range")
            pages.extend(number for number in range(start, end + 1) if number not in pages)
            if len(pages) > MAX_EXPLICIT_PAGES:
                raise ValueError("Too many explicit pages")
    return tuple(pages)
