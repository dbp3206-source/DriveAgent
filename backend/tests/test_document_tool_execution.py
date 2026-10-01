from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.document_creator import DocumentBlock, DocumentSpec
from app.tools.contracts import ToolContext, ToolError
from app.tools.documents import (
    DocumentApproval,
    DocumentEditIntent,
    DocumentPrepare,
    docs_execute,
    docs_prepare,
    docs_reconcile,
)


def _context(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'document-tool.db'}"
    return ToolContext(
        request_id="req-docs",
        user=SimpleNamespace(id="user-docs"),
        db=AsyncMock(),
        settings=Settings(_env_file=None, database_url=database_url),
        source="test",
    )


def _spec() -> DocumentSpec:
    return DocumentSpec(
        title="Kế hoạch QA",
        theme="study",
        blocks=[DocumentBlock(text="Nội dung kiểm thử.")],
    )


@pytest.mark.asyncio
async def test_docs_prepare_persists_an_immutable_preview(tmp_path):
    context = _context(tmp_path)
    payload = DocumentPrepare(
        request_key="docs_prepare_1",
        action="create",
        document=_spec(),
    )
    first = await docs_prepare(payload, context)
    second = await docs_prepare(payload, context)

    assert first.data["state"] == "pending"
    assert first.data["operation_id"] == second.data["operation_id"]
    assert first.data["preview"]["document"]["title"] == "Kế hoạch QA"
    assert first.data["expires_after_seconds"] == 1800


@pytest.mark.asyncio
async def test_docs_prepare_edit_intent_reads_revision_and_persists_bound_patch(tmp_path):
    context = _context(tmp_path)
    payload = DocumentPrepare(
        request_key="docs_edit_prepare_1",
        action="edit",
        edit=DocumentEditIntent(document_id="doc-id", old_text="Before", new_text="After"),
    )
    creator = MagicMock()
    creator.read.return_value = {
        "revisionId": "revision-1",
        "tabs": [
            {
                "tabProperties": {"tabId": "tab-1"},
                "documentTab": {"body": {"content": []}},
            }
        ],
    }
    service = MagicMock()
    service.__enter__.return_value = service
    service.__exit__.return_value = False
    with (
        patch(
            "app.tools.documents.refresh_and_store_if_needed",
            AsyncMock(return_value=SimpleNamespace()),
        ),
        patch("app.tools.documents.build", return_value=service),
        patch("app.tools.documents.DocumentCreator", return_value=creator),
    ):
        result = await docs_prepare(payload, context)

    preview = result.data["preview"]
    assert "edit" not in preview
    assert preview["patch"]["revision_id"] == "revision-1"
    assert preview["patch"]["tab_id"] == "tab-1"
    creator.preview_patch.assert_called_once()


@pytest.mark.asyncio
async def test_docs_execute_claims_once_checkpoints_and_finishes(tmp_path):
    context = _context(tmp_path)
    operation_id = str(uuid4())
    prepared = DocumentPrepare(
        request_key="docs_execute_1", action="create", document=_spec()
    )
    row = {
        "id": operation_id,
        "capability": "docs_create",
        "spec": prepared.model_dump_json(),
    }
    store = MagicMock()
    store.get.return_value = row
    creator = MagicMock()
    creator.create.return_value = {
        "document_id": "doc-created",
        "verified": True,
        "url": "https://docs.google.com/document/d/doc-created/edit",
    }
    service = MagicMock()
    service.__enter__.return_value = service
    service.__exit__.return_value = False

    with (
        patch("app.tools.documents.operation_store", return_value=store),
        patch(
            "app.tools.documents.refresh_and_store_if_needed",
            AsyncMock(return_value=SimpleNamespace()),
        ),
        patch("app.tools.documents.build", return_value=service),
        patch("app.tools.documents.DocumentCreator", return_value=creator),
    ):
        result = await docs_execute(
            DocumentApproval(operation_id=operation_id, approved_digest="a" * 64), context
        )

    assert result.data["document_id"] == "doc-created"
    store.claim.assert_called_once_with(context.user.id, operation_id, "a" * 64)
    store.finish.assert_called_once()
    creator.create.assert_called_once()


@pytest.mark.asyncio
async def test_docs_execute_marks_generic_failures_uncertain_and_preserves_error(tmp_path):
    context = _context(tmp_path)
    operation_id = str(uuid4())
    prepared = DocumentPrepare(
        request_key="docs_execute_2", action="create", document=_spec()
    )
    store = MagicMock()
    store.get.return_value = {
        "id": operation_id,
        "capability": "docs_create",
        "spec": prepared.model_dump_json(),
    }
    creator = MagicMock()
    creator.create.side_effect = ToolError("Drive blocked", code="permission_denied")
    service = MagicMock()
    service.__enter__.return_value = service
    service.__exit__.return_value = False

    with (
        patch("app.tools.documents.operation_store", return_value=store),
        patch(
            "app.tools.documents.refresh_and_store_if_needed",
            AsyncMock(return_value=SimpleNamespace()),
        ),
        patch("app.tools.documents.build", return_value=service),
        patch("app.tools.documents.DocumentCreator", return_value=creator),
    ):
        with pytest.raises(ToolError, match="Drive blocked"):
            await docs_execute(
                DocumentApproval(operation_id=operation_id, approved_digest="b" * 64), context
            )

    store.uncertain.assert_called_once_with(context.user.id, operation_id, "permission_denied")


@pytest.mark.asyncio
async def test_docs_reconcile_rejects_invalid_rows_without_any_google_write(tmp_path):
    context = _context(tmp_path)
    operation_id = str(uuid4())
    store = MagicMock()
    store.get.return_value = {
        "id": operation_id,
        "state": "succeeded",
        "capability": "docs_create",
        "resource_id": "doc-id",
    }
    with patch("app.tools.documents.operation_store", return_value=store):
        with pytest.raises(ToolError) as invalid:
            await docs_reconcile(operation_id, context)
    assert invalid.value.code == "invalid_operation"

    store.get.return_value = {
        "id": operation_id,
        "state": "uncertain",
        "capability": "docs_edit",
        "resource_id": None,
    }
    with patch("app.tools.documents.operation_store", return_value=store):
        with pytest.raises(ToolError) as unavailable:
            await docs_reconcile(operation_id, context)
    assert unavailable.value.code == "reconcile_unavailable"


@pytest.mark.asyncio
async def test_docs_reconcile_reads_back_create_without_replaying_the_write(tmp_path):
    context = _context(tmp_path)
    operation_id = str(uuid4())
    prepared = DocumentPrepare(
        request_key="docs_reconcile_1", action="create", document=_spec()
    )
    store = MagicMock()
    store.get.return_value = {
        "id": operation_id,
        "state": "uncertain",
        "capability": "docs_create",
        "resource_id": "doc-created",
        "spec": prepared.model_dump_json(),
    }
    creator = MagicMock()
    service = MagicMock()
    service.__enter__.return_value = service
    service.__exit__.return_value = False
    with (
        patch("app.tools.documents.operation_store", return_value=store),
        patch(
            "app.tools.documents.refresh_and_store_if_needed",
            AsyncMock(return_value=SimpleNamespace()),
        ),
        patch("app.tools.documents.build", return_value=service),
        patch("app.tools.documents.DocumentCreator", return_value=creator),
    ):
        result = await docs_reconcile(operation_id, context)

    assert result.data["reconciled"] is True
    creator.verify_created.assert_called_once_with("doc-created", prepared.document)
    store.finish_reconciliation.assert_called_once()
