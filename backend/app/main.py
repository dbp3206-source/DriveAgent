"""FastAPI application factory của Veridra."""

import asyncio
import ipaddress
import logging
import re
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
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
    briefings,
    chat,
    chat_tasks,
    creation,
    documents,
    drive,
    evaluation_jobs,
    gmail,
    gmail_remote,
    harness,
    local_sources,
    memory,
    metrics,
    protocols,
    provider_credentials,
    rag,
    release,
    scheduler,
    sheets,
    skills,
    system,
)
from app.api.dependencies import is_trusted_ui_origin
from app.core.config import PROJECT_ROOT, assert_release_configuration, get_settings
from app.db.session import SessionFactory, engine, init_database
from app.services.agentops import expire_run_traces
from app.services.artifacts import artifact_tool_definitions
from app.services.backup_retention import expire_pre_scrub_backups
from app.services.embeddings import EmbeddingService
from app.services.inference_gateway import RequestPinningGate
from app.services.local_sources import local_source_tool_definitions
from app.services.memory import MemoryService, memory_tool_definitions
from app.services.protocols import build_protocol_apps
from app.services.rag import RagService, rag_tool_definitions
from app.services.user_inference import UserInferencePool, runtime_settings
from app.services.vector_recovery import reconcile_document_vectors
from app.services.vector_store import VectorStore
from app.tools.calculator import calculator_tool_definitions
from app.tools.calendar import calendar_tool_definitions
from app.tools.company_info import company_tool_definitions
from app.tools.contracts import ToolAccessDeniedError, ToolError, ToolRateLimitError
from app.tools.documents import document_tool_definitions
from app.tools.drive import drive_tool_definitions
from app.tools.gmail import gmail_tool_definitions
from app.tools.registry import ToolRegistry
from app.tools.sheets import spreadsheet_tool_definitions
from app.tools.skills import skill_tool_definitions
from app.tools.web_research import web_research_tool_definitions

settings = get_settings()
protocol_bridge, mcp_lifespan_app, mcp_app, a2a_app = build_protocol_apps(settings)
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


async def _new_orchestrator(runtime_settings, registry):
    if runtime_settings.orchestrator_backend == "langgraph":
        from app.agent.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(runtime_settings, registry)
    elif runtime_settings.orchestrator_backend == "adk":
        orchestrator = AdkOrchestrator(runtime_settings, registry)
    else:
        orchestrator = CompilerOrchestrator(runtime_settings, registry)
    await orchestrator.initialize()
    return orchestrator


