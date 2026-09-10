"""User-reviewed Sheets creation through the same durable write ledger as Docs."""

import asyncio
import json
from typing import Literal

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.auth.google_oauth import refresh_and_store_if_needed
from app.auth.permissions import DRIVE_WRITE
from app.services.sheet_creator import (
    SpreadsheetCreator,
    SpreadsheetEditIntent,
    SpreadsheetPatchSpec,
    SpreadsheetSpec,
)
from app.tools.contracts import ToolContext, ToolDefinition, ToolError
from app.tools.documents import (
    DRIVE_FILE_SCOPE,
    DocumentApproval,
    DocumentOperationResult,
    operation_store,
)
from app.tools.google_errors import workspace_http_error


class SpreadsheetPrepare(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(pattern=r"^[A-Za-z0-9_-]{8,100}$")
    action: Literal["create", "edit"] = "create"
    spreadsheet: SpreadsheetSpec | None = None
    patch: SpreadsheetPatchSpec | None = None
    edit: SpreadsheetEditIntent | None = None

    @model_validator(mode="after")
    def matching(self):
        if self.action == "create" and (
            self.spreadsheet is None or self.patch is not None or self.edit is not None
        ):
            raise ValueError("Create requires only a spreadsheet")
        if self.action == "edit" and (
            self.spreadsheet is not None or (self.patch is None) == (self.edit is None)
        ):
            raise ValueError("Edit requires exactly one patch or edit intent")
        return self


async def sheets_prepare(payload: SpreadsheetPrepare, context: ToolContext):
    normalized = payload
    if payload.patch or payload.edit:
        credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)

        def preview():
            with build("sheets", "v4", credentials=credentials, cache_discovery=False) as service:
                creator = SpreadsheetCreator(service)
                patch = payload.patch or creator.prepare_patch(payload.edit)
                creator.preview_patch(patch)
                return patch

        patch = await asyncio.to_thread(preview)
        normalized = payload.model_copy(update={"patch": patch, "edit": None})
    row = await asyncio.to_thread(
        operation_store(context).prepare,
        context.user.id,
        payload.request_key,
        "sheets_" + payload.action,
        normalized.model_dump(mode="json", exclude={"edit"}),
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


async def sheets_execute(payload: DocumentApproval, context: ToolContext):
    store = operation_store(context)
    row = await asyncio.to_thread(store.get, context.user.id, payload.operation_id)
    if row["capability"] not in {"sheets_create", "sheets_edit"}:
        raise ToolError("Không phải thao tác Google Sheets.", code="invalid_operation")
    spec = SpreadsheetPrepare.model_validate_json(row["spec"])
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)
    await asyncio.to_thread(store.claim, context.user.id, row["id"], payload.approved_digest)

    def execute():
        try:
            with build("sheets", "v4", credentials=credentials, cache_discovery=False) as service:
                creator = SpreadsheetCreator(service)
                result = (
                    creator.create(
                        spec.spreadsheet,
                        lambda resource_id: store.checkpoint(
                            context.user.id, row["id"], resource_id
                        ),
                    )
                    if spec.action == "create"
                    else creator.apply_patch(spec.patch)
                )
            store.finish(context.user.id, row["id"], result)
            return DocumentOperationResult(data={"operation_id": row["id"], **result})
        except Exception as exc:
            error = (
                exc
                if isinstance(exc, ToolError)
                else workspace_http_error(exc, "Google Sheets")
                if isinstance(exc, HttpError)
                else ToolError(
                    "Google Sheets chưa xác minh hoàn tất. Kiểm tra trạng thái trước khi thử lại.",
                    code="google_execution_uncertain",
                )
            )
            store.uncertain(context.user.id, row["id"], error.code)
            raise error from None

    return await asyncio.to_thread(execute)


def spreadsheet_tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name=name,
            description=description,
            input_model=model,
            output_model=DocumentOperationResult,
            handler=handler,
            required_permissions={DRIVE_WRITE},
            required_oauth_scopes={DRIVE_FILE_SCOPE},
            max_attempts=1,
            timeout_seconds=90,
            requires_user_action=True,
        )
        for name, description, model, handler in [
            (
                "sheets_prepare",
                "Xem trước bảng tính, công thức và biểu đồ; chưa tạo file.",
                SpreadsheetPrepare,
                sheets_prepare,
            ),
            (
                "sheets_execute",
                "Tạo đúng bảng tính người dùng đã duyệt và đọc lại kiểm tra.",
                DocumentApproval,
                sheets_execute,
            ),
        ]
    ]
