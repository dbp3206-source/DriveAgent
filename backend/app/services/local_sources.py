"""Import văn bản local có giới hạn. Notebook chỉ đọc source, không chạy cell."""

import csv
import hashlib
import io
import json
from pathlib import PurePath
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.permissions import RAG_READ
from app.db.models import LocalSource
from app.tools.contracts import ToolContext, ToolDefinition, ToolError

MAX_BYTES = 2_000_000
MAX_TEXT = 100_000


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
    source_id: UUID
    offset: int = Field(default=0, ge=0, le=100000)


class LocalOutput(BaseModel):
    data: dict


async def search_local(payload: LocalSearchInput, context: ToolContext) -> LocalOutput:
    query = select(LocalSource).where(LocalSource.user_id == context.user.id)
    if payload.query.strip():
        # Literal contains escapes wildcard characters; this is NOT semantic/vector retrieval.
        query = query.where(LocalSource.name.contains(payload.query.strip(), autoescape=True))
    rows = await context.db.scalars(query.order_by(LocalSource.created_at.desc()).limit(50))
    return LocalOutput(
        data={
            "sources": [
                {"id": row.id, "name": row.name, "characters": len(row.content)} for row in rows
            ],
            "search_type": "literal_filename",
            "limit": 50,
        }
    )


async def read_local(payload: LocalReadInput, context: ToolContext) -> LocalOutput:
    row = await context.db.scalar(
        select(LocalSource).where(
            LocalSource.id == str(payload.source_id), LocalSource.user_id == context.user.id
        )
    )
    if row is None:
        raise ToolError("Không tìm thấy tài liệu local của bạn.", code="source_not_found")
    end = payload.offset + 12000
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
                    "snippet": row.content[payload.offset : payload.offset + 500],
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
            description="Liệt kê/tìm tên tài liệu đã import local, không tìm Drive.",
            input_model=LocalSearchInput,
            output_model=LocalOutput,
            handler=search_local,
            required_permissions={RAG_READ},
            max_attempts=1,
        ),
        ToolDefinition(
            name="local_source_read",
            description=(
                "Đọc tài liệu local theo source_id và offset. Dùng next_offset để đọc tiếp nếu cần."
            ),
            input_model=LocalReadInput,
            output_model=LocalOutput,
            handler=read_local,
            required_permissions={RAG_READ},
            max_attempts=1,
        ),
    ]
