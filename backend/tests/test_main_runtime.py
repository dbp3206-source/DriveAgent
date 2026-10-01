from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Response
from starlette.requests import Request

from app import main
from app.core.config import Settings
from app.tools.contracts import ToolAccessDeniedError, ToolError, ToolRateLimitError


def _request(
    request_id: str | None = None,
    path: str = "/api/health",
    client_host: str = "127.0.0.1",
) -> Request:
    headers = [] if request_id is None else [(b"x-request-id", request_id.encode())]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": headers,
            "query_string": b"",
            "server": ("localhost", 8000),
            "client": (client_host, 1),
            "scheme": "http",
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ToolAccessDeniedError("blocked"), 403),
        (ToolRateLimitError("slow down"), 429),
        (ToolError("daily budget", code="quota_daily_exhausted"), 429),
        (ToolError("minute budget", code="quota_minute_exhausted"), 429),
        (ToolError("retry", retryable=True), 503),
        (ToolError("invalid"), 400),
    ],
)
async def test_tool_error_handler_maps_structured_errors(error, status):
    response = await main.tool_error_handler(_request(), error)
    assert response.status_code == status
    assert error.code.encode() in response.body


@pytest.mark.asyncio
async def test_request_id_middleware_preserves_safe_id_and_replaces_unsafe_id():
    async def call_next(_request):
        return Response("ok")

    safe = _request("QA_request-1")
    response = await main.request_id_middleware(safe, call_next)
    assert response.headers["x-request-id"] == "QA_request-1"
    assert safe.state.request_id == "QA_request-1"

    unsafe = _request("bad request id with spaces")
    response = await main.request_id_middleware(unsafe, call_next)
    assert response.headers["x-request-id"] != "bad request id with spaces"
    assert len(response.headers["x-request-id"]) == 36


@pytest.mark.asyncio
async def test_development_refuses_remote_peer_even_when_host_header_is_local():
    async def call_next(_request):
        return Response("ok")

    with patch.object(main, "settings", Settings(_env_file=None, environment="development")):
        local = await main.local_loopback_middleware(_request(), call_next)
        remote = await main.local_loopback_middleware(
            _request(client_host="203.0.113.7"), call_next
        )
        assert local.status_code == 200
        assert remote.status_code == 403


@pytest.mark.asyncio
async def test_container_gateway_is_exact_opt_in_and_requires_docker():
    async def call_next(_request):
        return Response("ok")

    configured = Settings(_env_file=None, container_local_gateway="172.17.0.1")
    with patch.object(main, "settings", configured):
        with patch.object(main.Path, "is_file", return_value=False):
            assert (
                await main.local_loopback_middleware(_request(client_host="172.17.0.1"), call_next)
            ).status_code == 403
        with patch.object(main.Path, "is_file", return_value=True):
            assert (
                await main.local_loopback_middleware(_request(client_host="172.17.0.1"), call_next)
            ).status_code == 200
            assert (
                await main.local_loopback_middleware(_request(client_host="172.17.0.2"), call_next)
            ).status_code == 403


