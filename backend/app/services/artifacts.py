"""Local artifacts: explicit save, tenant filter, idempotency and optimistic revision."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.auth.permissions import MEMORY_READ, MEMORY_WRITE
from app.db.models import SavedArtifact
from app.tools.contracts import ToolContext, ToolDefinition, ToolError


class ArtifactWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=100_000)
    kind: Literal["note", "checklist", "quiz", "plan", "report"] = "note"
    creation_key: UUID
    artifact_id: UUID | None = None
    expected_revision: int = Field(default=1, ge=1)
    is_archived: bool = False

    @field_validator("title", "content")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        # Giữ xuống dòng/indent của Markdown; chỉ title được trim khi ghi database.
        if not value.strip():
            raise ValueError("Tiêu đề và nội dung không được chỉ chứa khoảng trắng.")
        return value


class ArtifactView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    content: str
    kind: str
    revision: int
    is_archived: bool


class ArtifactListInput(BaseModel):
    include_archived: bool = False


class ArtifactListOutput(BaseModel):
    items: list[ArtifactView]


async def save_artifact(payload: ArtifactWrite, context: ToolContext) -> ArtifactView:
    if payload.artifact_id:
        result = await context.db.execute(
            update(SavedArtifact)
            .where(
                SavedArtifact.id == str(payload.artifact_id),
                SavedArtifact.user_id == context.user.id,
                SavedArtifact.revision == payload.expected_revision,
            )
            .values(
                title=payload.title.strip(),
                content=payload.content,
                kind=payload.kind,
                is_archived=payload.is_archived,
                revision=SavedArtifact.revision + 1,
            )
        )
        if result.rowcount != 1:
            raise ToolError(
                "Bản lưu đã đổi hoặc không tồn tại. Hãy tải lại trước khi sửa.",
                code="revision_conflict",
            )
        row = await context.db.scalar(
            select(SavedArtifact)
            .where(
                SavedArtifact.id == str(payload.artifact_id),
                SavedArtifact.user_id == context.user.id,
            )
            .execution_options(populate_existing=True)
        )
    else:
        row = await context.db.scalar(
            select(SavedArtifact).where(
                SavedArtifact.user_id == context.user.id,
                SavedArtifact.creation_key == str(payload.creation_key),
            )
        )
        if row is not None:
            if (row.title, row.content, row.kind) != (
                payload.title.strip(),
                payload.content,
                payload.kind,
            ):
                raise ToolError("Mã lưu đã dùng cho nội dung khác.", code="idempotency_conflict")
        else:
            row = SavedArtifact(
                user_id=context.user.id,
                creation_key=str(payload.creation_key),
                title=payload.title.strip(),
                content=payload.content,
                kind=payload.kind,
            )
            try:
                async with context.db.begin_nested():
                    context.db.add(row)
                    await context.db.flush()
            except IntegrityError:
                # Hai tab có thể retry cùng khóa đồng thời. Savepoint giữ audit transaction.
                row = await context.db.scalar(
                    select(SavedArtifact).where(
                        SavedArtifact.user_id == context.user.id,
                        SavedArtifact.creation_key == str(payload.creation_key),
                    )
                )
                if row is None or (row.title, row.content, row.kind) != (
                    payload.title.strip(),
                    payload.content,
                    payload.kind,
                ):
                    raise ToolError(
                        "Mã lưu đã dùng cho nội dung khác.", code="idempotency_conflict"
                    ) from None
    return ArtifactView.model_validate(row)


async def list_artifacts(payload: ArtifactListInput, context: ToolContext) -> ArtifactListOutput:
    query = select(SavedArtifact).where(SavedArtifact.user_id == context.user.id)
    if not payload.include_archived:
        query = query.where(SavedArtifact.is_archived.is_(False))
    rows = await context.db.scalars(query.order_by(SavedArtifact.updated_at.desc()).limit(200))
    return ArtifactListOutput(items=[ArtifactView.model_validate(row) for row in rows])


def artifact_tool_definitions() -> list[ToolDefinition]:
    # Chỉ list được cấp cho model. Save được UI/API gọi sau hành động chủ động của user.
    return [
        ToolDefinition(
            name="artifact_list",
            description="Đọc các ghi chú/kế hoạch đã lưu riêng.",
            input_model=ArtifactListInput,
            output_model=ArtifactListOutput,
            handler=list_artifacts,
            required_permissions={MEMORY_READ},
            max_attempts=1,
        ),
        ToolDefinition(
            name="artifact_save",
            requires_user_action=True,
            description="Lưu bản kết quả do người dùng duyệt.",
            input_model=ArtifactWrite,
            output_model=ArtifactView,
            handler=save_artifact,
            required_permissions={MEMORY_WRITE},
            max_attempts=1,
        ),
    ]
