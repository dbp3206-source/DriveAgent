"""Preview/approval boundary for Google Slides creation and targeted edits."""

import asyncio
import json
from typing import Literal

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.auth.google_oauth import refresh_and_store_if_needed
from app.auth.permissions import DRIVE_WRITE
from app.services.slide_creator import (
    PresentationEditIntent,
    PresentationPatchSpec,
    PresentationSpec,
    SlideCreator,
)
from app.services.visuals import VisualSpec, VisualStore
from app.tools.contracts import ToolContext, ToolDefinition, ToolError
from app.tools.documents import (
    DRIVE_FILE_SCOPE,
    DocumentApproval,
    DocumentOperationResult,
    operation_store,
)
from app.tools.google_errors import workspace_http_error


class SlidesPrepare(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(pattern=r"^[A-Za-z0-9_-]{8,100}$")
    action: Literal["create", "edit"]
    presentation: PresentationSpec | None = None
    patch: PresentationPatchSpec | None = None
    edit: PresentationEditIntent | None = None

    @model_validator(mode="after")
    def matching(self):
        if self.action == "create" and (
            self.presentation is None or self.patch is not None or self.edit is not None
        ):
            raise ValueError("Create requires only a presentation")
        if self.action == "edit" and (
            self.presentation is not None or (self.patch is None) == (self.edit is None)
        ):
            raise ValueError("Edit requires exactly one patch or edit intent")
        return self


def resolve_visuals(payload: SlidesPrepare, context: ToolContext) -> SlidesPrepare:
    """Resolve immutable, user-owned visual IDs without exposing filesystem paths."""

    store = VisualStore(context.settings.data_dir)

    def resolve(visual_id: str | None, visual: VisualSpec | None) -> VisualSpec | None:
        if visual is not None or visual_id is None:
            return visual
        return VisualSpec.model_validate_json(store.get(context.user.id, visual_id)["spec"])

    if payload.presentation:
        slides = [
            slide.model_copy(update={"visual": resolve(slide.visual_id, slide.visual)})
            for slide in payload.presentation.slides
        ]
        return payload.model_copy(
            update={"presentation": payload.presentation.model_copy(update={"slides": slides})}
        )
    if payload.edit:
        add_slides = [
            slide.model_copy(update={"visual": resolve(slide.visual_id, slide.visual)})
            for slide in payload.edit.add_slides
        ]
        return payload.model_copy(
            update={"edit": payload.edit.model_copy(update={"add_slides": add_slides})}
        )
    assert payload.patch is not None
    add_slides = [
        slide.model_copy(update={"visual": resolve(slide.visual_id, slide.visual)})
        for slide in payload.patch.add_slides
    ]
    visual_updates = [
        update.model_copy(update={"visual": resolve(update.visual_id, update.visual)})
        for update in payload.patch.visual_updates
    ]
    return payload.model_copy(
        update={
            "patch": payload.patch.model_copy(
                update={"add_slides": add_slides, "visual_updates": visual_updates}
            )
        }
    )


async def slides_prepare(payload: SlidesPrepare, context: ToolContext):
    resolved = await asyncio.to_thread(resolve_visuals, payload, context)
    if payload.patch or payload.edit:
        credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)

        def preview():
            with build("slides", "v1", credentials=credentials, cache_discovery=False) as service:
                creator = SlideCreator(service)
                patch = resolved.patch
                if resolved.edit:
                    actual = creator.read(resolved.edit.presentation_id)
                    patch = PresentationPatchSpec(
                        presentation_id=resolved.edit.presentation_id,
                        revision_id=actual["revisionId"],
                        replacements=resolved.edit.replacements,
                        add_slides=resolved.edit.add_slides,
                        delete_slide_ids=resolved.edit.delete_slide_ids,
                    )
                creator.preview_patch(patch)
                return patch

        patch = await asyncio.to_thread(preview)
        resolved = resolved.model_copy(update={"patch": patch, "edit": None})
    row = await asyncio.to_thread(
        operation_store(context).prepare,
        context.user.id,
        payload.request_key,
        "slides_" + payload.action,
        resolved.model_dump(mode="json", exclude={"edit"}),
    )
    return DocumentOperationResult(
        data={
            "operation_id": row["id"],
            "state": row["state"],
            "digest": row["digest"],
            "preview": json.loads(row["spec"]),
            "expires_after_seconds": 1800,
        }
    )


async def slides_execute(payload: DocumentApproval, context: ToolContext):
    store = operation_store(context)
    row = await asyncio.to_thread(store.get, context.user.id, payload.operation_id)
    if row["capability"] not in {"slides_create", "slides_edit"}:
        raise ToolError("Không phải thao tác Google Slides.", code="invalid_operation")
    spec = SlidesPrepare.model_validate_json(row["spec"])
    resolved = await asyncio.to_thread(resolve_visuals, spec, context)
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)
    await asyncio.to_thread(store.claim, context.user.id, row["id"], payload.approved_digest)

    def execute():
        try:
            with build("slides", "v1", credentials=credentials, cache_discovery=False) as service:
                creator = SlideCreator(service)
                result = (
                    creator.create(
                        resolved.presentation,
                        lambda resource_id: store.checkpoint(
                            context.user.id, row["id"], resource_id
                        ),
                    )
                    if spec.action == "create"
                    else creator.apply_patch(resolved.patch)
                )
            store.finish(context.user.id, row["id"], result)
            return DocumentOperationResult(data={"operation_id": row["id"], **result})
        except Exception as exc:
            error = (
                exc
                if isinstance(exc, ToolError)
                else workspace_http_error(exc, "Google Slides")
                if isinstance(exc, HttpError)
                else ToolError(
                    "Google Slides chưa xác minh hoàn tất. Kiểm tra trạng thái trước khi thử lại.",
                    code="google_execution_uncertain",
                )
            )
            store.uncertain(context.user.id, row["id"], error.code)
            raise error from None

    return await asyncio.to_thread(execute)


def slide_tool_definitions() -> list[ToolDefinition]:
    pairs = [
        (
            "slides_prepare",
            "Xem trước bản tạo/sửa Google Slides; chưa ghi dữ liệu.",
            SlidesPrepare,
            slides_prepare,
        ),
        (
            "slides_execute",
            "Thực hiện đúng bản Google Slides người dùng đã duyệt.",
            DocumentApproval,
            slides_execute,
        ),
    ]
    return [
        ToolDefinition(
            name=n,
            description=d,
            input_model=m,
            output_model=DocumentOperationResult,
            handler=h,
            required_permissions={DRIVE_WRITE},
            required_oauth_scopes={DRIVE_FILE_SCOPE},
            max_attempts=1,
            timeout_seconds=120,
            requires_user_action=True,
        )
        for n, d, m, h in pairs
    ]