@pytest.mark.asyncio
async def test_closed_beta_does_not_block_remote_peer_at_local_middleware():
    async def call_next(_request):
        return Response("ok")

    with patch.object(main, "settings", Settings(_env_file=None, environment="staging")):
        response = await main.local_loopback_middleware(
            _request(client_host="203.0.113.7"), call_next
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_security_headers_middleware_sets_all_browser_guards():
    async def call_next(_request):
        return Response("ok")

    response = await main.security_headers_middleware(_request(), call_next)
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "img-src 'self' data: https:" in response.headers["content-security-policy"]
    assert "accounts.google.com" in response.headers["content-security-policy"]


@pytest.mark.parametrize("path", ["/", "/index.html"])
async def test_security_headers_revalidate_spa_entrypoint(path: str):
    request = _request(path=path)

    async def call_next(_request):
        return Response("ok")

    response = await main.security_headers_middleware(request, call_next)

    assert response.headers["cache-control"] == "no-cache, must-revalidate"


def test_application_registers_expected_runtime_surfaces():
    paths = set(main.app.openapi()["paths"])
    assert "/api/health" in paths
    assert "/api/auth/google" in paths
    assert "/api/chat" in paths
    mount_paths = {getattr(route, "path", None) for route in main.app.routes}
    assert "/api/mcp" in mount_paths
    assert "/api/a2a" in mount_paths
    assert main.app.title == "Veridra API"
    assert main.app.description.startswith("Trợ lý Veridra")
    assert main.protocol_bridge is not None
    assert isinstance(main.app.user_middleware, list)


@pytest.mark.asyncio
async def test_insecure_beta_refuses_startup_before_database_changes():
    invalid = Settings(_env_file=None, environment="production", beta_invited_emails=[])
    fake_app = SimpleNamespace(state=SimpleNamespace())
    with (
        patch.object(main, "settings", invalid),
        patch.object(main, "init_database", AsyncMock()) as init_database,
        pytest.raises(ValueError, match="invited email"),
    ):
        async with main.lifespan(fake_app):
            pass
    init_database.assert_not_awaited()


def test_request_fixture_has_state_namespace():
    request = _request()
    request.state.example = SimpleNamespace(value=True)
    assert request.state.example.value is True


@pytest.mark.asyncio
@pytest.mark.parametrize("retention_error", [None, PermissionError("private archive")])
@pytest.mark.parametrize("storage_error", [None, RuntimeError("storage_bucket_unavailable")])
async def test_lifespan_initializes_and_closes_runtime_services(retention_error, storage_error):
    class AsyncContext:
        def __init__(self, value=None):
            self.value = value

        async def __aenter__(self):
            return self.value

        async def __aexit__(self, *_args):
            return False

    vector_store = SimpleNamespace(
        backend_name="qdrant-embedded",
        initialize=AsyncMock(),
        close=AsyncMock(),
    )
    embeddings = SimpleNamespace(close=AsyncMock())
    orchestrator = SimpleNamespace(initialize=AsyncMock(), close=AsyncMock())
    protocol_bridge = SimpleNamespace(registry=None)
    lifecycle_app = SimpleNamespace(
        router=SimpleNamespace(lifespan_context=lambda _app: AsyncContext())
    )
    fake_app = SimpleNamespace(state=SimpleNamespace())
    settings = Settings(
        _env_file=None,
        orchestrator_backend="adk",
        environment="development",
        public_base_url="http://localhost:8000",
    )
    session = AsyncMock()
    engine = SimpleNamespace(dispose=AsyncMock())

    with (
        patch.object(main, "settings", settings),
        patch(
            "app.services.object_storage.initialize_object_storage",
            AsyncMock(side_effect=storage_error),
        ),
        patch.object(main, "VectorStore", return_value=vector_store),
        patch.object(main, "EmbeddingService", return_value=embeddings),
        patch.object(main, "RagService", return_value=SimpleNamespace()),
        patch.object(main, "MemoryService", return_value=SimpleNamespace()),
        patch.object(main, "expire_run_traces", AsyncMock(return_value=0)),
        patch.object(main, "expire_pre_scrub_backups", return_value=[],
                     side_effect=retention_error),
        patch.object(main, "SessionFactory", side_effect=lambda: AsyncContext(session)),
        patch.object(main, "reconcile_document_vectors", AsyncMock(return_value=3)),
        patch.object(main, "AdkOrchestrator", return_value=orchestrator),
        patch.object(main, "protocol_bridge", protocol_bridge),
        patch.object(main, "mcp_lifespan_app", lifecycle_app),
        patch.object(main, "engine", engine),
        patch.object(main, "rag_tool_definitions", return_value=[]),
        patch.object(main, "memory_tool_definitions", return_value=[]),
    ):
        async with main.lifespan(fake_app):
            assert fake_app.state.vector_store is vector_store
            assert fake_app.state.embeddings is embeddings
            assert fake_app.state.orchestrator is orchestrator
            assert protocol_bridge.registry is fake_app.state.registry
            assert fake_app.state.encrypted_backup_retention_healthy is (retention_error is None)
            assert fake_app.state.object_storage_healthy is (storage_error is None)

    vector_store.initialize.assert_awaited_once()
    orchestrator.initialize.assert_awaited_once()
    orchestrator.close.assert_awaited_once()
    embeddings.close.assert_awaited_once()
    vector_store.close.assert_awaited_once()
    engine.dispose.assert_awaited_once()
