"""Exercise real HTTP routes against isolated SQLite, never the user's database."""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.artifacts import router as artifacts_router
from app.api.dependencies import get_current_user
from app.api.local_sources import router as sources_router
from app.db.models import Base, LocalSource, SavedArtifact, User
from app.db.session import get_db


@pytest.mark.asyncio
async def test_direct_links_enforce_tenant_role_and_safe_content_type(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'access.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(artifacts_router)
    app.include_router(sources_router)
    async with factory() as db:
        owner = User(email="owner@test.invalid", display_name="A", role="editor")
        other = User(email="other@test.invalid", display_name="B", role="editor")
        db.add_all([owner, other])
        await db.flush()
        artifact = SavedArtifact(
            user_id=owner.id,
            creation_key=str(uuid4()),
            title="Test",
            kind="note",
            content="<script>alert('inert')</script>",
        )
        source = LocalSource(
            user_id=owner.id,
            name="sample.md",
            content="Private fixture",
            content_hash="a" * 64,
        )
        db.add_all([artifact, source])
        await db.commit()
        actor = owner

        async def current_user():
            return actor

        async def session():
            yield db

        app.dependency_overrides[get_current_user] = current_user
        app.dependency_overrides[get_db] = session
        paths = [f"/api/artifacts/{artifact.id}/export", f"/api/local-sources/{source.id}/text"]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in paths:
                response = await client.get(path)
                assert response.status_code == 200
                assert response.headers["x-content-type-options"] == "nosniff"
                assert response.headers["cache-control"] == "no-store"
                assert "text/html" not in response.headers["content-type"]
            exported = await client.get(paths[0])
            assert exported.headers["content-disposition"].startswith("attachment;")
            actor = other
            for path in paths:
                assert (await client.get(path)).status_code == 404
            assert (await client.get("/api/local-sources")).json() == []
            # Owning a record is not sufficient when the role no longer grants access.
            actor = owner
            owner.role = "unknown-role"
            for path in [*paths, "/api/local-sources"]:
                assert (await client.get(path)).status_code == 403
    await engine.dispose()
