"""Import văn bản local có giới hạn. Notebook chỉ đọc source, không chạy cell."""

import csv
import hashlib
import io
import json
import re
from pathlib import PurePath
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from app.auth.permissions import RAG_READ
from app.core.source_evidence import page_evidence_excerpt
from app.db.models import LocalSource
from app.services.chunking import chunk_document
from app.tools.contracts import ToolContext, ToolDefinition, ToolError

MAX_BYTES = 2_000_000
MAX_TEXT = 100_000


def excluded_ocr_source(source, settings) -> bool:
    """Quarantine historical generated OCR without deleting its original/data.

    Native-only re-extraction removes this generated notice and restores access.
    The exact notice was written by the PDF pipeline, not supplied by the model.
    """
    return (not getattr(settings, "pdf_ocr_enabled", False)
            and source.name.casefold().endswith(".pdf")
            and "Văn bản OCR: cần đối chiếu ảnh gốc khi sử dụng số liệu." in source.content)


def extract_text(name: str, data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise ToolError("Tệp vượt 2 MB.", code="file_too_large")
    suffix = PurePath(name).suffix.lower()
    if suffix not in {".txt", ".md", ".csv", ".ipynb"}:
        raise ToolError(
            "Import local hiện hỗ trợ TXT, MD, CSV và IPYNB UTF-8.", code="unsupported_type"
        )
    try:
        text = data.decode("utf-8-sig")
        if "\x00" in text:
            raise ValueError("binary")
        if suffix == ".ipynb":
            notebook = json.loads(text)
            if not isinstance(notebook, dict) or not isinstance(notebook.get("cells"), list):
                raise ValueError("notebook")
            parts = []
            for cell in notebook["cells"]:
                if not isinstance(cell, dict):
                    raise ValueError("cell")
                source = cell.get("source", "")
                if isinstance(source, list) and all(isinstance(line, str) for line in source):
                    source = "".join(source)
                if not isinstance(source, str):
                    raise ValueError("source")
                parts.append(source)
            text = "\n\n".join(parts)
        elif suffix == ".csv":
            rows = list(csv.reader(io.StringIO(text)))
            if len(rows) > 5000 or any(len(row) > 100 for row in rows):
                raise ToolError("CSV vượt 5000 dòng hoặc 100 cột.", code="table_too_large")
        if not text.strip():
            raise ToolError("Tệp không có văn bản để đọc.", code="empty_document")
        if len(text) > MAX_TEXT:
            raise ToolError(
                "Văn bản vượt 100.000 ký tự; hãy chia thành tệp nhỏ hơn.", code="text_too_large"
            )
        return text
    except (UnicodeError, ValueError, csv.Error) as exc:
        raise ToolError("Không đọc được định dạng/UTF-8 của tệp.", code="invalid_document") from exc


class LocalSearchInput(BaseModel):
    query: str = Field(default="", max_length=200)


class LocalReadInput(BaseModel):
    source_id: str | UUID = Field(default="", description="ID hoặc tên tệp local cần đọc")
    page_number: int | None = Field(
        default=None, ge=1,
        description=("Trang PDF chính xác cần đọc. Khi người dùng chỉ rõ trang, "
                     "dùng trường này thay vì tìm theo từ khóa."),
    )
    offset: int = Field(default=0, ge=0, le=250_000_000)
    query: str = Field(default="", max_length=2000)
    limit: int = Field(default=6, ge=1, le=12)


class LocalOutput(BaseModel):
    data: dict


async def search_local(payload: LocalSearchInput, context: ToolContext) -> LocalOutput:
    clean_q = payload.query.strip()
    query = select(LocalSource).where(LocalSource.user_id == context.user.id)

    stop_words = {
        "tài", "liệu", "file", "tệp", "local", "vừa", "import", "cho", "tôi", "xem",
        "đọc", "về", "trong", "trên", "máy", "của", "gì", "nào", "kiểm", "tra", "tóm", "tắt"
    }
    tokens = [
        t.lower() for t in re.findall(r"[\w.-]+", clean_q)
        if t.lower() not in stop_words and len(t) > 1
    ]

    if clean_q and tokens:
        clauses = [
            LocalSource.name.contains(clean_q, autoescape=True),
            LocalSource.content.contains(clean_q, autoescape=True),
        ]
        for token in tokens:
            clauses.append(LocalSource.name.contains(token, autoescape=True))
            clauses.append(LocalSource.content.contains(token, autoescape=True))
        query = query.where(or_(*clauses))
    elif clean_q and not tokens:
        query = query.where(
            or_(
                LocalSource.name.contains(clean_q, autoescape=True),
                LocalSource.content.contains(clean_q, autoescape=True),
            )
        )

    rows = list(await context.db.scalars(query.order_by(LocalSource.created_at.desc()).limit(50)))

    # Only generic navigation queries may fall back to recent files. Falling back
    # after a specific query would make an unrelated document look like evidence.
    if not rows and clean_q and not tokens:
        fallback_query = select(LocalSource).where(LocalSource.user_id == context.user.id)
        rows = list(
            await context.db.scalars(
                fallback_query.order_by(LocalSource.created_at.desc()).limit(10)
            )
        )

    def _extract_snippet(content: str, q: str, tok_list: list[str]) -> tuple[str, int | None, int]:
        lower_content = content.lower()
        pos = -1
        if q and q.lower() in lower_content:
            pos = lower_content.find(q.lower())
        else:
            for t in tok_list:
                pos = lower_content.find(t)
                if pos >= 0:
                    break
        anchor = max(pos, 0)
        start = max(0, pos - 80) if pos >= 0 else 0
        end = min(len(content), anchor + 280)
        markers = list(re.finditer(r"<!--\s*page:(\d+)\s*-->", content))
        preceding = [marker for marker in markers if marker.start() <= anchor]
        page_number = int(preceding[-1].group(1)) if preceding else None
        if preceding:
            start = max(start, preceding[-1].start())
            following = next((marker for marker in markers if marker.start() > anchor), None)
            if following:
                end = min(end, following.start())
        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(content) else ""
        return prefix + content[start:end].strip() + suffix, page_number, start

    ranked_rows = []
    for row in rows:
        if excluded_ocr_source(row, context.settings):
            continue
        haystack = f"{row.name} {row.content}".casefold()
        match_score = sum(haystack.count(token.casefold()) for token in tokens)
        if clean_q.casefold() and clean_q.casefold() in haystack:
            match_score += 3
        ranked_rows.append((match_score, row))
    ranked_rows.sort(key=lambda item: (item[0], item[1].created_at), reverse=True)
    sources = []
    for score, row in ranked_rows:
        snippet, page_number, offset = _extract_snippet(row.content, clean_q, tokens)
        sources.append({
            "id": row.id,
            "name": row.name,
            "characters": len(row.content),
            "snippet": snippet,
            "page_number": page_number,
            "offset": offset,
            "match_score": score,
            "web_view_link": (
                f"{context.settings.public_base_url}/api/local-sources/{row.id}/text"
            ),
        })

    return LocalOutput(
        data={
            "sources": sources,
            "search_type": "keyword_and_content" if tokens else "recent_sources",
            "limit": 50,
        }
    )


async def read_local(payload: LocalReadInput, context: ToolContext) -> LocalOutput:
    clean_id = str(payload.source_id).removeprefix("local:").strip()
    row = await context.db.scalar(
        select(LocalSource).where(
            LocalSource.user_id == context.user.id,
            or_(LocalSource.id == clean_id, LocalSource.name == clean_id),
        )
    )
    if row is None:
        raise ToolError("Không tìm thấy tài liệu local của bạn.", code="source_not_found")
    if excluded_ocr_source(row, context.settings):
        raise ToolError("Bản OCR cũ nằm ngoài phạm vi; hãy đọc lại PDF có lớp văn bản.",
                        code="pdf_ocr_excluded")
    if payload.page_number is not None:
        markers = list(re.finditer(r"<!--\s*page:(\d+)\s*-->", row.content))
        selected = next(
            (index for index, marker in enumerate(markers)
             if int(marker.group(1)) == payload.page_number), None
        )
        if selected is None:
            raise ToolError("Không tìm thấy trang được yêu cầu trong tài liệu.",
                            code="source_page_not_found")
        marker = markers[selected]
        page_end = (markers[selected + 1].start()
                    if selected + 1 < len(markers) else len(row.content))
        start = min(marker.end() + payload.offset, page_end)
        end = min(start + 12000, page_end)
        text = row.content[start:end]
        return LocalOutput(data={
            "source_id": row.id, "name": row.name, "content_hash": row.content_hash,
            "retrieval_method": "exact_page", "page_number": payload.page_number,
            "offset": payload.offset, "next_offset": end - marker.end() if end < page_end else None,
            "text": text,
            "citations": [{
                "file_id": f"local:{row.id}", "file_name": row.name,
                "chunk_index": start, "page_number": payload.page_number,
                "snippet": page_evidence_excerpt(text), "score": 1.0,
                "web_view_link": (
                    f"{context.settings.public_base_url}/api/local-sources/{row.id}/text"
                ),
            }],
        })
    if payload.query:
        terms = set(re.findall(r"\w+", payload.query.casefold()))
        drafts = chunk_document(row.content, "text/markdown")
        ranked = sorted(drafts, key=lambda draft: (
            -len(terms & set(re.findall(r"\w+", draft.content.casefold()))), draft.index
        ))[:payload.limit]
        citations = [{
            "file_id": f"local:{row.id}", "file_name": row.name,
            "chunk_index": draft.index, "page_number": draft.page_number,
            "snippet": draft.content,
            "web_view_link": f"{context.settings.public_base_url}/api/local-sources/{row.id}/text",
            "score": 1.0,
        } for draft in ranked]
        return LocalOutput(data={
            "source_id": row.id, "name": row.name, "content_hash": row.content_hash,
            "retrieval_method": "page_aware_keyword", "citations": citations,
            "text": "\n\n".join(draft.content for draft in ranked),
        })
    end = payload.offset + 12000
    page_markers = list(re.finditer(r"<!--\s*page:(\d+)\s*-->", row.content))
    preceding = [marker for marker in page_markers if marker.start() <= payload.offset]
    page_number = int(preceding[-1].group(1)) if preceding else (
        int(page_markers[0].group(1)) if page_markers else None)
    following = next((marker for marker in page_markers if marker.start() > payload.offset), None)
    if following is not None and preceding:
        end = min(end, following.start())
    return LocalOutput(
        data={
            "source_id": row.id,
            "name": row.name,
            "text": row.content[payload.offset : end],
            "offset": payload.offset,
            "next_offset": end if end < len(row.content) else None,
            "content_hash": row.content_hash,
            "citations": [
                {
                    "file_id": f"local:{row.id}",
                    "file_name": row.name,
                    "chunk_index": payload.offset,
                    "page_number": page_number,
                    "snippet": row.content[payload.offset : min(end, payload.offset + 500)],
                    "web_view_link": (
                        f"{context.settings.public_base_url}/api/local-sources/{row.id}/text"
                    ),
                    "score": 1.0,
                }
            ],
        }
    )


def hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def local_source_tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="local_source_search",
            description=(
                "Liệt kê hoặc tìm kiếm tài liệu/tệp tin đã import local (trên máy) "
                "theo tên file hoặc nội dung bên trong. "
                "Dùng khi người dùng hỏi về tài liệu local, file trên máy, hoặc tệp vừa import."
                " Kết quả chỉ là đoạn xem trước, không phải toàn trang. Khi cần tên chính, "
                "bảng hoặc chi tiết của trang cụ thể, đọc trang bằng local_source_read."
            ),
            input_model=LocalSearchInput,
            output_model=LocalOutput,
            handler=search_local,
            required_permissions={RAG_READ},
            max_attempts=1,
        ),
        ToolDefinition(
            name="local_source_read",
            description=(
                "Đọc nội dung chi tiết của tài liệu local theo source_id hoặc tên tệp. "
                "Trả về văn bản và trích dẫn (citation) có nguồn dẫn tới tài liệu local."
                " Với PDF, người dùng chỉ định trang nào thì truyền page_number đúng trang "
                "đó; query không thay thế việc đọc trang cụ thể. Đọc tiếp next_offset nếu "
                "trang còn nội dung. Phân biệt tiêu đề chính với tên mục nội dung."
            ),
            input_model=LocalReadInput,
            output_model=LocalOutput,
            handler=read_local,
            required_permissions={RAG_READ},
            max_attempts=1,
        ),
    ]
