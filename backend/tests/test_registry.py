from pathlib import Path

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.permissions import MEMORY_READ, MEMORY_WRITE
from app.core.config import Settings
from app.db.models import AuditEvent, Base, User, UserRole
from app.tools.contracts import ToolAccessDeniedError, ToolContext, ToolDefinition, ToolError
from app.tools.documents import document_tool_definitions
from app.tools.gmail import gmail_tool_definitions
from app.tools.registry import ToolRegistry
from app.tools.sheets import spreadsheet_tool_definitions


class EchoInput(BaseModel):
    text: str = Field(min_length=2)


class EchoOutput(BaseModel):
    value: str


def test_gmail_compose_scope_satisfies_send_but_not_readonly() -> None:
    """Compose includes sending, but must not grant mailbox read access."""
    scopes = {"https://www.googleapis.com/auth/gmail.compose"}
    assert ToolRegistry._is_oauth_scope_satisfied(
        "https://www.googleapis.com/auth/gmail.send", scopes
    )
    assert not ToolRegistry._is_oauth_scope_satisfied(
        "https://www.googleapis.com/auth/gmail.readonly", scopes
    )


async def create_session(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


def test_beta_cloud_write_markers_cover_only_execution_not_preview_or_readback():
    definitions = {
        item.name: item
        for item in [
            *document_tool_definitions(),
            *spreadsheet_tool_definitions(),
            *gmail_tool_definitions(),
        ]
    }
    assert {name for name, item in definitions.items() if item.external_write} == {
        "docs_execute", "sheets_execute", "gmail_create_draft", "gmail_send"
    }


@pytest.mark.asyncio
async def test_closed_beta_cloud_write_gate_blocks_handler_and_audits(tmp_path):
    engine, factory = await create_session(tmp_path)
    registry = ToolRegistry()
    called = []

    async def handler(payload, _context):
        called.append(payload.text)
        return EchoOutput(value=payload.text)

    registry.register(
        ToolDefinition(
            name="cloud_write_simulation",
            description="Test cloud write gate",
            input_model=EchoInput,
            output_model=EchoOutput,
            handler=handler,
            required_permissions={MEMORY_WRITE},
            external_write=True,
        )
    )
    async with factory() as db:
        user = User(email="beta@test.invalid", display_name="Beta", role="editor")
        db.add(user)
        await db.commit()
        denied = ToolContext(
            request_id="beta-denied", user=user, db=db,
            settings=Settings(environment="production", beta_allow_external_writes=False),
        )
        with pytest.raises(ToolAccessDeniedError, match="chỉ đọc"):
            await registry.execute("cloud_write_simulation", {"text": "write"}, denied)
        assert called == []
        audit = await db.scalar(select(AuditEvent).where(AuditEvent.request_id == "beta-denied"))
        assert audit.status == "denied"

        allowed = ToolContext(
            request_id="beta-allowed", user=user, db=db,
            settings=Settings(environment="production", beta_allow_external_writes=True),
        )
        await registry.execute("cloud_write_simulation", {"text": "write"}, allowed)
        assert called == ["write"]
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["agent", "adk", "api"])
async def test_explicit_action_gate_is_enforced_and_audited(tmp_path, source):
    engine, factory = await create_session(tmp_path)
    registry = ToolRegistry()
    called = []

    async def handler(payload, _context):
        called.append(True)
        return EchoOutput(value=payload.text)

    registry.register(
        ToolDefinition(
            name="explicit_save",
            description="Test",
            input_model=EchoInput,
            output_model=EchoOutput,
            handler=handler,
            required_permissions={MEMORY_WRITE},
            requires_user_action=True,
        )
    )
    async with factory() as db:
        user = User(email="gate@test.invalid", display_name="Test", role="editor")
        db.add(user)
        await db.commit()
        context = ToolContext(
            request_id="gate", user=user, db=db, settings=Settings(), source=source
        )
        if source == "api":
            await registry.execute("explicit_save", {"text": "hello"}, context)
            assert called == [True]
        else:
            with pytest.raises(ToolAccessDeniedError):
                await registry.execute("explicit_save", {"text": "hello"}, context)
            assert not called
        audit = await db.scalar(select(AuditEvent).where(AuditEvent.request_id == "gate"))
        assert audit.status == ("success" if source == "api" else "denied")
    await engine.dispose()


