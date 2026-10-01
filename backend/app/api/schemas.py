"""DTO công khai của REST API.

Không trả thẳng SQLAlchemy model để tránh vô tình làm lộ credential đã mã hóa hoặc
trường nội bộ khi mô hình dữ liệu thay đổi.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.agent.controls import ChatControls


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("*", when_used="always", check_fields=False)
    def serialize_legacy_utc(self, value: Any) -> Any:
        """SQLite drops timezone metadata; public API timestamps are always UTC."""

        if isinstance(value, datetime):
            aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
            return aware.isoformat().replace("+00:00", "Z")
        return value


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
    index_status: Literal["not_indexed", "fresh", "stale"] = "not_indexed"


class DriveFileListResponse(BaseModel):
    files: list[DriveFileResponse]
    next_page_token: str | None = None


class FileContentResponse(BaseModel):
    file: DriveFileResponse
    text: str
    truncated: bool = False
    assets: list[str] = Field(default_factory=list)


class IndexFileResponse(BaseModel):
    file_id: str
    file_name: str
    chunks: int
    skipped: bool
    message: str


class UnindexFileResponse(BaseModel):
    file_id: str
    file_name: str
    chunks_removed: int
    message: str


class Citation(BaseModel):
    file_id: str
    file_name: str
    chunk_index: int
    page_number: int | None = None
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

    @field_validator("content", "tags", "confidence", "is_archived", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: Any) -> Any:
        # PATCH cho phép bỏ qua trường, không cho phép xóa giá trị bằng null.
        # Validator không chạy với default omitted nên partial update vẫn hợp lệ.
        if value is None:
            raise ValueError("Không chấp nhận null; hãy bỏ qua trường không muốn cập nhật.")
        return value


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
    model: str | None = None
    controls: ChatControls = Field(default_factory=ChatControls)


class ChatResponse(BaseModel):
    proposals: list[dict[str, Any]] = Field(default_factory=list)
    session_id: str
    message_id: str
    answer: str
    status: Literal["completed", "incomplete"] = "completed"
    citations: list[Citation] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)


class SessionResponse(ApiModel):
    id: str
    title: str
    summary: str | None
    created_at: datetime
    updated_at: datetime


class SessionPage(ApiModel):
    items: list[SessionResponse]
    next_cursor: str | None = None


class SessionUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)


class MessageResponse(ApiModel):
    proposals: list[dict[str, Any]] = Field(default_factory=list)
    id: str
    role: str
    content: str
    citations: list[Citation] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)
    status: Literal["running", "completed", "incomplete", "failed", "cancelled"] = "completed"
    created_at: datetime


class MessagePage(ApiModel):
    items: list[MessageResponse]
    next_cursor: str | None = None


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


class AuditPage(ApiModel):
    items: list[AuditResponse]
    next_cursor: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    object_storage: bool = True
    gemini_configured: bool
    gemini_connectivity: Literal["not_probed"] = "not_probed"
    google_oauth_configured: bool
    google_workspace_connectivity: Literal["not_probed"] = "not_probed"
    vector_store: str
    gemini_chat_model: str
    gemini_fallback_model: str
    gemini_embedding_model: str
    embedding_dimensions: int
    runtime_started_at: str | None = None
    runtime_pid: int | None = None
