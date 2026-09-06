"""DTO công khai của REST API.

Không trả thẳng SQLAlchemy model để tránh vô tình làm lộ credential đã mã hóa hoặc
trường nội bộ khi mô hình dữ liệu thay đổi.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserResponse(ApiModel):
    id: str
    email: str
    display_name: str
    avatar_url: str | None
    role: str
    scopes: list[str] = Field(default_factory=list)


class AuthStatusResponse(BaseModel):
    authenticated: bool
    oauth_configured: bool
    gemini_configured: bool
    demo_login_enabled: bool = False
    user: UserResponse | None = None


class DriveFileResponse(BaseModel):
    id: str
    name: str
    mime_type: str
    modified_time: str | None = None
    size: str | None = None
    web_view_link: str | None = None
    owners: list[str] = Field(default_factory=list)
    indexed: bool = False


class DriveFileListResponse(BaseModel):
    files: list[DriveFileResponse]
    next_page_token: str | None = None


class FileContentResponse(BaseModel):
    file: DriveFileResponse
    text: str
    truncated: bool = False


class IndexFileResponse(BaseModel):
    file_id: str
    file_name: str
    chunks: int
    skipped: bool
    message: str


class Citation(BaseModel):
    file_id: str
    file_name: str
    chunk_index: int
    snippet: str
    web_view_link: str | None = None
    score: float


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    file_ids: list[str] = Field(default_factory=list, max_length=50)
    limit: int = Field(default=6, ge=1, le=20)


class RagSearchResponse(BaseModel):
    query: str
    citations: list[Citation]


class MemoryCreateRequest(BaseModel):
    kind: Literal["fact", "preference", "context", "episodic", "procedural", "summary"]
    content: str = Field(min_length=2, max_length=8000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(default=1.0, ge=0, le=1)


class MemoryUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=2, max_length=8000)
    tags: list[str] | None = Field(default=None, max_length=20)
    confidence: float | None = Field(default=None, ge=0, le=1)
    is_archived: bool | None = None


class MemoryResponse(ApiModel):
    id: str
    kind: str
    content: str
    tags: list[str] = Field(default_factory=list)
    confidence: float
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)


class SessionResponse(ApiModel):
    id: str
    title: str
    summary: str | None
    created_at: datetime
    updated_at: datetime


class MessageResponse(ApiModel):
    id: str
    role: str
    content: str
    citations: list[Citation] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class AuditResponse(ApiModel):
    id: str
    request_id: str
    user_email: str | None
    role: str | None
    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    status: str
    latency_ms: int | None
    error_type: str | None
    error_message: str | None
    created_at: datetime


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    gemini_configured: bool
    google_oauth_configured: bool
    vector_store: str
    gemini_chat_model: str
    gemini_fallback_model: str
    gemini_embedding_model: str
    embedding_dimensions: int
