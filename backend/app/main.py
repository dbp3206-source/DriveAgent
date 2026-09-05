"""FastAPI application factory của DriveAgent."""

import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.agent.orchestrator import AgentOrchestrator
from app.api import admin, audit, auth, chat, drive, memory, rag, system
from app.core.config import get_settings
from app.db.session import engine, init_database
from app.services.embeddings import EmbeddingService
from app.services.memory import MemoryService, memory_tool_definitions
from app.services.rag import RagService, rag_tool_definitions
from app.services.vector_store import VectorStore
from app.tools.contracts import ToolAccessDeniedError, ToolError, ToolRateLimitError
from app.tools.drive import drive_tool_definitions
from app.tools.registry import ToolRegistry

settings = get_settings()
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
    for definition in rag_tool_definitions(rag_service, registry):
        registry.register(definition)
    for definition in memory_tool_definitions(memory_service):
        registry.register(definition)

    orchestrator = AgentOrchestrator(settings, registry)
    await orchestrator.initialize()
    app.state.vector_store = vector_store
    app.state.embeddings = embeddings
    app.state.registry = registry
    app.state.orchestrator = orchestrator
    try:
        yield
    finally:
        await orchestrator.close()
        await vector_store.close()
        await engine.dispose()


app = FastAPI(
    title="DriveAgent API",
    version="0.1.0",
    description="Google Drive Agent với Tool Registry, RAG, Memory và LangGraph.",
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
    request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
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
    audit.router,
    admin.router,
):
    app.include_router(api_router)


# Khi frontend đã build, FastAPI phục vụ cùng một origin. Trong lúc dev, Vite dùng proxy.
frontend_dist = settings.frontend_dist
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
