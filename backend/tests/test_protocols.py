import json
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.applications import Starlette
from starlette.routing import Mount

from app.core.config import Settings
from app.db.models import Base, User
from app.services.protocols import build_protocol_apps, token_signer
from app.tools.calculator import calculator_tool_definitions
from app.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_real_mcp_and_a2a_sdk_routes_require_user_and_execute_without_llm(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite+aiosqlite:///{tmp_path / 'app.db'}")
    engine = create_async_engine(settings.resolved_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email="protocol@test.invalid", display_name="Test", role="editor")
        db.add(user)
        await db.commit()
        token = token_signer(settings).dumps({"sub": user.id, "scope": "knowledge:read"})
    bridge, lifecycle, mcp, a2a = build_protocol_apps(settings, factory)
    bridge.registry = ToolRegistry()
    for definition in calculator_tool_definitions():
        bridge.registry.register(definition)
    app = Starlette(routes=[Mount("/mcp", mcp), Mount("/a2a", a2a)])
    async with lifecycle.router.lifespan_context(lifecycle):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://127.0.0.1:8000"
        ) as client:
            assert (await client.post("/mcp/", json={})).status_code == 401
            assert (await client.get("/a2a/.well-known/agent-card.json")).status_code == 401
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json, text/event-stream",
            }
            initialized = await client.post(
                "/mcp/",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1"},
                    },
                },
            )
            assert initialized.status_code == 200, initialized.text
            call = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "knowledge_read",
                    "arguments": {
                        "tool": "calculate",
                        "arguments": {
                            "operation": "sum",
                            "values": ["0.1", "0.2"],
                        },
                    },
                },
            }
            result = await client.post("/mcp/", headers=headers, json=call)
            assert result.status_code == 200, result.text
            assert not result.json()["result"].get("isError"), result.text
            assert "0.3" in result.text
            card = await client.get("/a2a/.well-known/agent-card.json", headers=headers)
            assert card.status_code == 200, card.text
            assert card.json()["name"] == "DriveAgent Knowledge"
            a2a_headers = {**headers, "A2A-Version": "1.0"}
            sent = await client.post(
                "/a2a/",
                headers=a2a_headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "SendMessage",
                    "params": {
                        "message": {
                            "messageId": str(uuid4()),
                            "role": "ROLE_USER",
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "tool": "calculate",
                                            "arguments": {
                                                "operation": "sum",
                                                "values": ["0.1", "0.2"],
                                            },
                                        }
                                    ),
                                }
                            ],
                        },
                    },
                },
            )
            assert sent.status_code == 200 and "error" not in sent.json(), sent.text
            assert "0.3" in sent.text
            call["params"]["arguments"]["tool"] = "memory_save"
            blocked = await client.post("/mcp/", headers=headers, json=call)
            assert blocked.json()["result"].get("isError"), blocked.text
            rejected = await client.post(
                "/mcp/", headers={**headers, "Origin": "https://evil.invalid"}, json=call
            )
            assert rejected.status_code == 403
    await engine.dispose()
