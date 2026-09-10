"""FastAPI application factory của DriveAgent."""

import logging
import os
import re
from contextlib import asynccontextmanager
from uuid import uuid4

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.agent.adk_orchestrator import AdkOrchestrator
from app.agent.compiler import CompilerOrchestrator
from app.api import (
    admin,
    artifacts,
    audit,
    auth,
    chat,
    creation,
    documents,
    drive,
    gmail,
    harness,
    local_sources,
    memory,
    protocols,
    rag,
    sheets,
    skills,
    slides,
    system,
    visuals,
)
from app.core.config import get_settings
from app.db.session import engine, init_database
from app.services.artifacts import artifact_tool_definitions
from app.services.embeddings import EmbeddingService
from app.services.local_sources import local_source_tool_definitions
from app.services.memory import MemoryService, memory_tool_definitions
from app.services.protocols import build_protocol_apps
from app.services.rag import RagService, rag_tool_definitions
from app.services.vector_store import VectorStore
from app.tools.calculator import calculator_tool_definitions
from app.tools.contracts import ToolAccessDeniedError, ToolError, ToolRateLimitError
from app.tools.documents import document_tool_definitions
from app.tools.drive import drive_tool_definitions
from app.tools.gmail import gmail_tool_definitions
from app.tools.registry import ToolRegistry
from app.tools.sheets import spreadsheet_tool_definitions
from app.tools.skills import skill_tool_definitions
from app.tools.slides import slide_tool_definitions
from app.tools.visuals import visual_tool_definitions

settings = get_settings()
protocol_bridge, mcp_lifespan_app, mcp_app, a2a_app = build_protocol_apps(settings)
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
    vector_store = VectorStore(settings)
    await vector_store.initialize()
    embeddings = EmbeddingService(settings)
    rag_service = RagService(embeddings, vector_store)
    memory_service = MemoryService(embeddings, vector_store)

    registry = ToolRegistry()
    for definition in drive_tool_definitions():
        registry.register(definition)
    for definition in document_tool_definitions():
        registry.register(definition)
    for definition in spreadsheet_tool_definitions():
        registry.register(definition)
    for definition in slide_tool_definitions():
        registry.register(definition)
    for definition in calculator_tool_definitions():
        registry.register(definition)
    for definition in artifact_tool_definitions():
        registry.register(definition)
    for definition in local_source_tool_definitions():
        registry.register(definition)
    for definition in rag_tool_definitions(rag_service, registry):
        registry.register(definition)
    for definition in memory_tool_definitions(memory_service):
        registry.register(definition)
    for definition in gmail_tool_definitions():
        registry.register(definition)
    for definition in visual_tool_definitions():
        registry.register(definition)
    for definition in skill_tool_definitions():
        registry.register(definition)

    if settings.orchestrator_backend == "langgraph":
        from app.agent.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(settings, registry)
    elif settings.orchestrator_backend == "adk":
        orchestrator = AdkOrchestrator(settings, registry)
    else:
        orchestrator = CompilerOrchestrator(settings, registry)
    await orchestrator.initialize()
    app.state.vector_store = vector_store
    app.state.embeddings = embeddings
    app.state.registry = registry
    app.state.orchestrator = orchestrator
    protocol_bridge.registry = registry
    try:
        async with mcp_lifespan_app.router.lifespan_context(mcp_lifespan_app):
            yield
    finally:
        await orchestrator.close()
        await embeddings.close()
        await vector_store.close()
        await engine.dispose()


app = FastAPI(
    title="DriveAgent API",
    version="0.1.0",
    description="Google Drive Agent với ADK quota-first, RAG, Memory và giao thức MCP/A2A.",
    lifespan=lifespan,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret,
    session_cookie="drive_agent_session",
    same_site="lax",
    https_only=settings.environment == "production",
    max_age=60 * 60 * 24 * 14,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    incoming = request.headers.get("X-Request-ID", "")
    request.state.request_id = (
        incoming if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", incoming) else str(uuid4())
    )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
        "script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https://*.googleusercontent.com; "
        "connect-src 'self'; form-action 'self' https://accounts.google.com"
    )
    return response


@app.exception_handler(ToolError)
async def tool_error_handler(_request: Request, exc: ToolError):
    if isinstance(exc, ToolAccessDeniedError):
        status_code = 403
    elif isinstance(exc, ToolRateLimitError):
        status_code = 429
    elif exc.retryable:
        status_code = 503
    else:
        status_code = 400
    return JSONResponse(
        status_code=status_code,
        content={"detail": str(exc), "code": exc.code, "retryable": exc.retryable},
    )


for api_router in (
    auth.router,
    system.router,
    drive.router,
    rag.router,
    memory.router,
    chat.router,
    creation.router,
    audit.router,
    admin.router,
    artifacts.router,
    local_sources.router,
    protocols.router,
    documents.router,
    sheets.router,
    slides.router,
    skills.router,
    gmail.router,
    harness.router,
    visuals.router,
):
    app.include_router(api_router)


# Khi frontend đã build, FastAPI phục vụ cùng một origin. Trong lúc dev, Vite dùng proxy.
app.mount("/api/mcp", mcp_app)
app.mount("/api/a2a", a2a_app)
frontend_dist = settings.frontend_dist
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
