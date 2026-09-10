"""Authenticated, read-only MCP/A2A adapters around the existing registry.

No agent delegation, cloud service, LLM call, arbitrary URL fetching or write tools.
Protocol tokens are short-lived app tokens, never Google access/refresh tokens.
"""

import json
from contextvars import ContextVar
from typing import Literal
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import a2a_pb2 as proto
from itsdangerous import BadSignature, URLSafeTimedSerializer
from mcp.server import MCPServer
from starlette.applications import Starlette
from starlette.authentication import SimpleUser
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.auth.permissions import permissions_for_role
from app.core.config import Settings
from app.db.models import User
from app.db.session import SessionFactory
from app.tools.contracts import ToolAccessDeniedError, ToolContext, ToolError

READ_TOOLS = frozenset(
    {
        "drive_list_files",
        "drive_search_files",
        "drive_read_file",
        "rag_search",
        "memory_search",
        "local_source_search",
        "local_source_read",
        "calculate",
    }
)
actor_id: ContextVar[str | None] = ContextVar("protocol_actor", default=None)


def token_signer(settings: Settings):
    return URLSafeTimedSerializer(settings.app_secret, salt="drive-agent-read-protocol-v1")


class ProtocolAuth:
    def __init__(self, app, settings: Settings, session_factory=SessionFactory):
        self.app, self.settings, self.sessions = app, settings, session_factory

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope, receive)
        origin = request.headers.get("origin")
        if origin and origin not in {self.settings.frontend_origin, self.settings.public_base_url}:
            return await JSONResponse({"detail": "Origin denied"}, 403)(scope, receive, send)
        bearer = request.headers.get("authorization", "")
        try:
            if not bearer.startswith("Bearer ") or len(bearer) > 4096:
                raise BadSignature("Missing bearer")
            payload = token_signer(self.settings).loads(bearer[7:], max_age=3600)
            if not isinstance(payload, dict) or payload.get("scope") != "knowledge:read":
                raise BadSignature("Invalid scope")
            async with self.sessions() as db:
                user = await db.get(User, payload.get("sub"))
                if not user or not user.is_active:
                    raise BadSignature("Inactive")
                user_id = user.id
        except (BadSignature, TypeError, ValueError):
            return await JSONResponse({"detail": "Protocol token required"}, 401)(
                scope, receive, send
            )
        # Bound body size for BOTH SDKs, without recording payload or credentials.
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 65536:
                return await JSONResponse({"detail": "Payload too large"}, 413)(
                    scope, receive, send
                )
            body.extend(chunk)
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        scope["user"] = SimpleUser(user_id)
        token = actor_id.set(user_id)
        try:
            await self.app(scope, bounded_receive, send)
        finally:
            actor_id.reset(token)


class KnowledgeBridge:
    def __init__(self, settings: Settings, session_factory=SessionFactory):
        self.settings, self.sessions = settings, session_factory
        self.registry = None  # Bound at application startup, before serving any request.

    async def read(self, tool: str, arguments: dict, user_id: str | None):
        if not user_id or tool not in READ_TOOLS:
            raise ToolAccessDeniedError("Giao thức chỉ cho phép bộ công cụ đọc đã duyệt.")
        if self.registry is None:
            raise ToolError("Registry chưa sẵn sàng.", code="not_ready")
        async with self.sessions() as db:
            user = await db.get(User, user_id)
            result = await self.registry.execute(
                tool,
                arguments,
                ToolContext(
                    request_id=str(uuid4()),
                    user=user,
                    db=db,
                    settings=self.settings,
                    source="protocol",
                ),
            )
            return result.model_dump(mode="json")


class KnowledgeExecutor(AgentExecutor):
    def __init__(self, bridge: KnowledgeBridge):
        self.bridge = bridge

    async def execute(self, context, event_queue):
        try:
            # Reject opaque files/URLs and unrelated tasks rather than fetching resources.
            if context.message is None or any(
                p.WhichOneof("content") != "text" for p in context.message.parts
            ):
                raise ToolError("Chỉ nhận text JSON chứa tool và arguments.", code="invalid_input")
            payload = json.loads(context.get_user_input())
            if set(payload) != {"tool", "arguments"} or not isinstance(payload["arguments"], dict):
                raise ValueError("Invalid input")
            data = await self.bridge.read(
                payload["tool"], payload["arguments"], context.call_context.user.user_name
            )
            result = {"success": True, "data": data}
        except (ValueError, TypeError, ToolError) as exc:
            result = {"success": False, "error_code": getattr(exc, "code", "invalid_input")}
        await event_queue.enqueue_event(
            proto.Message(
                message_id=str(uuid4()),
                role=proto.ROLE_AGENT,
                parts=[proto.Part(text=json.dumps(result, ensure_ascii=False))],
            )
        )

    async def cancel(self, context, event_queue):
        # Immediate read responses do not create resumable background jobs.
        return None


def build_protocol_apps(settings: Settings, session_factory=SessionFactory):
    bridge = KnowledgeBridge(settings, session_factory)
    mcp = MCPServer("DriveAgent Knowledge")

    @mcp.tool()
    async def knowledge_read(
        tool: Literal[
            "drive_list_files",
            "drive_search_files",
            "drive_read_file",
            "rag_search",
            "memory_search",
            "local_source_search",
            "local_source_read",
            "calculate",
        ],
        arguments: dict,
    ) -> dict:
        """Read private knowledge using a named governed tool; never create/edit/send."""
        return await bridge.read(tool, arguments, actor_id.get())

    @mcp.tool()
    async def knowledge_capabilities() -> dict:
        """Return input schemas for permitted knowledge tools, not data or credentials."""
        async with bridge.sessions() as db:
            user = await db.get(User, actor_id.get())
            if not user or not user.is_active or bridge.registry is None:
                raise ToolAccessDeniedError("Phiên không hợp lệ.")
            permissions = permissions_for_role(user.role)
            return {
                d.name: d.input_model.model_json_schema()
                for d in bridge.registry.definitions()
                if d.name in READ_TOOLS and d.required_permissions <= permissions
            }

    mcp_app = mcp.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        max_request_body_size=65536,
    )
    card = proto.AgentCard(
        name="DriveAgent Knowledge",
        version="1.0.0",
        description="Authenticated read-only knowledge access; no delegated LLM or writes.",
        supported_interfaces=[
            proto.AgentInterface(
                url=settings.public_base_url + "/api/a2a/",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        capabilities=proto.AgentCapabilities(streaming=False, push_notifications=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            proto.AgentSkill(
                id="knowledge_read",
                name="Read knowledge",
                description='Text JSON: {"tool":"calculate","arguments":{...}}',
                tags=["read-only"],
            )
        ],
        security_schemes={
            "bearer": proto.SecurityScheme(
                http_auth_security_scheme=proto.HTTPAuthSecurityScheme(scheme="bearer")
            )
        },
        security_requirements=[proto.SecurityRequirement(schemes={"bearer": proto.StringList()})],
    )
    handler = DefaultRequestHandler(
        agent_executor=KnowledgeExecutor(bridge), task_store=InMemoryTaskStore(), agent_card=card
    )
    a2a_app = Starlette(
        routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, rpc_url="/")]
    )
    return (
        bridge,
        mcp_app,
        ProtocolAuth(mcp_app, settings, session_factory),
        ProtocolAuth(a2a_app, settings, session_factory),
    )
