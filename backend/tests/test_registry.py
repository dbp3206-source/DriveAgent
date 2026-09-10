from pathlib import Path

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.permissions import MEMORY_READ, MEMORY_WRITE
from app.core.config import Settings
from app.db.models import AuditEvent, Base, User, UserRole
from app.tools.contracts import ToolAccessDeniedError, ToolContext, ToolDefinition, ToolError
from app.tools.registry import ToolRegistry


class EchoInput(BaseModel):
    text: str = Field(min_length=2)


class EchoOutput(BaseModel):
    value: str


async def create_session(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


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
