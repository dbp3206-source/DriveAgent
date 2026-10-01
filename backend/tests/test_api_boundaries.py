"""HTTP boundary checks for provider routes, independent of provider SDKs."""

from types import SimpleNamespace

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.dependencies import get_current_user
from app.api.drive import router as drive_router
from app.api.gmail import router as gmail_router
from app.api.memory import router as memory_router
from app.api.rag import router as rag_router
from app.api.schemas import DriveFileListResponse
from app.api.sheets import router as sheets_router
from app.api.system import router as system_router
from app.core.config import get_settings
from app.db.models import Base, DriveFileIndex, LongTermMemory, User
from app.db.session import get_db
from app.services.rag import index_fingerprint


class RecordingRegistry:
    def __init__(self):
        self.calls = []

    async def execute(self, name, payload, context):
        self.calls.append((name, payload, context))
        if name in {"drive_list_files", "drive_search_files"}:
            return DriveFileListResponse(
                files=[
                    {
                        "id": "file-a",
                        "name": "Kế hoạch.md",
                        "mime_type": "text/markdown",
                        "modified_time": "2026-09-12T00:00:00Z",
                    }
                ]
            )
        if name == "drive_read_file":
            return {
                "file": {
                    "id": "file-a",
                    "name": "Kế hoạch.md",
                    "mime_type": "text/markdown",
                },
                "text": "Nội dung QA",
            }
        if name == "rag_index_drive_file":
            return {
                "file_id": payload["file_id"],
                "file_name": "Kế hoạch.md",
                "chunks": 1,
                "skipped": False,
                "message": "Đã lập chỉ mục.",
            }
        if name == "rag_search":
            return {"query": payload["query"], "citations": []}
        return {"data": {"state": "pending", "tool": name}}


async def test_gmail_write_boundary_rejects_cross_origin_and_keeps_read_route_available():
    app = FastAPI()
    app.include_router(gmail_router)
    registry = RecordingRegistry()
    app.state.registry = registry
    user = SimpleNamespace(id="user-a", role="owner")

    async def current_user():
        return user

    async def session():
        yield SimpleNamespace()

    @app.middleware("http")
    async def request_id(request, call_next):
        request.state.request_id = "api-boundary-request"
        return await call_next(request)

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db] = session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Read-only provider calls remain usable without a browser Origin header.
        response = await client.get("/api/gmail/messages")
        assert response.status_code == 200
        assert registry.calls[-1][0] == "gmail_list_messages"

        payload = {
            "request_key": "request_key_123",
            "draft": {
                "recipient": "qa@example.invalid",
                "subject": "QA",
                "body": "Boundary test",
            },
        }
        approval = {
            "operation_id": "11111111-1111-1111-1111-111111111111",
            "approved_digest": "a" * 64,
        }
        for path, body in (
            ("/api/gmail/draft", payload),
            ("/api/gmail/draft/approve", approval),
            ("/api/gmail/prepare", payload),
            ("/api/gmail/approve", approval),
        ):
            response = await client.post(
                path,
                headers={"Origin": "https://evil.invalid"},
                json=body,
            )
            assert response.status_code == 403, path
            assert registry.calls[-1][0] == "gmail_list_messages"

        response = await client.post(
            "/api/gmail/prepare",
            headers={"Origin": "http://localhost:8000"},
            json=payload,
        )
        assert response.status_code == 200
        assert registry.calls[-1][0] == "gmail_prepare_draft"
        assert registry.calls[-1][2].request_id == "api-boundary-request"


async def test_drive_and_rag_http_boundaries_preserve_tenant_index_state(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'api-boundary.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(drive_router)
    app.include_router(rag_router)
    registry = RecordingRegistry()
    app.state.registry = registry

    async with factory() as setup_db:
        owner = User(email="owner@test.invalid", display_name="Owner", role="owner")
        other = User(email="other@test.invalid", display_name="Other", role="owner")
        setup_db.add_all([owner, other])
        await setup_db.flush()
        setup_db.add_all(
            [
                DriveFileIndex(
                    user_id=owner.id,
                    drive_file_id="file-a",
                    name="Kế hoạch.md",
                    mime_type="text/markdown",
                    modified_time="2026-09-12T00:00:00Z",
                    content_hash=index_fingerprint("owner", get_settings()),
                    chunk_count=1,
                ),
                DriveFileIndex(
                    user_id=other.id,
                    drive_file_id="file-a",
                    name="Kế hoạch riêng.md",
                    mime_type="text/markdown",
                    modified_time="1999-01-01T00:00:00Z",
                    content_hash="b" * 64,
                    chunk_count=1,
                ),
            ]
        )
        await setup_db.commit()
        owner_id = owner.id

    async def current_user():
        async with factory() as db:
            return await db.get(User, owner_id)

    async def session():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db] = session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/drive/files", params={"query": "Kế hoạch"})
        assert response.status_code == 200
        assert response.json()["files"][0]["index_status"] == "fresh"
        assert registry.calls[-1][0] == "drive_search_files"

        response = await client.get("/api/drive/files/file-a/content")
        assert response.status_code == 200
        assert response.json()["text"] == "Nội dung QA"

        response = await client.post("/api/drive/files/file-a/index")
        assert response.status_code == 200
        assert registry.calls[-1][0] == "rag_index_drive_file"

        response = await client.post(
            "/api/rag/search", json={"query": "mục tiêu", "limit": 4}
        )
        assert response.status_code == 200
        assert registry.calls[-1][0] == "rag_search"
        assert registry.calls[-1][1]["limit"] == 4

        call_count = len(registry.calls)
        response = await client.post("/api/rag/search", json={"query": "x"})
        assert response.status_code == 422
        assert len(registry.calls) == call_count

    await engine.dispose()


