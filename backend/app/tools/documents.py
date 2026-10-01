"""Preview → explicit API approval → one Google write attempt → read-back check."""

import asyncio
import json
from typing import Literal

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.auth.google_oauth import refresh_and_store_if_needed
from app.auth.permissions import DRIVE_WRITE
from app.services.document_creator import (
    DocumentCreator,
    DocumentPatchSpec,
    DocumentSpec,
    document_tab,
)
from app.services.operations import OperationStore
from app.services.relational_operations import operation_store_for
from app.tools.contracts import OperationReference, ToolContext, ToolDefinition, ToolError
from app.tools.google_errors import workspace_http_error

DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"


class DocumentPrepare(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(pattern=r"^[A-Za-z0-9_-]{8,100}$")
    action: Literal["create", "edit"]
    document: DocumentSpec | None = None
    patch: DocumentPatchSpec | None = None
    edit: "DocumentEditIntent | None" = None

    @model_validator(mode="after")
    def matching_spec(self):
        if self.action == "create" and (
            self.document is None or self.patch is not None or self.edit is not None
        ):
            raise ValueError("Create requires only a document spec")
        if self.action == "edit" and (
            self.document is not None or (self.patch is None) == (self.edit is None)
        ):
            raise ValueError("Edit requires exactly one patch or edit intent")
        return self


class DocumentEditIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,200}$")
    tab_id: str | None = Field(default=None, max_length=200)
    old_text: str = Field(min_length=1, max_length=30000)
    new_text: str = Field(max_length=30000)


class DocumentApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    approved_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class DocumentOperationResult(BaseModel):
    data: dict


def operation_store(context: ToolContext) -> OperationStore:
    return operation_store_for(context.settings)


async def docs_prepare(payload: DocumentPrepare, context: ToolContext):
    # Preparing a creation has no Google side effects. Edits verify the preview
    # against the selected current revision before allowing approval.
    normalized = payload
    if payload.patch or payload.edit:
        credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)

        def preview():
            with build("docs", "v1", credentials=credentials, cache_discovery=False) as service:
                creator = DocumentCreator(service)
                patch = payload.patch
                if payload.edit:
                    actual = creator.read(payload.edit.document_id)
                    tab_id, _ = document_tab(actual, payload.edit.tab_id)
                    patch = DocumentPatchSpec(
                        document_id=payload.edit.document_id,
                        tab_id=tab_id,
                        revision_id=actual["revisionId"],
                        old_text=payload.edit.old_text,
                        new_text=payload.edit.new_text,
                    )
                creator.preview_patch(patch)
                return patch

        patch = await asyncio.to_thread(preview)
        normalized = payload.model_copy(update={"patch": patch, "edit": None})
    row = await asyncio.to_thread(
        operation_store(context).prepare,
        context.user.id,
        payload.request_key,
        "docs_" + payload.action,
        # ``edit`` is only a convenient user intent.  Persist the immutable,
        # revision-bound patch so the approval digest never covers a second
        # representation of the same write.
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


async def docs_execute(payload: DocumentApproval, context: ToolContext):
    store = operation_store(context)
    row = await asyncio.to_thread(store.get, context.user.id, payload.operation_id)
    if row["capability"] not in {"docs_create", "docs_edit"}:
        raise ToolError("Không phải thao tác Google Docs.", code="invalid_operation")
    spec = DocumentPrepare.model_validate_json(row["spec"])
    # Refresh/auth failures before claiming have no write side effects.
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)
    await asyncio.to_thread(store.claim, context.user.id, row["id"], payload.approved_digest)

    def execute():
        try:
            with build("docs", "v1", credentials=credentials, cache_discovery=False) as service:
                creator = DocumentCreator(service)
                if spec.action == "create":
                    result = creator.create(
                        spec.document,
                        lambda resource_id: store.checkpoint(
                            context.user.id, row["id"], resource_id
                        ),
                    )
                else:
                    store.checkpoint(context.user.id, row["id"], spec.patch.document_id)
                    result = creator.apply_patch(spec.patch)
            store.finish(context.user.id, row["id"], result)
            return DocumentOperationResult(data={"operation_id": row["id"], **result})
        except Exception as exc:
            error = (
                exc
                if isinstance(exc, ToolError)
                else workspace_http_error(exc, "Google Docs")
                if isinstance(exc, HttpError)
                else ToolError(
                    "Google Docs chưa xác minh hoàn tất. Kiểm tra trạng thái trước khi thử lại.",
                    code="google_execution_uncertain",
                )
            )
            store.uncertain(context.user.id, row["id"], error.code)
            raise error from None

    return await asyncio.to_thread(execute)


async def docs_reconcile(operation_id: str, context: ToolContext):
    """Read back an uncertain Docs write without sending it again."""

    store = operation_store(context)
    row = await asyncio.to_thread(store.get, context.user.id, operation_id)
    if row["state"] != "uncertain" or row["capability"] not in {"docs_create", "docs_edit"}:
        raise ToolError("Thao tác Docs không thể đối soát.", code="invalid_operation")
    if not row["resource_id"]:
        raise ToolError("Thao tác chưa có Document ID để đọc lại.", code="reconcile_unavailable")
    spec = DocumentPrepare.model_validate_json(row["spec"])
    credentials = await refresh_and_store_if_needed(context.user, context.db, context.settings)

    def reconcile():
        with build("docs", "v1", credentials=credentials, cache_discovery=False) as service:
            creator = DocumentCreator(service)
            if spec.action == "create":
                creator.verify_created(row["resource_id"], spec.document)
            else:
                creator.verify_patch_applied(spec.patch)
        result = {
            "document_id": row["resource_id"],
            "verified": True,
            "reconciled": True,
            "url": f"https://docs.google.com/document/d/{row['resource_id']}/edit",
        }
        store.finish_reconciliation(context.user.id, operation_id, result)
        return DocumentOperationResult(data={"operation_id": operation_id, **result})

    return await asyncio.to_thread(reconcile)


async def docs_reconcile_tool(payload: OperationReference, context: ToolContext):
    return await docs_reconcile(payload.operation_id, context)


def document_tool_definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="docs_prepare",
            description=(
                "Xem trước bản tạo/sửa Google Docs để người dùng kiểm tra và duyệt."
            ),
            input_model=DocumentPrepare,
            output_model=DocumentOperationResult,
            handler=docs_prepare,
            required_permissions={DRIVE_WRITE},
            required_oauth_scopes={DRIVE_FILE_SCOPE},
            max_attempts=1,
            timeout_seconds=90,
            requires_user_action=True,
        ),
        ToolDefinition(
            name="docs_execute",
            description="Thực hiện đúng bản Google Docs người dùng vừa duyệt trên giao diện.",
            input_model=DocumentApproval,
            output_model=DocumentOperationResult,
            handler=docs_execute,
            external_write=True,
            required_permissions={DRIVE_WRITE},
            required_oauth_scopes={DRIVE_FILE_SCOPE},
            max_attempts=1,
            timeout_seconds=90,
            requires_user_action=True,
        ),
        ToolDefinition(
            name="docs_reconcile",
            description="Đọc lại một thao tác Docs chưa xác định mà không ghi lần nữa.",
            input_model=OperationReference,
            output_model=DocumentOperationResult,
            handler=docs_reconcile_tool,
            required_permissions={DRIVE_WRITE},
            required_oauth_scopes={DRIVE_FILE_SCOPE},
            max_attempts=1,
            timeout_seconds=60,
            requires_user_action=True,
        ),
    ]
