from types import SimpleNamespace

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.dependencies import get_current_user
from app.api.harness import router
from app.db.models import Base, ChatSession, LongTermMemory, Message, User
from app.db.session import get_db
from app.tools.calculator import calculator_tool_definitions
from app.tools.registry import ToolRegistry


async def test_harness_uses_owned_data_and_feedback_is_upserted(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'harness.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(router)
    registry = ToolRegistry()
    for definition in calculator_tool_definitions():
        registry.register(definition)
    app.state.registry = registry
    app.state.orchestrator = SimpleNamespace()

    async with factory() as db:
        owner = User(email="owner@test.invalid", display_name="Owner", role="owner")
        other = User(email="other@test.invalid", display_name="Other", role="owner")
        db.add_all([owner, other])
        await db.flush()
        owned_session = ChatSession(user_id=owner.id, title="Owned")
        other_session = ChatSession(user_id=other.id, title="Private")
        db.add_all([owned_session, other_session])
        await db.flush()
        answer = Message(
            user_id=owner.id,
            session_id=owned_session.id,
            role="assistant",
            content="Answer",
        )
        private_answer = Message(
            user_id=other.id,
            session_id=other_session.id,
            role="assistant",
            content="Private",
        )
        db.add_all(
            [
                answer,
                private_answer,
                LongTermMemory(
                    user_id=owner.id,
                    kind="preference",
                    content="Concise",
                    normalized_hash="owned",
                ),
                LongTermMemory(
                    user_id=other.id,
                    kind="preference",
                    content="Private",
                    normalized_hash="other",
                ),
            ]
        )
        await db.commit()

        async def current_user():
            return owner

        async def session():
            yield db

        app.dependency_overrides[get_current_user] = current_user
        app.dependency_overrides[get_db] = session
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            overview = (await client.get("/api/harness/overview")).json()
            assert overview["context"] == {"sessions": 1, "active_memories": 1}
            assert overview["tools"]["total"] == 1
            assert overview["evaluation"]["feedback_count"] == 0

            url = f"/api/harness/feedback/{answer.id}"
            assert (await client.post(url, json={"rating": "helpful"})).status_code == 200
            assert (
                await client.post(url, json={"rating": "notlish", "reasons": []})
            ).status_code == 422
            assert (
                await client.post(
                    f"/api/harness/feedback/{private_answer.id}",
                    json={"rating": "helpful"},
                )
            ).status_code == 404
            assert (
                await client.post(url, json={"rating": "not_helpful", "reasons": ["too_short"]})
            ).status_code == 200
            updated = (await client.get("/api/harness/overview")).json()
            assert updated["evaluation"]["feedback_count"] == 1
            assert updated["evaluation"]["helpful_rate"] == 0.0
    await engine.dispose()