async def _periodic_agentops_retention(app: FastAPI) -> None:
    """Keep the 30-day trace policy true for a long-running local process."""

    while True:
        await asyncio.sleep(3600)
        try:
            async with SessionFactory() as retention_db:
                expired = await expire_run_traces(retention_db)
                await retention_db.commit()
            removed_backups = expire_pre_scrub_backups(PROJECT_ROOT / ".local-backups")
            from app.services.operational_tracing import expire_local_langfuse_metadata

            await asyncio.to_thread(expire_local_langfuse_metadata)
            app.state.agentops_retention_healthy = True
            app.state.encrypted_backup_retention_healthy = True
            if expired:
                logging.getLogger(__name__).info("Expired %s old AgentOps run traces", expired)
            if removed_backups:
                logging.getLogger(__name__).info(
                    "Expired %s encrypted AgentOps backups", len(removed_backups)
                )
        except Exception as exc:
            app.state.agentops_retention_healthy = False
            app.state.encrypted_backup_retention_healthy = False
            logging.getLogger(__name__).error(
                "AgentOps trace retention failed; type=%s", type(exc).__name__
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    assert_release_configuration(settings)
    await init_database()
    from app.services.object_storage import initialize_object_storage

    try:
        await initialize_object_storage(settings)
        app.state.object_storage_healthy = True
    except (httpx.HTTPError, RuntimeError) as exc:
        app.state.object_storage_healthy = False
        logging.getLogger(__name__).error(
            "Private object storage unavailable at startup; type=%s", type(exc).__name__
        )
    from app.services.relational_state import prepare_state_schema, state_engine

    if settings.relational_state_url is not None:
        await asyncio.to_thread(
            prepare_state_schema, state_engine(settings.relational_state_url.get_secret_value())
        )
    from app.services.relational_skills import close_state_engines, initialize_skill_store

    await asyncio.to_thread(initialize_skill_store, settings)
    from app.services.relational_evaluation import evaluation_queue, initialize_evaluation_queue

    await asyncio.to_thread(initialize_evaluation_queue, settings)
    from app.services.relational_quota import initialize_quota_store

    await asyncio.to_thread(initialize_quota_store, settings)
    from app.services.relational_circuit import initialize_circuit_store

    await asyncio.to_thread(initialize_circuit_store, settings)
    from app.services.relational_operations import initialize_operation_store

    await asyncio.to_thread(initialize_operation_store, settings)
    from app.services.relational_remote_actions import initialize_remote_action_ledger

    await asyncio.to_thread(initialize_remote_action_ledger, settings)
    async with SessionFactory() as retention_db:
        expired = await expire_run_traces(retention_db)
        await retention_db.commit()
    app.state.agentops_retention_healthy = True
    try:
        removed_backups = expire_pre_scrub_backups(PROJECT_ROOT / ".local-backups")
        app.state.encrypted_backup_retention_healthy = True
    except OSError as exc:
        removed_backups = []
        app.state.encrypted_backup_retention_healthy = False
        logging.getLogger(__name__).error(
            "Encrypted backup retention unavailable; type=%s", type(exc).__name__
        )
    if expired:
        logging.getLogger(__name__).info("Expired %s old AgentOps run traces", expired)
    if removed_backups:
        logging.getLogger(__name__).info(
            "Expired %s encrypted AgentOps backups", len(removed_backups)
        )
    vector_store = VectorStore(settings)
    await vector_store.initialize()
    async with SessionFactory() as recovery_db:
        recovered_vectors = await reconcile_document_vectors(recovery_db, vector_store)
    logging.getLogger(__name__).info(
        "Document vector reconciliation verified %s SQL rows; backend=%s",
        recovered_vectors,
        vector_store.backend_name,
    )
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
    for definition in calendar_tool_definitions():
        registry.register(definition)
    for definition in company_tool_definitions():
        registry.register(definition)
    for definition in web_research_tool_definitions():
        registry.register(definition)
    for definition in skill_tool_definitions():
        registry.register(definition)

    environment_settings = runtime_settings(settings, settings.gemini_api_key)
    orchestrator = await _new_orchestrator(environment_settings, registry)
    inference_pinning = RequestPinningGate()
    user_inference = UserInferencePool(
        settings=settings,
        registry=registry,
        factory=_new_orchestrator,
        environment_orchestrator=orchestrator,
        retire=inference_pinning.retire,
    )
    app.state.vector_store = vector_store
    app.state.embeddings = embeddings
    app.state.rag_service = rag_service
    app.state.registry = registry
    app.state.orchestrator = orchestrator
    app.state.user_inference = user_inference
    app.state.resolve_user_orchestrator = user_inference.get
    app.state.resolve_user_alternate_orchestrator = user_inference.get_alternate
    app.state.gemini_rotation_lock = asyncio.Lock()
    app.state.inference_pinning = inference_pinning

    async def invalidate_user_gemini_runtime(user_id: str) -> None:
        """Publish a user's newly activated credential after active requests finish."""

        async with app.state.gemini_rotation_lock:
            await user_inference.invalidate(user_id)

    app.state.invalidate_user_gemini_runtime = invalidate_user_gemini_runtime
    app.state.runtime_started_at = datetime.now(UTC).isoformat()
    protocol_bridge.registry = registry
    retention_task = asyncio.create_task(_periodic_agentops_retention(app))
    from app.services.durable_evaluation import worker

    queue = await asyncio.to_thread(evaluation_queue, settings)
    evaluation_worker = asyncio.create_task(worker(settings.data_dir, queue=queue))
    from app.services.pdf_jobs import worker as pdf_worker
    pdf_task = asyncio.create_task(pdf_worker(SessionFactory, settings))
    from app.services.scheduled_jobs import worker as scheduled_worker

    scheduler_task = asyncio.create_task(scheduled_worker(SessionFactory, settings, registry))
    from app.services.chat_tasks import worker as chat_worker

    chat_workers = [asyncio.create_task(chat_worker(SessionFactory, app)) for _ in range(2)]
    try:
        async with mcp_lifespan_app.router.lifespan_context(mcp_lifespan_app):
            yield
    finally:
        for task in chat_workers:
            task.cancel()
        for task in chat_workers:
            with suppress(asyncio.CancelledError):
                await task
        scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await scheduler_task
        pdf_task.cancel()
        with suppress(asyncio.CancelledError):
            await pdf_task
        evaluation_worker.cancel()
        with suppress(asyncio.CancelledError):
            await evaluation_worker
        retention_task.cancel()
        with suppress(asyncio.CancelledError):
            await retention_task
        from app.services.operational_tracing import flush_operational_traces

        await asyncio.to_thread(flush_operational_traces)
        await user_inference.close()
        await orchestrator.close()
        await embeddings.close()
        await vector_store.close()
        await engine.dispose()
        await asyncio.to_thread(close_state_engines)


app = FastAPI(
    title="Veridra API",
    version="0.1.0",
    description="Trợ lý Veridra với ADK quota-first, RAG, Memory và giao thức MCP/A2A.",
    lifespan=lifespan,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret,
    session_cookie="drive_agent_session",
    same_site="lax",
    https_only=not settings.is_local_environment,
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
async def local_loopback_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Do not let a development instance serve requests from a remote peer."""

    if settings.is_local_environment:
        peer = request.client.host if request.client else ""
        try:
            loopback = ipaddress.ip_address(peer).is_loopback
        except ValueError:
            # Starlette's in-process TestClient uses this synthetic peer. It is
            # not a routable network address exposed by a socket listener.
            loopback = peer == "testclient"
        # Docker's loopback-published port arrives from its NAT gateway. This is
        # opt-in, one exact peer, and effective only inside Docker. Never trust
        # Host/X-Forwarded-For or a whole private subnet to bypass this boundary.
        container_gateway = (
            bool(settings.container_local_gateway)
            and peer == settings.container_local_gateway
            and Path("/.dockerenv").is_file()
        )
        if not loopback and not container_gateway:
            return JSONResponse(status_code=403, content={"detail": "Local-only instance"})
    return await call_next(request)


@app.middleware("http")
async def public_unsafe_request_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Apply the same browser-origin gate to every session-backed write API.

    Signed remote action tokens are deliberately independent of browser
    sessions; MCP/A2A have their own protocol authorization. The Gmail webhook
    currently returns 501 and will need its own Google OIDC check if enabled.
    """

    path = request.url.path
    exempt = (
        path in {"/api/gmail/remote/action", "/api/gmail/remote/webhook"}
        or path in {"/api/mcp", "/api/a2a"}
        or path.startswith(("/api/mcp/", "/api/a2a/"))
    )
    if (
        not settings.is_local_environment
        and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}
        and path.startswith("/api/")
        and not exempt
        and not is_trusted_ui_origin(request, settings)
    ):
        return JSONResponse(
            status_code=403,
            content={"detail": "Yêu cầu ghi phải bắt nguồn từ giao diện Veridra."},
        )
    return await call_next(request)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    incoming = request.headers.get("X-Request-ID", "")
    request.state.request_id = (
        incoming if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", incoming) else str(uuid4())
    )
    from app.services.operational_tracing import tracer

    # Fixed span name: URL query/path may contain user data. Never export them.
    with tracer().start_as_current_span(
        "veridra.request", record_exception=False, set_status_on_exception=False
    ) as span:
        span.set_attribute("request_id", request.state.request_id)
        response = await call_next(request)
        span.set_attribute("http_status", response.status_code)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers.setdefault(
        "Content-Security-Policy",
        (
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            "script-src 'self'; style-src 'self' 'unsafe-inline'; "
            # Gmail's sandboxed srcdoc inherits this policy; allowing HTTPS image
            # sources is required for the user's explicit Gmail setting to display
            # newsletter images by default. Scripts, forms, frames, and connections
            # remain restricted, and MailBodyViewer still strips active HTML.
            "img-src 'self' data: https:; "
            "connect-src 'self'; form-action 'self' https://accounts.google.com"
        ),
    )
    # The SPA entrypoint references content-hashed chunks.  Revalidate the HTML on
    # every navigation so a restarted local runner never serves an old chunk map
    # that no longer exists after a fresh frontend build.  Hashed JS/CSS assets
    # remain cacheable by the static-file handler.
    if request.url.path == "/" or request.url.path.endswith(".html"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


@app.exception_handler(ToolError)
async def tool_error_handler(_request: Request, exc: ToolError):
    if isinstance(exc, ToolAccessDeniedError):
        status_code = 403
    elif isinstance(exc, ToolRateLimitError) or exc.code in {
        "quota_daily_exhausted",
        "quota_minute_exhausted",
    }:
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
    briefings.router,
    system.router,
    drive.router,
    rag.router,
    memory.router,
    metrics.router,
    chat_tasks.router,
    chat.router,
    creation.router,
    audit.router,
    admin.router,
    artifacts.router,
    local_sources.router,
    protocols.router,
    provider_credentials.router,
    documents.router,
    sheets.router,
    skills.router,
    gmail.router,
    gmail_remote.router,
    harness.router,
    release.router,
    evaluation_jobs.router,
    scheduler.router,
):
    app.include_router(api_router)


# Khi frontend đã build, FastAPI phục vụ cùng một origin. Trong lúc dev, Vite dùng proxy.
app.mount("/api/mcp", mcp_app)
app.mount("/api/a2a", a2a_app)
frontend_dist = settings.frontend_dist
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
