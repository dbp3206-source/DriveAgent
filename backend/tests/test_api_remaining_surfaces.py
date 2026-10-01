import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agent.orchestrator import AgentNotConfiguredError, AgentRunResult
from app.api import artifacts, audit, auth, chat, creation, local_sources, memory
from app.api.schemas import ChatRequest, SessionUpdateRequest
from app.core.config import Settings
from app.db.models import AuditEvent, Base, LongTermMemory, ProviderCredential, SavedArtifact, User
from app.services.artifacts import ArtifactWrite


async def _database(tmp_path, name: str):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / name}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _request(**state):
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(**state)),
        state=SimpleNamespace(request_id="r1"),
    )


@pytest.mark.asyncio
async def test_artifact_api_delegates_to_registry_and_exports_owned_markdown(tmp_path):
    engine, factory = await _database(tmp_path, "artifacts.db")
    registry = SimpleNamespace(execute=AsyncMock(return_value={"items": []}))
    settings = Settings(
        _env_file=None, database_url=f"sqlite+aiosqlite:///{tmp_path / 'artifacts.db'}"
    )
    request = _request(registry=registry)
    try:
        async with factory() as db:
            user = User(email="artifact@example.test", display_name="Artifact", role="editor")
            db.add(user)
            await db.flush()
            row = SavedArtifact(
                user_id=user.id,
                creation_key=str(uuid4()),
                title="Kế hoạch",
                content="- Việc 1",
                kind="plan",
            )
            db.add(row)
            await db.commit()
            with patch("app.core.config.get_settings", return_value=settings):
                assert await artifacts.listing(request, user, db) == {"items": []}
                payload = ArtifactWrite(
                    title="Ghi chú", content="Nội dung", creation_key=uuid4()
                )
                assert await artifacts.save(payload, request, user, db) == {"items": []}
            exported = await artifacts.export(row.id, user, db)
            assert exported.headers["content-disposition"].endswith(f'report-{row.id}.md"')
            assert b"# K" in exported.body
            with pytest.raises(HTTPException) as missing:
                await artifacts.export("missing", user, db)
            assert missing.value.status_code == 404
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_audit_api_filters_owned_rows_serializes_and_paginates(tmp_path):
    engine, factory = await _database(tmp_path, "audit.db")
    try:
        async with factory() as db:
            user = User(email="audit@example.test", display_name="Audit", role="editor")
            other = User(email="other@example.test", display_name="Other", role="editor")
            db.add_all([user, other])
            await db.flush()
            db.add_all(
                [
                    AuditEvent(
                        request_id="a1",
                        user_id=user.id,
                        user_email=user.email,
                        role=user.role,
                        tool_name="drive_read_file",
                        arguments_json="not-json",
                        result_json='{"ok": true}',
                        status="success",
                        created_at=datetime(2026, 9, 15, 9, tzinfo=UTC),
                    ),
                    AuditEvent(
                        request_id="a2",
                        user_id=other.id,
                        user_email=other.email,
                        role=other.role,
                        tool_name="gmail_list_messages",
                        status="error",
                        created_at=datetime(2026, 9, 15, 8, tzinfo=UTC),
                    ),
                ]
            )
            await db.commit()
            rows = await audit.list_audit_events(user, db, tool="drive_read_file", limit=10)
            assert len(rows) == 1 and rows[0].arguments == {}
            page = await audit.list_audit_page(user, db, limit=1)
            assert len(page.items) == 1 and page.next_cursor is None
            with pytest.raises(HTTPException) as invalid:
                await audit.list_audit_page(user, db, cursor="bad", limit=1)
            assert invalid.value.status_code == 422
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_local_source_upload_read_and_permission_guards(tmp_path):
    engine, factory = await _database(tmp_path, "local.db")

    async def body():
        yield b"# QA\nNoi dung tai lieu local."

    try:
        async with factory() as db:
            user = User(email="local@example.test", display_name="Local", role="editor")
            db.add(user)
            await db.commit()
            request = _request()
            request.stream = body
            created = await local_sources.upload("qa.md", request, user, db)
            assert created["characters"] > 10
            listed = await local_sources.listing(user, db)
            assert listed == [
                {"id": created["id"], "name": "qa.md", "characters": created["characters"]}
            ]
            content = await local_sources.read(created["id"], user, db)
            assert "Noi dung" in content.body.decode()
            with pytest.raises(HTTPException) as bad_name:
                await local_sources.upload("../bad.txt", request, user, db)
            assert bad_name.value.status_code == 400
            with pytest.raises(HTTPException) as no_file:
                await local_sources.read("missing", user, db)
            assert no_file.value.status_code == 404
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_memory_api_lists_updates_vectors_and_deletes_owned_memory(tmp_path):
    engine, factory = await _database(tmp_path, "memory-api.db")
    try:
        async with factory() as db:
            user = User(email="memory@example.test", display_name="Memory", role="editor")
            db.add(user)
            await db.flush()
            row = LongTermMemory(
                user_id=user.id,
                kind="preference",
                content="Trả lời bằng tiếng Việt",
                normalized_hash="initial",
                tags_json='["tone"]',
                embedding_json="[0.1]",
            )
            db.add(row)
            await db.commit()
            listed = await memory.list_memories(user, db)
            assert listed.memories[0].content == "Trả lời bằng tiếng Việt"
            embeddings = SimpleNamespace(settings=memory.get_settings(),
                                         embed=AsyncMock(return_value=[0.3, 0.4]))
            vector_store = SimpleNamespace(upsert=AsyncMock(), delete_points=AsyncMock())
            request = _request(embeddings=embeddings, vector_store=vector_store)
            updated = await memory.update_memory(
                row.id,
                memory.MemoryUpdateRequest(
                    content="Ưu tiên câu trả lời có bảng", tags=["format", "format"], confidence=0.8
                ),
                request,
                user,
                db,
            )
            assert updated.tags == ["format"]
            vector_store.upsert.assert_awaited_once()
            await memory.delete_memory(row.id, request, user, db)
            vector_store.delete_points.assert_awaited_once()
            with pytest.raises(HTTPException) as missing:
                await memory.delete_memory(row.id, request, user, db)
            assert missing.value.status_code == 404
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_creation_rejects_missing_and_retired_proposals_without_invoking_write_tools():
    user = SimpleNamespace(id="user-creation")
    db = AsyncMock()
    db.scalar.return_value = None
    with pytest.raises(HTTPException) as missing:
        await creation.prepare("missing", _request(), user, db)
    assert missing.value.status_code == 404

    db.scalar.return_value = SimpleNamespace(spec_json='{"kind":"slide"}', id="proposal")
    with pytest.raises(HTTPException) as retired:
        await creation.prepare("proposal", _request(), user, db)
    assert retired.value.status_code == 410


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw", "tool_name"),
    [
        (
            {
                "kind": "document",
                "document": {"title": "Kế hoạch", "blocks": [{"text": "Ôn tập"}]},
            },
            "docs_prepare",
        ),
        (
            {
                "kind": "spreadsheet",
                "spreadsheet": {
                    "title": "Chi tiêu",
                    "tabs": [{"title": "Tháng 9", "headers": ["Mục"], "rows": [["Sách"]]}],
                },
            },
            "sheets_prepare",
        ),
    ],
)
async def test_creation_prepares_only_the_persisted_document_or_sheet_proposal(raw, tool_name):
    db = AsyncMock()
    db.scalar.return_value = SimpleNamespace(id="proposal-1", spec_json=json.dumps(raw))
    user = SimpleNamespace(id="user-creation")
    request = _request()
    with patch("app.api.creation.invoke", AsyncMock(return_value={"state": "pending"})) as invoke:
        result = await creation.prepare("proposal-1", request, user, db)
    assert result == {"state": "pending"}
    assert invoke.await_args.args[0] == tool_name
    assert invoke.await_args.args[1].request_key == "proposal-1"


