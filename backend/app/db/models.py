"""Mô hình dữ liệu local-first, nhưng mọi dữ liệu riêng đều gắn ``user_id``.

Nguyên tắc multi-user này được áp dụng ngay cả khi chạy trên một laptop. Vì vậy dự án
có thể chuyển lên server sau này mà không phải tách lại Drive, memory và audit của người dùng.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class SavedArtifact(Base):
    """Kết quả do người dùng chủ động lưu; revision chống ghi đè chỉnh sửa."""

    __tablename__ = "saved_artifacts"
    __table_args__ = (Index("ux_artifact_request", "user_id", "creation_key", unique=True),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    creation_key: Mapped[str] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(240))
    kind: Mapped[str] = mapped_column(String(24), default="note")
    content: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class PdfIngestionJob(Base):
    """Owner-scoped page checkpoints; SQL store works on SQLite/PostgreSQL."""

    __tablename__ = "pdf_ingestion_jobs"
    __table_args__ = (Index("ux_pdf_job_owner_digest", "user_id", "content_hash", unique=True),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(240))
    content_hash: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(24), default="inspect")
    pages: Mapped[int] = mapped_column(Integer, default=0)
    checkpoint_json: Mapped[str] = mapped_column(Text, default="[]")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[float | None] = mapped_column(Float)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    source_id: Mapped[str | None] = mapped_column(String(36))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ScheduledJob(Base):
    """Durable, idempotent owner job created by the authenticated cron endpoint."""

    __tablename__ = "scheduled_jobs"
    __table_args__ = (
        Index("ux_scheduled_job_owner_slot", "user_id", "kind", "dedupe_key", unique=True),
        Index("ix_scheduled_job_claim", "status", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    dedupe_key: Mapped[str] = mapped_column(String(96))
    status: Mapped[str] = mapped_column(String(24), default="queued")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    checkpoint_json: Mapped[str] = mapped_column(Text, default="{}")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[float | None] = mapped_column(Float)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class LocalSource(Base):
    __tablename__ = "local_sources"
    __table_args__ = (Index("ux_local_source_hash", "user_id", "content_hash", unique=True),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(240))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class MemoryKind(StrEnum):
    FACT = "fact"
    PREFERENCE = "preference"
    CONTEXT = "context"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"
    SUMMARY = "summary"


class AuditStatus(StrEnum):
    STARTED = "started"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    DENIED = "denied"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(32), default=UserRole.VIEWER.value)
    oauth_scopes_json: Mapped[str] = mapped_column(Text, default="[]")
    encrypted_google_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    sessions: Mapped[list[ChatSession]] = relationship(back_populates="user")


class ProviderCredential(Base):
    """Encrypted, owner-scoped provider credential metadata.

    ``encrypted_secret`` is never serialized by an API schema.  ``fingerprint``
    is a one-way identifier used for duplicate detection and quota namespaces.
    """

    __tablename__ = "provider_credentials"
    __table_args__ = (
        Index("ux_provider_credential_fingerprint", "user_id", "fingerprint", unique=True),
        Index("ix_provider_credential_active", "user_id", "provider", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="gemini")
    display_name: Mapped[str] = mapped_column(String(80))
    project_alias: Mapped[str] = mapped_column(String(120), default="")
    fingerprint: Mapped[str] = mapped_column(String(24))
    encrypted_secret: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="ready")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    failover_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(240), default="Cuộc trò chuyện mới")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    user: Mapped[User] = relationship(back_populates="sessions")
    messages: Mapped[list[Message]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_session_created", "session_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    citations_json: Mapped[str] = mapped_column(Text, default="[]")
    trace_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(16), default="completed", index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class ResponseFeedback(Base):
    """A user's explicit quality signal for one assistant response."""

    __tablename__ = "response_feedback"
    __table_args__ = (Index("ux_feedback_user_message", "user_id", "message_id", unique=True),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    rating: Mapped[int] = mapped_column(Integer)
    reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CreationProposalRecord(Base):
    """Separate table keeps existing message history intact without an ALTER migration."""

    __tablename__ = "creation_proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    spec_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DriveFileIndex(Base):
    __tablename__ = "drive_file_index"
    __table_args__ = (Index("ux_drive_file_per_user", "user_id", "drive_file_id", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    drive_file_id: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(200))
    web_view_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    modified_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_chunks_user_file", "user_id", "drive_file_id"),
        Index("ux_chunk_key", "user_id", "drive_file_id", "chunk_index", unique=True),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    drive_file_id: Mapped[str] = mapped_column(String(200), index=True)
    file_name: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(200))
    web_view_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    token_terms_json: Mapped[str] = mapped_column(Text, default="[]")
    embedding_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class LongTermMemory(Base):
    __tablename__ = "long_term_memories"
    __table_args__ = (Index("ix_memory_user_kind", "user_id", "kind"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    normalized_hash: Mapped[str] = mapped_column(String(64), index=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    source_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    embedding_json: Mapped[str] = mapped_column(Text, default="[]")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CompanyProfile(Base):
    """User-scoped company facts with explicit provenance and freshness."""

    __tablename__ = "company_profiles"
    __table_args__ = (
        Index("ux_company_user_domain", "user_id", "domain", unique=True),
        Index("ix_company_user_name", "user_id", "normalized_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(240))
    normalized_name: Mapped[str] = mapped_column(String(240), index=True)
    domain: Mapped[str] = mapped_column(String(253))
    industry: Mapped[str | None] = mapped_column(String(240), nullable=True)
    products_json: Mapped[str] = mapped_column(Text, default="[]")
    contacts_json: Mapped[str] = mapped_column(Text, default="[]")
    notes: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(Text)
    source_kind: Mapped[str] = mapped_column(String(32), default="official")
    last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_user_created", "user_id", "created_at"),
        Index("ix_audit_request_id", "request_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(120), index=True)
    arguments_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(32), default=AuditStatus.STARTED.value)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GraphCheckpoint(Base):
    """Snapshot dễ đọc cho UI; LangGraph vẫn có checkpoint store riêng."""

    __tablename__ = "graph_checkpoints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    thread_id: Mapped[str] = mapped_column(String(100), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    state_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