@pytest.mark.asyncio
async def test_registry_executes_and_writes_completed_audit(tmp_path: Path) -> None:
    engine, factory = await create_session(tmp_path)
    registry = ToolRegistry()

    async def echo(payload: EchoInput, _context: ToolContext) -> EchoOutput:
        return EchoOutput(value=payload.text.upper())

    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo test",
            input_model=EchoInput,
            output_model=EchoOutput,
            handler=echo,
            required_permissions={MEMORY_READ},
        )
    )
    async with factory() as db:
        user = User(email="linh@example.com", display_name="Linh", role=UserRole.EDITOR.value)
        db.add(user)
        await db.commit()
        result = await registry.execute(
            "echo",
            {"text": "xin chào"},
            ToolContext(
                request_id="request-1",
                user=user,
                db=db,
                settings=Settings(),
            ),
        )
        audit = await db.scalar(select(AuditEvent).where(AuditEvent.request_id == "request-1"))

        assert result.value == "XIN CHÀO"
        assert audit is not None
        assert audit.status == "success"
        assert audit.latency_ms is not None
        assert "xin chào" not in audit.arguments_json.lower()
        assert "xin chào" not in audit.result_json.lower()
        assert "XIN CHÀO" not in audit.result_json
        assert '"argument_count": 1' in audit.arguments_json
    await engine.dispose()


@pytest.mark.asyncio
async def test_registry_audits_missing_role_permission(tmp_path: Path) -> None:
    engine, factory = await create_session(tmp_path)
    registry = ToolRegistry()

    async def handler(_payload: EchoInput, _context: ToolContext) -> EchoOutput:
        return EchoOutput(value="never")

    registry.register(
        ToolDefinition(
            name="write_memory",
            description="Permission test",
            input_model=EchoInput,
            output_model=EchoOutput,
            handler=handler,
            required_permissions={MEMORY_WRITE},
        )
    )
    async with factory() as db:
        user = User(email="an@example.com", display_name="An", role=UserRole.VIEWER.value)
        db.add(user)
        await db.commit()
        with pytest.raises(ToolAccessDeniedError):
            await registry.execute(
                "write_memory",
                {"text": "hello"},
                ToolContext(request_id="request-2", user=user, db=db, settings=Settings()),
            )
        audit = await db.scalar(select(AuditEvent).where(AuditEvent.request_id == "request-2"))
        assert audit is not None
        assert audit.status == "denied"
        assert audit.error_type == "access_denied"
    await engine.dispose()


@pytest.mark.asyncio
async def test_registry_audits_invalid_arguments_without_calling_handler(tmp_path: Path) -> None:
    engine, factory = await create_session(tmp_path)
    registry = ToolRegistry()
    called = False

    async def handler(_payload: EchoInput, _context: ToolContext) -> EchoOutput:
        nonlocal called
        called = True
        return EchoOutput(value="never")

    registry.register(
        ToolDefinition(
            name="validated_tool",
            description="Schema audit test",
            input_model=EchoInput,
            output_model=EchoOutput,
            handler=handler,
            required_permissions={MEMORY_READ},
        )
    )
    async with factory() as db:
        user = User(email="schema@example.com", display_name="Schema", role="editor")
        db.add(user)
        await db.commit()

        with pytest.raises(ToolError) as invalid:
            await registry.execute(
                "validated_tool",
                {"text": "x"},
                ToolContext(request_id="request-invalid", user=user, db=db, settings=Settings()),
            )

        audit = await db.scalar(
            select(AuditEvent).where(AuditEvent.request_id == "request-invalid")
        )
        assert invalid.value.code == "invalid_arguments"
        assert called is False
        assert audit is not None
        assert audit.status == "error"
        assert audit.error_type == "invalid_arguments"
        assert audit.error_message == "Tool không hoàn tất; xem mã lỗi và request ID."
    await engine.dispose()


@pytest.mark.asyncio
async def test_tool_error_text_never_enters_metadata_audit(tmp_path: Path) -> None:
    engine, factory = await create_session(tmp_path)
    registry = ToolRegistry()

    async def handler(_payload: EchoInput, _context: ToolContext) -> EchoOutput:
        raise ToolError("private-document-canary", code="provider_failure")

    registry.register(
        ToolDefinition(
            name="read_private_document",
            description="Privacy audit test",
            input_model=EchoInput,
            output_model=EchoOutput,
            handler=handler,
            required_permissions={MEMORY_READ},
        )
    )
    async with factory() as db:
        user = User(email="private@example.com", display_name="Private", role="editor")
        db.add(user)
        await db.commit()
        with pytest.raises(ToolError):
            await registry.execute(
                "read_private_document",
                {"text": "private-request-canary"},
                ToolContext(request_id="privacy-request", user=user, db=db, settings=Settings()),
            )
        audit = await db.scalar(
            select(AuditEvent).where(AuditEvent.request_id == "privacy-request")
        )
        assert audit is not None
        assert audit.error_type == "provider_failure"
        assert "private-request-canary" not in audit.arguments_json
        assert "private-document-canary" not in audit.error_message
    await engine.dispose()


