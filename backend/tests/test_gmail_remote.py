"""Unit tests for Gmail Remote Service and Remote Action Signer."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.gmail_remote import _confirmation_page, _result_page
from app.core.config import Settings
from app.db.models import User
from app.services.gmail_remote import (
    GmailRemoteService,
    RemoteActionLedger,
    RemoteActionSigner,
    reply_draft_body,
)
from app.tools.contracts import ToolError
from app.tools.registry import ToolRegistry


def test_remote_gmail_pages_and_default_draft_use_veridra_brand():
    confirmation = _confirmation_page("opaque", "Xác nhận", "<p>Nội dung xem trước</p>")
    result = _result_page("Hoàn tất", "Đã lưu bản nháp.")

    assert "<title>Veridra · Xác nhận</title>" in confirmation.body.decode()
    assert "<title>Veridra · Trạng thái</title>" in result.body.decode()
    assert reply_draft_body("user@example.com", "Xin chào").endswith("Veridra")


def test_remote_action_signer_valid():
    secret = "test-secret-key-12345"
    payload = {"thread_id": "t123", "subject": "Test Subject"}
    token = RemoteActionSigner.sign_action(
        "create_reply_draft", payload, "user-1", secret, ttl_seconds=300
    )

    decoded = RemoteActionSigner.verify_action(token, secret)
    assert decoded["action"] == "create_reply_draft"
    assert decoded["payload"]["thread_id"] == "t123"
    assert decoded["user_id"] == "user-1"
    assert len(decoded["nonce"]) == 32


def test_remote_action_signer_invalid_signature():
    secret = "test-secret-key-12345"
    payload = {"thread_id": "t123"}
    token = RemoteActionSigner.sign_action("create_reply_draft", payload, "user-1", secret)

    # Tamper with signature
    parts = token.split(".")
    tampered_token = f"{parts[0]}.wrongsignature"

    with pytest.raises(ToolError) as exc_info:
        RemoteActionSigner.verify_action(tampered_token, secret)
    assert "Chữ ký" in str(exc_info.value) or "invalid_signature" in exc_info.value.code


def test_remote_action_signer_expired():
    secret = "test-secret-key-12345"
    payload = {"thread_id": "t123"}
    token = RemoteActionSigner.sign_action(
        "create_reply_draft", payload, "user-1", secret, ttl_seconds=-10
    )

    with pytest.raises(ToolError) as exc_info:
        RemoteActionSigner.verify_action(token, secret)
    assert "hết hạn" in str(exc_info.value) or "token_expired" in exc_info.value.code


def test_remote_action_ledger_rejects_replay(tmp_path):
    ledger = RemoteActionLedger(tmp_path / "remote_actions.db")
    ledger.consume("a" * 32, int(time.time()) + 60)
    with pytest.raises(ToolError) as exc_info:
        ledger.consume("a" * 32, int(time.time()) + 60)
    assert exc_info.value.code == "remote_action_replayed"


def test_urgency_scoring():
    settings = Settings(_env_file=None)
    registry = ToolRegistry()
    service = GmailRemoteService(settings, registry)

    # Normal email
    score, reasons = service.score_urgency(
        "Thảo luận kế hoạch", "Nội dung bình thường", "partner@example.com"
    )
    assert score == 1
    assert len(reasons) == 0

    # Urgent email
    score_urgent, reasons_urgent = service.score_urgency(
        "Báo cáo khẩn cấp về deadline quý 1?",
        "Cần phê duyệt gấp ngay hôm nay",
        "boss@example.com",
    )
    assert score_urgent >= 5
    assert any("khẩn" in r for r in reasons_urgent)


@pytest.mark.asyncio
async def test_execute_remote_token_create_reply(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'remote_service.db'}",
    )
    registry = ToolRegistry()

    # Mock registry.execute for gmail_create_draft
    mock_output = MagicMock()
    mock_output.draft_id = "draft-remote-999"
    mock_output.gmail_draft_url = "https://mail.google.com/mail/u/0/#drafts"
    registry.execute = AsyncMock(return_value=mock_output)

    service = GmailRemoteService(settings, registry)

    # Mock DB and User
    mock_user = User(id="u123", email="user@example.com", display_name="Bao Phuc", is_active=True)
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_user)

    token = RemoteActionSigner.sign_action(
        "create_reply_draft",
        {
            "thread_id": "thread-1",
            "recipient": "boss@example.com",
            "subject": "Re: Khẩn",
            "source_snippet": "Báo cáo đâu?",
        },
        "u123",
        settings.app_secret,
    )

    result = await service.execute_remote_token(token, mock_db, "req-1")
    assert result["status"] == "success"
    assert result["draft_id"] == "draft-remote-999"
    assert "mail.google.com" in result["gmail_draft_url"]
    assert registry.execute.await_args.args[0] == "gmail_create_draft"
    assert registry.execute.await_args.args[1]["operation_id"]
    with pytest.raises(ToolError) as exc_info:
        await service.execute_remote_token(token, mock_db, "req-2")
    assert exc_info.value.code == "remote_action_replayed"


@pytest.mark.asyncio
async def test_gmail_remote_api_routes(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.api.gmail_remote import router as gmail_remote_router
    from app.db.models import Base
    from app.db.session import get_db

    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'remote_app.db'}",
    )
    monkeypatch.setattr("app.api.gmail_remote.get_settings", lambda: settings)

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'remote_test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        user = User(
            id="user-remote-1",
            email="remote@example.com",
            display_name="Remote User",
            is_active=True,
        )
        db.add(user)
        await db.commit()

    app = FastAPI()
    app.include_router(gmail_remote_router)

    async def request_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = request_db

    registry = ToolRegistry()
    mock_output = MagicMock()
    mock_output.draft_id = "draft-api-123"
    mock_output.gmail_draft_url = "https://mail.google.com/mail/u/0/#drafts"
    registry.execute = AsyncMock(return_value=mock_output)
    app.state.registry = registry

    token = RemoteActionSigner.sign_action(
        "create_reply_draft",
        {
            "thread_id": "t-api",
            "recipient": "colleague@example.com",
            "subject": "Re: Trao đổi",
            "source_snippet": "<script>alert(1)</script>",
            "display_name": "Remote User",
        },
        "user-remote-1",
        settings.app_secret,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET renders a confirmation and performs no write.
        get_res = await client.get(f"/api/gmail/remote/action/run?token={token}")
        assert get_res.status_code == 200
        assert "Xác nhận thao tác này" in get_res.text
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in get_res.text
        assert registry.execute.await_count == 0

        # A deliberate form POST is the approval step and can run only once.
        confirm_res = await client.post("/api/gmail/remote/action/confirm", data={"token": token})
        assert confirm_res.status_code == 200
        assert "Đã tạo thư nháp trả lời thành công" in confirm_res.text
        assert "mail.google.com" in confirm_res.text
        replay_res = await client.post("/api/gmail/remote/action/confirm", data={"token": token})
        assert replay_res.status_code == 409
        assert registry.execute.await_count == 1

        # The placeholder webhook must not claim to have accepted an event.
        hook_res = await client.post("/api/gmail/remote/webhook")
        assert hook_res.status_code == 501
    await engine.dispose()
