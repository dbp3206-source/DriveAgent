"""Health, setup diagnostics và catalog tool có schema JSON."""

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.api.dependencies import CurrentUser, DbSession
from app.api.schemas import HealthResponse
from app.core.config import get_settings
from app.services.embeddings import EMBEDDING_DIMENSION

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request, db: DbSession):
    settings = get_settings()
    database_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        database_ok = False
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        database=database_ok,
        gemini_configured=settings.gemini_is_configured,
        google_oauth_configured=settings.oauth_is_configured,
        vector_store=request.app.state.vector_store.backend_name,
        gemini_chat_model=settings.gemini_chat_model,
        gemini_fallback_model=settings.gemini_fallback_model,
        gemini_embedding_model=settings.gemini_embedding_model,
        embedding_dimensions=EMBEDDING_DIMENSION,
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