@pytest.mark.asyncio
async def test_registry_retries_only_retryable_errors(tmp_path: Path) -> None:
    engine, factory = await create_session(tmp_path)
    registry = ToolRegistry()
    attempts = 0

    async def flaky(payload: EchoInput, _context: ToolContext) -> EchoOutput:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ToolError("temporary", code="temporary", retryable=True)
        return EchoOutput(value=payload.text)

    registry.register(
        ToolDefinition(
            name="flaky",
            description="Retry test",
            input_model=EchoInput,
            output_model=EchoOutput,
            handler=flaky,
            required_permissions={MEMORY_READ},
            max_attempts=3,
        )
    )
    async with factory() as db:
        user = User(email="mai@example.com", display_name="Mai", role=UserRole.EDITOR.value)
        db.add(user)
        await db.commit()
        result = await registry.execute(
            "flaky",
            {"text": "done"},
            ToolContext(request_id="request-3", user=user, db=db, settings=Settings()),
        )
        assert result.value == "done"
        assert attempts == 3
    await engine.dispose()


@pytest.mark.asyncio
async def test_registry_redacts_platform_transport_error_from_user(tmp_path: Path, caplog) -> None:
    engine, factory = await create_session(tmp_path)
    registry = ToolRegistry()

    async def broken_transport(_payload: EchoInput, _context: ToolContext) -> EchoOutput:
        raise OSError("[WinError 10013] https://private.example/?token=secret-transport-canary")

    registry.register(
        ToolDefinition(
            name="broken_transport",
            description="Transport error test",
            input_model=EchoInput,
            output_model=EchoOutput,
            handler=broken_transport,
            required_permissions={MEMORY_READ},
            max_attempts=1,
        )
    )
    async with factory() as db:
        user = User(email="transport@example.com", display_name="Transport", role="editor")
        db.add(user)
        await db.commit()
        with pytest.raises(ToolError) as failure:
            await registry.execute(
                "broken_transport",
                {"text": "hello"},
                ToolContext(
                    request_id="request-transport", user=user, db=db, settings=Settings()
                ),
            )
        assert failure.value.code == "connection_error"
        assert "WinError" not in str(failure.value)
        assert "kiểm tra kết nối mạng" in str(failure.value)
        assert "secret-transport-canary" not in caplog.text
        assert "private.example" not in caplog.text
        assert "request-transport" in caplog.text
        audit = await db.scalar(
            select(AuditEvent).where(AuditEvent.request_id == "request-transport")
        )
        assert audit is not None
        assert audit.error_type == "connection_error"
        assert "WinError" not in (audit.error_message or "")
    await engine.dispose()


@pytest.mark.asyncio
async def test_registry_rolls_back_uncommitted_tool_changes_on_failure(tmp_path: Path) -> None:
    """Audit commit không được vô tình commit phần nghiệp vụ mà handler làm dở."""

    engine, factory = await create_session(tmp_path)
    registry = ToolRegistry()

    async def failing_handler(_payload: EchoInput, context: ToolContext) -> EchoOutput:
        context.user.display_name = "Tên bị sửa dở"
        raise ToolError("permanent failure", code="bad_request", retryable=False)

    registry.register(
        ToolDefinition(
            name="failing_write",
            description="Rollback test",
            input_model=EchoInput,
            output_model=EchoOutput,
            handler=failing_handler,
            required_permissions={MEMORY_WRITE},
            max_attempts=1,
        )
    )
    async with factory() as db:
        user = User(email="rollback@example.com", display_name="Tên ban đầu", role="editor")
        db.add(user)
        await db.commit()
        user_id = user.id
        with pytest.raises(ToolError, match="permanent failure"):
            await registry.execute(
                "failing_write",
                {"text": "change"},
                ToolContext(request_id="request-rollback", user=user, db=db, settings=Settings()),
            )

        db.expire_all()
        stored_user = await db.get(User, user_id)
        audit = await db.scalar(
            select(AuditEvent).where(AuditEvent.request_id == "request-rollback")
        )
        assert stored_user is not None
        assert stored_user.display_name == "Tên ban đầu"
        assert audit is not None
        assert audit.status == "error"
        assert audit.error_type == "bad_request"
    await engine.dispose()
