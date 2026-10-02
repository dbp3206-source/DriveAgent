"""Health, setup diagnostics và catalog tool có schema JSON."""

import asyncio
import os
from time import monotonic

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import text

from app.api.dependencies import CurrentUser, DbSession, is_trusted_ui_origin
from app.api.schemas import HealthResponse
from app.core.config import get_settings
from app.services.embeddings import EMBEDDING_DIMENSION
from app.services.object_storage import probe_object_storage
from app.services.operations import OperationStore  # noqa: F401 - compatibility seam for tests
from app.services.relational_operations import operation_store_for
from app.tools.contracts import ToolContext, ToolError

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request, db: DbSession):
    """Report local readiness without implying live Google/Gemini connectivity.

    The health endpoint deliberately avoids outbound provider probes: Gemini calls
    can consume quota, while OAuth/Workspace probes depend on a specific user's
    authorization. A successful feature request is the source of live connectivity
    status for that user's session.
    """
    settings = get_settings()
    database_ok = True
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=5)
    except Exception:
        database_ok = False
    vector_backend = request.app.state.vector_store.backend_name
    storage_ok = getattr(request.app.state, "object_storage_healthy", False)
    now = monotonic()
    if now - getattr(request.app.state, "storage_probe_at", 0) >= 30:
        # Cache the bounded read-only probe to avoid an outbound call per poll.
        request.app.state.storage_probe_at = now
        try:
            storage_ok = await asyncio.wait_for(probe_object_storage(settings), timeout=5)
        except Exception:
            storage_ok = False
        request.app.state.object_storage_healthy = storage_ok
    return HealthResponse(
        # SQLite keeps retrieval available, but a silent fallback usually means
        # Qdrant could not acquire its local storage (often another process).
        # Report that honestly so operators do not mistake fallback for full health.
        status=(
            "ok"
            if database_ok
            and storage_ok
            and vector_backend in {"qdrant-embedded", "postgres-hybrid", "postgres-pgvector"}
            else "degraded"
        ),
        database=database_ok,
        object_storage=storage_ok,
        gemini_configured=settings.gemini_is_configured,
        google_oauth_configured=settings.oauth_is_configured,
        vector_store=vector_backend,
        gemini_chat_model=settings.gemini_chat_model,
        gemini_fallback_model=settings.gemini_fallback_model,
        gemini_embedding_model=settings.gemini_embedding_model,
        embedding_dimensions=EMBEDDING_DIMENSION,
        runtime_started_at=getattr(request.app.state, "runtime_started_at", None),
        runtime_pid=os.getpid(),
    )


@router.get("/tools")
async def tool_catalog(request: Request, _user: CurrentUser):
    return [
        {
            "name": definition.name,
            "description": definition.description,
            "input_schema": definition.input_model.model_json_schema(),
            "output_schema": definition.output_model.model_json_schema(),
            "required_permissions": sorted(definition.required_permissions),
            "required_oauth_scopes": sorted(definition.required_oauth_scopes),
            "rate_limit_per_minute": definition.rate_limit_per_minute,
        }
        for definition in request.app.state.registry.definitions()
    ]


@router.get("/operations/status")
async def operation_status(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
):
    """Expose only redacted operation metadata for the signed-in user."""

    store = operation_store_for(get_settings())
    return await asyncio.to_thread(store.list_status, user.id, limit=limit)


@router.post("/operations/{operation_id}/acknowledge", status_code=204)
async def acknowledge_operation(
    operation_id: str,
    request: Request,
    user: CurrentUser,
):
    """Record manual review without claiming that Google completed the write."""

    settings = get_settings()
    if not is_trusted_ui_origin(request, settings):
        raise HTTPException(403, "Chỉ có thể đóng cảnh báo từ giao diện local.")
    store = operation_store_for(settings)
    await asyncio.to_thread(store.acknowledge_uncertain, user.id, operation_id)


@router.post("/operations/{operation_id}/reconcile")
async def reconcile_operation(
    operation_id: str,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Dispatch read-back by capability through the governed Tool Registry."""

    settings = get_settings()
    if not is_trusted_ui_origin(request, settings):
        raise HTTPException(403, "Chỉ có thể đối soát từ giao diện local.")
    store = operation_store_for(settings)
    row = await asyncio.to_thread(store.get, user.id, operation_id)
    tool_name = {
        "sheets_create": "sheets_reconcile",
        "sheets_edit": "sheets_reconcile",
        "docs_create": "docs_reconcile",
        "docs_edit": "docs_reconcile",
        "gmail_draft_create": "gmail_reconcile_draft",
    }.get(row["capability"])
    if not tool_name:
        raise ToolError("Loại thao tác này không hỗ trợ read-back.", code="reconcile_unavailable")
    return await request.app.state.registry.execute(
        tool_name,
        {"operation_id": operation_id},
        ToolContext(
            request_id=request.state.request_id,
            user=user,
            db=db,
            settings=settings,
            source="operation_reconciliation",
        ),
    )


@router.post("/operations/{operation_id}/archive", status_code=204)
async def archive_operation(operation_id: str, request: Request, user: CurrentUser):
    settings = get_settings()
    if not is_trusted_ui_origin(request, settings):
        raise HTTPException(403, "Chỉ có thể lưu trữ từ giao diện local.")
    store = operation_store_for(settings)
    await asyncio.to_thread(store.archive, user.id, operation_id)
