"""Real chat/creation HTTP routes; isolated DB and inert compiler boundary only."""

from types import SimpleNamespace

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agent.orchestrator import AgentRunResult
from app.api.chat import router as chat_router
from app.api.creation import router as creation_router
from app.api.dependencies import get_current_user
from app.db.models import Base, User
from app.db.session import get_db


async def test_chat_proposals_persist_and_prepare_only_owned_immutable_spec(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(chat_router)
    app.include_router(creation_router)
    proposal = {
        "kind": "document",
        "document": {"title": "Kế hoạch", "blocks": [{"text": "Ôn tập"}]},
    }

    async def run(**kwargs):
        return AgentRunResult(
            answer="Chờ xác nhận", plan=[], trace=[], citations=[], proposals=[proposal]
        )

    app.state.orchestrator = SimpleNamespace(run=run)
    prepared = []

    async def invoke(name, payload, request, user, db):
        prepared.append((name, payload.model_dump(), user.id))
        return {"data": {"state": "pending"}}

    monkeypatch.setattr("app.api.creation.invoke", invoke)

    @app.middleware("http")
    async def request_id(request, call_next):
        request.state.request_id = "test-creation"
        return await call_next(request)

    async with factory() as db:
        owner = User(email="alice@test.invalid", display_name="A", role="owner")
        other = User(email="bob@test.invalid", display_name="B", role="owner")
        db.add_all([owner, other])
        await db.commit()
        actor = owner

        async def user():
            return actor

        async def session():
            yield db

        app.dependency_overrides[get_current_user] = user
        app.dependency_overrides[get_db] = session
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat", json={"message": "Tạo tài liệu"})
            assert response.status_code == 200
            result = response.json()
            assert not prepared  # Generation/persistence does not prepare or execute writes.
            messages_url = f"/api/chat/sessions/{result['session_id']}/messages"
            saved = (await client.get(messages_url)).json()
            assert saved[-1]["proposals"] == result["proposals"]
            proposal_id = result["proposals"][0]["id"]
            url = f"/api/creation/proposals/{proposal_id}/prepare"
            # Browser-supplied replacements/approvals are not consumed by this endpoint.
            response = await client.post(url, json={"document": {"title": "Tampered"}})
            assert response.status_code == 200
            assert prepared[-1][1]["document"]["title"] == "Kế hoạch"
            assert prepared[-1][1]["request_key"] == proposal_id
            actor = other
            assert (await client.get(messages_url)).status_code == 404
            assert (await client.post(url)).status_code == 404
            assert len(prepared) == 1
    await engine.dispose()
