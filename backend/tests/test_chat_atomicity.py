from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agent.orchestrator import AgentNotConfiguredError
from app.api.chat import chat
from app.api.schemas import ChatRequest
from app.db.models import Base, ChatSession, Message, User


class FailingOrchestrator:
    async def run(self, **_kwargs):
        raise AgentNotConfiguredError("No model")


async def test_failed_new_turn_does_not_leave_duplicate_message_or_empty_session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email="atomic@example.com", display_name="Atomic", role="editor")
        db.add(user)
        await db.commit()
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="atomic-request"),
            app=SimpleNamespace(state=SimpleNamespace(orchestrator=FailingOrchestrator())),
        )
        with pytest.raises(HTTPException) as error:
            await chat(ChatRequest(message="retry me"), request, user, db)
        assert error.value.status_code == 503
        assert await db.scalar(select(func.count()).select_from(Message)) == 0
        assert await db.scalar(select(func.count()).select_from(ChatSession)) == 0
    await engine.dispose()