async def test_memory_http_boundary_fails_closed_across_tenants(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'memory-boundary.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(memory_router)

    class VectorStore:
        def __init__(self):
            self.deleted = []

        async def delete_points(self, collection, ids):
            self.deleted.append((collection, ids))

    vectors = VectorStore()
    app.state.vector_store = vectors
    async with factory() as setup_db:
        owner = User(email="memory-owner@test.invalid", display_name="Owner", role="owner")
        other = User(email="memory-other@test.invalid", display_name="Other", role="owner")
        setup_db.add_all([owner, other])
        await setup_db.flush()
        owned = LongTermMemory(
            user_id=owner.id,
            kind="preference",
            content="Trả lời có checklist",
            normalized_hash="owned-memory",
        )
        private = LongTermMemory(
            user_id=other.id,
            kind="preference",
            content="Không được lộ",
            normalized_hash="private-memory",
        )
        setup_db.add_all([owned, private])
        await setup_db.commit()
        owner_id, owned_id, private_id = owner.id, owned.id, private.id

    async def current_user():
        async with factory() as db:
            return await db.get(User, owner_id)

    async def session():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db] = session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/memories")
        assert response.status_code == 200
        memories = response.json()["memories"]
        assert [item["id"] for item in memories] == [owned_id]
        assert "Không được lộ" not in response.text

        response = await client.patch(
            f"/api/memories/{private_id}", json={"is_archived": True}
        )
        assert response.status_code == 404

        response = await client.patch(
            f"/api/memories/{owned_id}", json={"content": "API_KEY=secret-value"}
        )
        assert response.status_code == 400

        response = await client.delete(f"/api/memories/{private_id}")
        assert response.status_code == 404
        assert vectors.deleted == []

        response = await client.delete(f"/api/memories/{owned_id}")
        assert response.status_code == 204
        assert vectors.deleted and vectors.deleted[0][1] == [owned_id]

    async with factory() as verify_db:
        assert await verify_db.get(LongTermMemory, owned_id) is None
        assert await verify_db.get(LongTermMemory, private_id) is not None
    await engine.dispose()


async def test_health_reports_vector_fallback_as_degraded():
    app = FastAPI()
    app.include_router(system_router)

    class Database:
        async def execute(self, _statement):
            return None

    async def session():
        yield Database()

    app.dependency_overrides[get_db] = session
    app.state.vector_store = SimpleNamespace(backend_name="qdrant-embedded")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        app.state.vector_store.backend_name = "postgres-pgvector"
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["vector_store"] == "postgres-pgvector"

        app.state.vector_store.backend_name = "sqlite-fallback"
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "degraded"
        assert response.json()["vector_store"] == "sqlite-fallback"


async def test_sheets_prepare_requires_trusted_ui_and_passes_typed_spec_to_registry():
    app = FastAPI()
    app.include_router(sheets_router)
    registry = RecordingRegistry()
    app.state.registry = registry
    user = SimpleNamespace(id="user-a", role="owner")

    async def current_user():
        return user

    async def session():
        yield SimpleNamespace()

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db] = session
    payload = {
        "request_key": "sheet_request_123",
        "action": "create",
        "spreadsheet": {
            "title": "Ngân sách QA",
            "tabs": [
                {
                    "title": "Chi phí",
                    "headers": ["Hạng mục", "Số tiền"],
                    "rows": [["Sách", 50000]],
                }
            ],
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/sheets/prepare",
            headers={"Origin": "https://evil.invalid"},
            json=payload,
        )
        assert response.status_code == 403
        assert registry.calls == []

        response = await client.post(
            "/api/sheets/prepare",
            headers={"Origin": "http://localhost:8000"},
            json=payload,
        )
        assert response.status_code == 200
        assert registry.calls[-1][0] == "sheets_prepare"
        assert registry.calls[-1][1]["spreadsheet"]["tabs"][0]["rows"] == [
            ["Sách", 50000]
        ]
