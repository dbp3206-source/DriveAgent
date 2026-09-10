"""Stable per-turn source numbers, independent from a document's chunk index."""

from typing import Any


def source_references(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # chunk_index is a position inside the document, NOT the displayed [n] reference.
    return [{"reference": index, **citation} for index, citation in enumerate(citations, start=1)]
