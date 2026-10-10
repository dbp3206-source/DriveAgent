"""Deterministic public-query, date and exact-excerpt boundaries; no inference calls."""

import re
from datetime import datetime, timedelta
from urllib.parse import urlsplit


def normalize_public_question(question: str) -> str:
    """Remove presentation wrappers, never the content of a copied question."""
    text = re.sub(r"(?:^|\n)\s*```[A-Za-z0-9_-]*[ \t]*", "", question)
    text = text.replace("```", "")
    text = re.sub(r"(?m)^\s*(?:>\s*|[-*]\s+|\d+[.)]\s+)", "", text)
    return text.strip()


def official_sources_requested(question: str) -> bool:
    text = normalize_public_question(question)
    text = re.sub(r"(?:không|đừng)\s+(?:cần\s+)?(?:dùng\s+)?nguồn\s+chính\s+thức", "", text,
                  flags=re.I)
    return bool(re.search(r"nguồn\s+chính\s+thức|website\s+chính\s+thức|"
                          r"official\s+(?:source|website)",
                          text, re.I))


def relative_dates(question: str, now: datetime) -> dict[str, str]:
    text = normalize_public_question(question)
    offsets = {"hôm qua": -1, "ngày mai": 1, "yesterday": -1, "tomorrow": 1}
    return {label: (now.date() + timedelta(days=offset)).strftime("%d/%m/%Y")
            for label, offset in offsets.items()
            if re.search(r"\b" + label + r"\b", text, re.I)}


def government_publication(url: str) -> bool:
    """Recognize restricted government namespaces, not a word in an arbitrary host."""
    try:
        host = (urlsplit(url).hostname or "").casefold().rstrip(".")
    except ValueError:
        return False
    return bool(re.search(r"(?:^|\.)(?:gov(?:\.[a-z]{2})?|go\.(?:jp|kr|id)|lg\.jp|"
                          r"gouv\.fr|gob\.(?:mx|es|ar|pe)|gc\.ca|admin\.ch|chinhphu\.vn)$", host))


def same_public_host(url: str, selected_url: str) -> bool:
    try:
        host = (urlsplit(url).hostname or "").casefold().rstrip(".")
        selected = (urlsplit(selected_url).hostname or "").casefold().rstrip(".")
    except ValueError:
        return False
    return bool(selected and (host == selected or host.endswith("." + selected)))


def relevant_excerpt(raw: str, question: str, maximum: int = 9000) -> str:
    """Select bounded original spans, retaining identity and relevant lower-page text.

    Only whitespace is normalized. Omission separators are explicit; a quote
    cannot silently join two distant sections into a fabricated sentence.
    """
    text = re.sub(r"\s+", " ", raw).strip()[:100_000]
    if len(text) <= maximum:
        return text
    words = list(dict.fromkeys(re.findall(r"[^\W_]{3,}", question.casefold())))
    ignored = {"nguồn", "chính", "thức", "theo", "ngày", "nào", "không", "của", "cho",
               "hôm", "nay", "mai", "qua", "kiểm", "câu", "hỏi", "website", "official"}
    words = [word for word in words if word not in ignored][:24]
    if not words:
        return text[:maximum]
    ranked = []
    for start in range(0, len(text), 650):
        part = text[start:start + 1500].casefold()
        matches = sum(bool(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", part))
                      for word in words)
        if matches:
            bonus = 2 * bool(re.search(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{4}|"
                                      r"schedule|calendar|official website|lịch|diễn ra", part))
            ranked.append((matches + bonus, start))
    if not ranked:
        return text[:maximum]
    spans = [(0, 1800)]
    for _, start in sorted(ranked, key=lambda item: (-item[0], item[1])):
        end = min(len(text), start + 1500)
        if any(start < prior_end and end > prior_start for prior_start, prior_end in spans):
            continue
        if sum(end_ - start_ for start_, end_ in spans) + end - start > maximum - 60:
            continue
        spans.append((start, end))
        if len(spans) >= 5:
            break
    spans.sort()
    return "\n[…]\n".join(text[start:end] for start, end in spans)[:maximum]
