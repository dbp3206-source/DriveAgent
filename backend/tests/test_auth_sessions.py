from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth
from app.api.dependencies import CurrentUser
from app.auth.sessions import establish_session
from app.core.config import Settings, get_settings
from app.db.models import Base, User
from app.db.session import get_db


async def test_logout_revokes_copied_cookies_across_clients_but_not_other_users(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        first = User(email="first@example.test", display_name="First", role="editor")
        second = User(email="second@example.test", display_name="Second", role="editor")
        db.add_all([first, second])
        await db.commit()
        ids = [first.id, second.id]

    settings = Settings(_env_file=None, environment="development", gemini_api_key="")
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="synthetic-session-test-secret")
    app.include_router(auth.router)

    async def database():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_settings] = lambda: settings

    @app.post("/test-login/{index}")
    async def login(index: int, request: Request):
        async with factory() as db:
            user = await db.get(User, ids[index])
            establish_session(request.session, user)
            await db.commit()
        return {"ok": True}

    @app.get("/protected")
    async def protected(user: CurrentUser):
        return {"user_id": user.id}

    @app.post("/legacy-cookie")
    async def legacy(request: Request):
        request.session.update(user_id=ids[0])
        return {"ok": True}

    try:
        with TestClient(app) as owner, TestClient(app) as another_session, TestClient(app) as other:
            assert owner.post("/test-login/0").status_code == 200
            assert another_session.post("/test-login/0").status_code == 200
            assert other.post("/test-login/1").status_code == 200
            copied = owner.cookies.get("session")
            assert owner.get("/protected").json()["user_id"] == ids[0]
            assert owner.get("/api/auth/status").json()["authenticated"]
            assert owner.post("/api/auth/logout").status_code == 204
            assert another_session.get("/protected").status_code == 401
            assert other.get("/protected").json()["user_id"] == ids[1]
            with TestClient(app) as replay:
                replay.cookies.set("session", copied)
                assert replay.get("/api/auth/status").json()["authenticated"] is False
                replay.cookies.set("session", copied)
                assert replay.get("/protected").status_code == 401
                # Replaying a stale logout must not terminate a fresh login.
                assert owner.post("/test-login/0").status_code == 200
                replay.cookies.set("session", copied)
                assert replay.post("/api/auth/logout").status_code == 204
                assert owner.get("/protected").status_code == 200
            with TestClient(app) as legacy_client:
                legacy_client.post("/legacy-cookie")
                assert legacy_client.get("/protected").status_code == 401
    finally:
        await engine.dispose()