@pytest.mark.asyncio
async def test_auth_status_demo_login_google_start_and_logout_are_explicitly_guarded(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}",
        app_secret="x" * 32,
    )
    request = SimpleNamespace(session={})
    db = SimpleNamespace(
        get=AsyncMock(return_value=None),
        scalar=AsyncMock(return_value=None),
        commit=AsyncMock(),
    )
    db.add = MagicMock(side_effect=lambda row: setattr(row, "id", "demo-user"))
    status = await auth.auth_status(request, db, settings)
    assert status.authenticated is False
    with pytest.raises(HTTPException) as disabled:
        await auth.demo_login(request, db, settings)
    assert disabled.value.status_code == 404

    demo_settings = settings.model_copy(update={"enable_demo_login": True})
    db.scalar.return_value = None
    created = await auth.demo_login(request, db, demo_settings)
    assert created.email == "demo@driveagent.local"
    assert request.session["user_id"]

    with pytest.raises(HTTPException) as upgrade_before_login:
        await auth.google_login(SimpleNamespace(session={}), settings, capability="gmail")
    assert upgrade_before_login.value.status_code == 401

    flow = SimpleNamespace(code_verifier="verifier")
    flow.authorization_url = lambda **kwargs: (
        "https://accounts.google.com/consent",
        kwargs["state"],
    )
    oauth_request = SimpleNamespace(session={"user_id": "user-1"})
    with patch("app.api.auth.build_flow", return_value=flow):
        redirect = await auth.google_login(oauth_request, settings, capability="gmail")
    assert redirect.status_code == 307
    assert oauth_request.session["oauth_capability"] == "gmail"
    assert oauth_request.session["oauth_upgrade_user"] == "user-1"
    assert "oauth_pkce" in oauth_request.session

    # Reconnect keeps both existing optional capabilities in a single consent.
    with patch("app.api.auth.build_flow", return_value=flow) as flow_factory:
        await auth.google_login(oauth_request, settings, capability="reconnect")
    assert flow_factory.call_args.kwargs["workspace"] is True
    assert flow_factory.call_args.kwargs["gmail_compose"] is True

    await auth.logout(oauth_request)
    assert oauth_request.session == {}


