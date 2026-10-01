"""User-reviewed Sheets creation through the same durable write ledger as Docs."""

import asyncio
import json
import logging
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
    verify_spreadsheet,
)
from app.tools.contracts import OperationReference, ToolContext, ToolDefinition, ToolError
from app.tools.documents import (
    DRIVE_FILE_SCOPE,
    DocumentApproval,
    DocumentOperationResult,
    operation_store,
)
from app.tools.google_errors import workspace_http_error

logger = logging.getLogger(__name__)


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
                    else (
                        store.checkpoint(
                            context.user.id, row["id"], spec.patch.spreadsheet_id
                        )
                        or creator.apply_patch(spec.patch)
                    )
                )
            store.finish(context.user.id, row["id"], result)
            return DocumentOperationResult(data={"operation_id": row["id"], **result})
        except Exception as exc:
            if not isinstance(exc, (ToolError, HttpError)):
                # Tracebacks expose the failing integration line without logging
                # the spreadsheet body, OAuth credential or provider headers.
                logger.warning(
                    "Unexpected Google Sheets failure; type=%s",
                    type(exc).__name__,
                    exc_info=True,
                )
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


async def sheets_reconcile(operation_id: str, context: ToolContext):
    """Read back a checkpointed file; never repeat the external write."""

    store = operation_store(context)
    row = await asyncio.to_thread(store.get, context.user.id, operation_id)
    if row["capability"] not in {"sheets_create", "sheets_edit"} or row["state"] != "uncertain":
        raise ToolError(
            "Chỉ đối soát được thao tác Sheets ở trạng thái chưa chắc chắn.",
            code="operation_state_conflict",
        )
    if not row["resource_id"]:
        raise ToolError(
            "Google chưa trả về mã file; không thể đối soát an toàn.",
            code="reconciliation_unavailable",
        )
    spec = SpreadsheetPrepare.model_validate_json(row["spec"])
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)

    def reconcile():
        with build("sheets", "v4", credentials=credentials, cache_discovery=False) as service:
            creator = SpreadsheetCreator(service)
            if spec.action == "create":
                actual = creator.spreadsheets.get(
                    spreadsheetId=row["resource_id"], includeGridData=True
                ).execute(num_retries=0)
                verify_spreadsheet(spec.spreadsheet, actual)
            else:
                creator.verify_patch_applied(spec.patch)
        result = {
            "spreadsheet_id": row["resource_id"],
            "verified": True,
            "reconciled": True,
            "url": f"https://docs.google.com/spreadsheets/d/{row['resource_id']}/edit",
        }
        if spec.action == "edit":
            result["ranges_updated"] = len(spec.patch.patches)
        store.finish_reconciliation(context.user.id, operation_id, result)
        return DocumentOperationResult(data={"operation_id": operation_id, **result})

    return await asyncio.to_thread(reconcile)


async def sheets_reconcile_tool(payload: OperationReference, context: ToolContext):
    return await sheets_reconcile(payload.operation_id, context)


def spreadsheet_tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="sheets_prepare",
            description=(
                "Xem trước bảng tính, công thức và biểu đồ để người dùng kiểm tra, duyệt."
            ),
            input_model=SpreadsheetPrepare,
            output_model=DocumentOperationResult,
            handler=sheets_prepare,
            required_permissions={DRIVE_WRITE},
            required_oauth_scopes={DRIVE_FILE_SCOPE},
            max_attempts=1,
            timeout_seconds=90,
            requires_user_action=True,
        ),
        ToolDefinition(
            name="sheets_execute",
            description=(
                "Tạo bảng tính đã được người dùng duyệt trên giao diện rồi đọc lại kiểm tra."
            ),
            input_model=DocumentApproval,
            output_model=DocumentOperationResult,
            handler=sheets_execute,
            external_write=True,
            required_permissions={DRIVE_WRITE},
            required_oauth_scopes={DRIVE_FILE_SCOPE},
            max_attempts=1,
            timeout_seconds=90,
            requires_user_action=True,
        ),
        ToolDefinition(
            name="sheets_reconcile",
            description="Đọc lại một thao tác Sheets chưa xác định mà không ghi lần nữa.",
            input_model=OperationReference,
            output_model=DocumentOperationResult,
            handler=sheets_reconcile_tool,
            required_permissions={DRIVE_WRITE},
            required_oauth_scopes={DRIVE_FILE_SCOPE},
            max_attempts=1,
            timeout_seconds=60,
            requires_user_action=True,
        ),
    ]
