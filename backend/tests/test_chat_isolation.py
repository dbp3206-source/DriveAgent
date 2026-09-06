from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.chat import list_messages, list_sessions
from app.db.models import Base, ChatSession, Message, User, UserRole


@pytest.mark.asyncio
async def test_chat_sessions_and_messages_are_isolated_by_user(tmp_path: Path) -> None:
    """User B không thể liệt kê hoặc đoán ID để đọc chat của user A."""

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        first = User(email="first@example.com", display_name="First", role=UserRole.EDITOR.value)
        second = User(email="second@example.com", display_name="Second", role=UserRole.EDITOR.value)
        db.add_all([first, second])
        await db.flush()

        first_session = ChatSession(user_id=first.id, title="Chat riêng của A")
        second_session = ChatSession(user_id=second.id, title="Chat riêng của B")
        db.add_all([first_session, second_session])
        await db.flush()
        db.add_all(
            [
                Message(
                    session_id=first_session.id,
                    user_id=first.id,
                    role="user",
                    content="Nội dung chỉ A được đọc",
                ),
                Message(
                    session_id=second_session.id,
                    user_id=second.id,
                    role="user",
                    content="Nội dung chỉ B được đọc",
                ),
            ]
        )
        await db.commit()

        visible_to_second = await list_sessions(user=second, db=db)
        assert [session.id for session in visible_to_second] == [second_session.id]

        with pytest.raises(HTTPException) as denied:
            await list_messages(first_session.id, user=second, db=db)
        assert denied.value.status_code == 404

        own_messages = await list_messages(second_session.id, user=second, db=db)
        assert [message.content for message in own_messages] == ["Nội dung chỉ B được đọc"]

    await engine.dispose()