@pytest.mark.asyncio
async def test_auth_status_counts_only_the_signed_in_users_active_byok_key(tmp_path):
    engine, factory = await _database(tmp_path, "auth-byok.db")
    settings = Settings(_env_file=None, gemini_api_key="", environment="development")
    try:
        async with factory() as db:
            owner = User(email="owner@example.test", display_name="Owner", role="editor")
            other = User(email="other@example.test", display_name="Other", role="editor")
            db.add_all([owner, other])
            await db.flush()
            db.add(
                ProviderCredential(
                    user_id=owner.id,
                    provider="gemini",
                    display_name="Owner key",
                    fingerprint="owner-key-fingerprint",
                    encrypted_secret="synthetic-not-decrypted",
                    is_active=True,
                )
            )
            db.add(
                ProviderCredential(
                    user_id=other.id,
                    provider="gemini",
                    display_name="Inactive key",
                    fingerprint="inactive-key-fingerprint",
                    encrypted_secret="synthetic-not-decrypted",
                    is_active=False,
                )
            )
            await db.commit()

            owner_status = await auth.auth_status(
                SimpleNamespace(session={"user_id": owner.id}), db, settings
            )
            other_status = await auth.auth_status(
                SimpleNamespace(session={"user_id": other.id}), db, settings
            )
            anonymous_status = await auth.auth_status(
                SimpleNamespace(session={}), db, settings
            )
            assert owner_status.authenticated is True
            assert owner_status.gemini_configured is True
            assert other_status.authenticated is True
            assert other_status.gemini_configured is False
            assert anonymous_status.authenticated is False
            assert anonymous_status.gemini_configured is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_chat_api_persists_success_keeps_history_and_handles_failed_turn(tmp_path):
    engine, factory = await _database(tmp_path, "chat-api.db")
    try:
        async with factory() as db:
            user = User(email="chat@example.test", display_name="Chat", role="editor")
            db.add(user)
            await db.commit()
            success = AgentRunResult(
                answer="## Kết luận\n\n- Đã hoàn thành.",
                plan=["Kiểm tra"],
                trace=[{"stage": "model", "status": "success"}],
                citations=[],
            )
            orchestrator = SimpleNamespace(run=AsyncMock(return_value=success))
            request = _request(orchestrator=orchestrator)
            payload = ChatRequest(message="/agent study Lập kế hoạch ôn tập")
            response = await chat.chat(payload, request, user, db)
            assert response.answer.startswith("## Kết luận")
            assert response.trace[0] == {
                "stage": "plan",
                "step_count": 1,
                "run_id": "r1",
            }
            orchestrator.run.assert_awaited_once()

            sessions = await chat.list_sessions(user, db)
            assert len(sessions) == 1
            session_id = sessions[0].id
            messages = await chat.list_messages(session_id, user, db)
            assert [message.role for message in messages] == ["user", "assistant"]
            page = await chat.list_messages_page(session_id, user, db, limit=1)
            assert len(page.items) == 1 and page.next_cursor
            renamed = await chat.update_session(
                session_id, SessionUpdateRequest(title="  Ôn tập  "), user, db
            )
            assert renamed.title == "Ôn tập"

            failed = SimpleNamespace(run=AsyncMock(side_effect=AgentNotConfiguredError("no key")))
            request.app.state.orchestrator = failed
            with pytest.raises(HTTPException) as unavailable:
                await chat.chat(ChatRequest(message="Cần trợ giúp"), request, user, db)
            assert unavailable.value.status_code == 503

            with pytest.raises(HTTPException) as unknown:
                await chat.list_messages("missing", user, db)
            assert unknown.value.status_code == 404
            with pytest.raises(HTTPException) as empty_command:
                await chat.chat(ChatRequest(message="/rag"), request, user, db)
            assert empty_command.value.status_code == 422

            await chat.delete_session(session_id, user, db)
            with pytest.raises(HTTPException) as deleted:
                await chat.delete_session(session_id, user, db)
            assert deleted.value.status_code == 404
    finally:
        await engine.dispose()
