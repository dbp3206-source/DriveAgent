"""Chunking có ý thức về cấu trúc và giữ overlap để không cắt mất ngữ cảnh."""

import re
from dataclasses import dataclass

HEADING_PATTERN = re.compile(r"(?m)^(#{1,6}\s+.+|[^\n]{1,120}\n[-=]{3,})$")


@dataclass(slots=True)
class ChunkDraft:
    index: int
    content: str
    heading: str | None


def _target_size(mime_type: str) -> tuple[int, int]:
    if "spreadsheet" in mime_type or mime_type in {"text/csv", "application/csv"}:
        return 2200, 250
    if "presentation" in mime_type:
        return 900, 120
    if mime_type.startswith("text/"):
        return 1400, 180
    return 1200, 180


def chunk_document(text: str, mime_type: str) -> list[ChunkDraft]:
    """Recursive-style split: paragraph trước, câu sau, cuối cùng mới cắt cứng."""

    normalized = re.sub(r"\r\n?", "\n", text)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if not normalized:
        return []

    target, overlap = _target_size(mime_type)
    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    pieces: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= target:
            pieces.append(paragraph)
            continue
        sentences = re.split(r"(?<=[.!?。！？])\s+|\n", paragraph)
        for sentence in sentences:
            if len(sentence) <= target:
                pieces.append(sentence.strip())
            else:
                pieces.extend(
                    sentence[start : start + target]
                    for start in range(0, len(sentence), target - overlap)
                )

    chunks: list[ChunkDraft] = []
    buffer = ""
    last_heading: str | None = None
    for piece in pieces:
        if HEADING_PATTERN.match(piece):
            last_heading = piece.splitlines()[0].lstrip("# ").strip()
        candidate = f"{buffer}\n\n{piece}".strip() if buffer else piece
        if len(candidate) <= target:
            buffer = candidate
            continue
        if buffer:
            chunks.append(ChunkDraft(len(chunks), buffer, last_heading))
            prefix = buffer[-overlap:].lstrip()
            buffer = f"{prefix}\n\n{piece}".strip()
        else:
            buffer = piece
    if buffer:
        chunks.append(ChunkDraft(len(chunks), buffer, last_heading))
    return chunks
