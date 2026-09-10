"""Test suite for Gmail tools, 2-phase human approval, and Morning Briefing service."""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import Base, User, UserRole
from app.services.operations import OperationStore
from app.tools.contracts import ToolContext, ToolError
from app.tools.gmail import (
    EmailApprovalInput,
    EmailDraftSpec,
    EmailPrepareInput,
    gmail_prepare_draft,
    gmail_send,
    gmail_tool_definitions,
)


def test_gmail_tool_definitions_registered():
    defs = gmail_tool_definitions()
    names = {d.name for d in defs}
    assert "gmail_list_messages" in names
    assert "gmail_read_thread" in names
    assert "gmail_prepare_draft" in names
    assert "gmail_send" in names


@pytest.mark.asyncio
async def test_gmail_prepare_and_approve_two_phase_flow(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", gemini_api_key=""
    )
    user = User(
        id="user-gmail-qa",
        email="dbp3206@gmail.com",
        display_name="QA User",
        role=UserRole.SUPER_ADMIN.value,
    )

    async with factory() as db:
        context = ToolContext(request_id="req-gmail-1", user=user, db=db, settings=settings)

        # 1. Prepare draft
        prep_input = EmailPrepareInput(
            request_key="req-gmail-test-1",
            draft=EmailDraftSpec(
                recipient="test@example.com",
                subject="Báo cáo tiến độ",
                body="Xin chào, đây là nội dung email tiến độ.",
            ),
        )
        prep_res = await gmail_prepare_draft(prep_input, context)
        assert prep_res.data["state"] == "pending"
        assert len(prep_res.data["digest"]) == 64  # SHA-256 hex string
        operation_id = prep_res.data["operation_id"]

        # Check operations.db recorded the pending draft
        store = OperationStore(tmp_path / "operations.db")
        op = store.get(user.id, operation_id)
        assert op["state"] == "pending"
        assert op["digest"] == prep_res.data["digest"]

        # 2. Tampered digest must fail
        with pytest.raises(ToolError, match="không khớp"):
            await gmail_send(
                EmailApprovalInput(
                    operation_id=operation_id,
                    approved_digest="0" * 64,
                ),
                context,
            )

    await engine.dispose()
