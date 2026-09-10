"""Small, conservative routes. Ambiguous text is not interpreted as a write command."""

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Route:
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    direct: bool = False
    read_match: bool = False


def route_request(message: str) -> Route:
    text = message.strip().rstrip(".?!")
    # Explicit knowledge-source selection wins over filenames in that request.
    if re.search(r"(?:\brag(?:_search)?\b|đã (?:được )?lập chỉ mục)", text, re.I):
        return Route("rag_search", {"query": text[:2000], "limit": 6})
    if re.search(r"(?:tóm tắt|đọc).*?(?:mới (?:chỉnh sửa|nhất)|gần (?:đây )?nhất)", text, re.I):
        return Route("drive_list_files", {"page_size": 1, "exclude_folders": True}, read_match=True)
    # Filename is explicit; never interpret arbitrary document prose as a tool directive.
    filename = re.search(r"([\w.-]+\.(?:md|txt|csv|ipynb|pdf|docx|xlsx))\b", text, re.I)
    if filename and re.search(r"(?:local|import|trên máy)", text, re.I):
        return Route("local_source_search", {"query": filename[1]}, read_match=True)
    if re.fullmatch(
        r"(?:liệt kê|list)(?: các| tất cả)? (?:file|tệp|tài liệu)"
        r"(?: trên| trong)? (?:google )?drive(?: của tôi)?",
        text,
        re.I,
    ):
        return Route("drive_list_files", {"page_size": 50}, True)
    if re.fullmatch(r"tìm tài liệu học tập trong drive của tôi", text, re.I):
        return Route("drive_search_files", {"query": "học", "page_size": 50}, True)
    # Compound requests must gather the document before synthesis, not search for
    # the entire sentence as if it were a filename.
    if filename and re.search(
        r"(?:đọc|tóm tắt|phân tích|tạo|sửa|chỉnh sửa|read|summarize|edit)", text, re.I
    ):
        return Route("drive_search_files", {"query": filename[1], "page_size": 10}, read_match=True)
    named_read = re.fullmatch(
        r"(?:đọc|tóm tắt|phân tích)(?: nội dung)?(?: trong| của)? "
        r"(?:docs|tài liệu|file|tệp)\s+(.+?)(?: của tôi| trong (?:google )?drive)?",
        text,
        re.I,
    )
    if named_read and not re.fullmatch(
        r"(?:đọc file|read file)\s+[A-Za-z0-9_-]{10,200}", text, re.I
    ):
        return Route(
            "drive_search_files",
            {"query": named_read[1].strip('"“”'), "page_size": 10},
            read_match=True,
        )
    match = re.fullmatch(r"(?:tìm (?:file|tệp)(?: tên)?|search file)\s+(.+)", text, re.I)
    if match:
        return Route("drive_search_files", {"query": match[1].strip('"')[:500]}, True)
    match = re.fullmatch(r"(?:đọc file|read file)\s+([A-Za-z0-9_-]{10,200})", text, re.I)
    if match:
        return Route("drive_read_file", {"file_id": match[1], "max_characters": 12000}, True)
    if re.search(r"\b(?:rag|lập chỉ mục)\b", text, re.I):
        return Route("rag_search", {"query": text[:2000], "limit": 6})
    if filename:
        return Route("drive_search_files", {"query": filename[1], "page_size": 10}, read_match=True)
    match = re.fullmatch(r"(?:ghi nhớ|lưu sở thích)(?: rằng| là)?\s*:?\s*(.+)", text, re.I)
    if match:
        return Route("memory_save", {"kind": "preference", "content": match[1]}, True)
    match = re.fullmatch(
        r"(?:tính|calculate)\s+(-?\d+(?:\.\d+)?)\s*(?:\+|cộng)\s*(-?\d+(?:\.\d+)?)", text, re.I
    )
    if match:
        return Route("calculate", {"operation": "sum", "values": [match[1], match[2]]}, True)
    if re.search(r"(?:bộ nhớ|sở thích|memory)", text, re.I):
        return Route("memory_search", {"query": text[:2000], "limit": 4})
    return Route()
