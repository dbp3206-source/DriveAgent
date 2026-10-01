from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.audit import router as audit_router
from app.api.chat import router as chat_router
from app.api.dependencies import get_current_user
from app.core.cursor import decode_cursor, encode_cursor
from app.db.models import AuditEvent, Base, ChatSession, Message, User
from app.db.session import get_db


async def test_chat_and_audit_keyset_pages_do_not_duplicate_rows(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'pages.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    async with factory() as db:
        user = User(email="page@test.invalid", display_name="Page", role="owner")
        db.add(user)
        await db.flush()
        for number in range(5):
            session = ChatSession(
                user_id=user.id,
                title=f"Session {number}",
                updated_at=now - timedelta(minutes=number),
            )
            db.add(session)
            await db.flush()
            db.add(
                Message(
                    session_id=session.id,
                    user_id=user.id,
                    role="user",
                    content=f"Message {number}",
                    created_at=now - timedelta(minutes=number),
                )
            )
            db.add(
                AuditEvent(
                    request_id=f"req-{number}",
                    user_id=user.id,
                    tool_name="calculator",
                    status="success",
                    created_at=now - timedelta(minutes=number),
                )
            )
        await db.commit()
        user_id = user.id

    app = FastAPI()
    app.include_router(chat_router)
    app.include_router(audit_router)

    async def current_user():
        async with factory() as db:
            return await db.get(User, user_id)

    async def session_dependency():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db] = session_dependency
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = (await client.get("/api/chat/sessions-page", params={"limit": 2})).json()
        second = (
            await client.get(
                "/api/chat/sessions-page",
                params={"limit": 2, "cursor": first["next_cursor"]},
            )
        ).json()
        assert len(first["items"]) == len(second["items"]) == 2
        assert {item["id"] for item in first["items"]}.isdisjoint(
            item["id"] for item in second["items"]
        )

        audit_first = (await client.get("/api/audit/page", params={"limit": 3})).json()
        audit_second = (
            await client.get(
                "/api/audit/page",
                params={"limit": 3, "cursor": audit_first["next_cursor"]},
            )
        ).json()
        assert len(audit_first["items"]) == 3
        assert len(audit_second["items"]) == 2
        assert {item["id"] for item in audit_first["items"]}.isdisjoint(
            item["id"] for item in audit_second["items"]
        )

        assert (await client.get("/api/audit/page", params={"cursor": "broken"})).status_code == 422

    await engine.dispose()


def test_cursor_round_trip_preserves_key():
    at = datetime(2026, 9, 15, 3, 4, 5, tzinfo=UTC)
    assert decode_cursor(encode_cursor(at, "row-id")) == (at, "row-id")
