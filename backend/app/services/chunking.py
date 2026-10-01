"""Chunking có ý thức về cấu trúc và giữ overlap để không cắt mất ngữ cảnh."""

import re
from dataclasses import dataclass

HEADING_PATTERN = re.compile(r"(?m)^(#{1,6}\s+.+|[^\n]{1,120}\n[-=]{3,})$")
PAGE_MARKER_PATTERN = re.compile(
    r"<!--\s*(?:page|page-break-after):(\d+)\s*-->", re.IGNORECASE
)
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\((?:<[^>]+>|[^)\n]+)\)")
LEGACY_ASSET_COMMENT = re.compile(
    r"<!--\s*DriveAgent assets:.*?-->", re.IGNORECASE | re.DOTALL
)


@dataclass(slots=True)
class ChunkDraft:
    index: int
    content: str
    heading: str | None
    page_number: int | None = None


def _target_size(mime_type: str) -> tuple[int, int]:
    if "spreadsheet" in mime_type or mime_type in {"text/csv", "application/csv"}:
        return 2200, 250
    if "presentation" in mime_type:
        return 900, 150
    if mime_type.startswith("text/"):
        return 1500, 200
    return 1400, 200


def _is_table_block(block: str) -> bool:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    return len(lines) >= 2 and lines[0].startswith("|") and any(
        "|" in line and re.match(r"^\|?\s*:?-{3,}", line) for line in lines[:3]
    )


def _split_table_block(table_text: str, target: int) -> list[str]:
    lines = [line.strip() for line in table_text.splitlines() if line.strip()]
    if len(lines) < 3 or len(table_text) <= target:
        return [table_text]
    header = lines[0]
    delimiter = lines[1]
    header_block = f"{header}\n{delimiter}"

    chunks: list[str] = []
    current_rows: list[str] = []
    current_len = len(header_block)

    for row in lines[2:]:
        row_len = len(row) + 1
        if current_rows and (current_len + row_len > target):
            chunks.append(header_block + "\n" + "\n".join(current_rows))
            current_rows = [row]
            current_len = len(header_block) + row_len
        else:
            current_rows.append(row)
            current_len += row_len

    if current_rows:
        chunks.append(header_block + "\n" + "\n".join(current_rows))
    return chunks


def _chunk_section(
    text: str,
    mime_type: str,
    *,
    page_number: int | None,
    start_index: int,
) -> list[ChunkDraft]:
    """Chunk một section; PDF page boundaries never share retrieval evidence."""

    # A PDF parser may emit hundreds of extracted-image URLs. Empty image links
    # carry no searchable meaning and previously consumed embedding quota while
    # outranking real prose. Keep descriptive alt text as evidence; the complete
    # visual document remains available in the Drive reader itself.
    normalized = LEGACY_ASSET_COMMENT.sub("", text)
    normalized = MARKDOWN_IMAGE_PATTERN.sub(
        lambda match: f"Hình: {match.group(1).strip()}" if match.group(1).strip() else "",
        normalized,
    )
    normalized = re.sub(r"\r\n?", "\n", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if not normalized:
        return []

    target, overlap = _target_size(mime_type)
    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    pieces: list[str] = []
    for paragraph in paragraphs:
        if _is_table_block(paragraph):
            pieces.extend(_split_table_block(paragraph, target))
            continue
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
            chunks.append(
                ChunkDraft(start_index + len(chunks), buffer, last_heading, page_number)
            )
            prefix = buffer[-overlap:].lstrip()
            buffer = f"{prefix}\n\n{piece}".strip()
        else:
            buffer = piece
    if buffer:
        chunks.append(ChunkDraft(start_index + len(chunks), buffer, last_heading, page_number))
    return chunks


def chunk_document(text: str, mime_type: str) -> list[ChunkDraft]:
    """Recursive-style split, preserving tables and PDF page provenance.

    OpenDataLoader inserts a numbered marker before each PDF page. We deliberately
    flush at those boundaries so one citation cannot silently mix
    evidence from two pages. Other document types keep the original behaviour.
    """

    matches = list(PAGE_MARKER_PATTERN.finditer(text))
    if not matches:
        return _chunk_section(text, mime_type, page_number=None, start_index=0)

    chunks: list[ChunkDraft] = []
    chunks.extend(
        _chunk_section(
            text[: matches[0].start()], mime_type, page_number=None, start_index=0
        )
    )
    for position, match in enumerate(matches):
        page_number = int(match.group(1))
        section_end = matches[position + 1].start() if position + 1 < len(matches) else len(text)
        chunks.extend(
            _chunk_section(
                text[match.end() : section_end],
                mime_type,
                page_number=page_number,
                start_index=len(chunks),
            )
        )
    return chunks
