import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from google.genai.errors import ClientError, ServerError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agent.controls import ChatControls
from app.agent.orchestrator import AgentNotConfiguredError, AgentRunResult
from app.agent.routing import Route
from app.api.chat import _failed_task_diagnostic, _gmail_followup_route, chat
from app.api.schemas import ChatRequest
from app.db.models import AuditEvent, Base, ChatSession, CreationProposalRecord, Message, User
from app.tools.contracts import ToolError


class FailingOrchestrator:
    async def run(self, **_kwargs):
        raise AgentNotConfiguredError("No model")


class TransportFailingOrchestrator:
    async def run(self, **_kwargs):
        raise httpx.ConnectError("Gemini unavailable")


class SocketPermissionFailingOrchestrator:
    async def run(self, **_kwargs):
        raise PermissionError(5, "Provider socket denied")


class ProviderOverloadOrchestrator:
    async def run(self, **_kwargs):
        raise ServerError(503, {"error": {"message": "temporarily overloaded"}})


class ProviderDeadlineOrchestrator:
    async def run(self, **_kwargs):
        raise ServerError(504, {"error": {"message": "deadline exceeded"}})


class ProviderConfigurationOrchestrator:
    async def run(self, **_kwargs):
        raise ClientError(400, {"error": {"message": "invalid request configuration"}})


class CapturingOrchestrator:
    def __init__(self):
        self.calls = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        return AgentRunResult(
            answer="Đã liệt kê.",
            plan=[],
            trace=[],
            citations=[],
        )


class IncompleteOrchestrator:
    async def run(self, **_kwargs):
        return AgentRunResult(
            answer="Bản nháp ngắn chưa đủ yêu cầu.",
            plan=[],
            trace=[
                {
                    "stage": "output_contract",
                    "status": "degraded",
                    "violations": ["below_explicit_word_minimum"],
                }
            ],
            citations=[],
            # A deliberately malformed proposal must not cross the persistence
            # boundary when the presentation contract has already failed.
            proposals=[{"kind": "invalid", "untrusted": True}],
        )


class PrivateTraceOrchestrator:
    async def run(self, **_kwargs):
        return AgentRunResult(
            answer="Safe answer",
            plan=[],
            trace=[
                {
                    "stage": "planning",
                    "status": "success",
                    "steps": ["private-gmail-canary"],
                    "note": "private-gmail-canary",
                }
            ],
            citations=[],
        )


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (ServerError(503, {"error": {"message": "private-email-canary"}}), "provider_unavailable"),
        (httpx.ConnectError("private-email-canary"), "provider_transport"),
        (ToolError("private-email-canary", code="access_denied"), "application_guard"),
    ],
)
def test_failed_task_diagnostic_classifies_without_leaking_exception_text(error, category):
    message, data = _failed_task_diagnostic(error, "failed")
    assert data["failure_category"] == category
    assert "private-email-canary" not in message
    assert "private-email-canary" not in json.dumps(data)


async def test_failed_new_turn_preserves_prompt_with_explicit_failed_status(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email="atomic@example.com", display_name="Atomic", role="editor")
        db.add(user)
        await db.commit()
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="atomic-request"),
            app=SimpleNamespace(state=SimpleNamespace(orchestrator=FailingOrchestrator())),
        )
        with pytest.raises(HTTPException) as error:
            await chat(ChatRequest(message="retry me"), request, user, db)
        assert error.value.status_code == 503
        assert await db.scalar(select(func.count()).select_from(Message)) == 1
        assert await db.scalar(select(func.count()).select_from(ChatSession)) == 1
        row = await db.scalar(select(Message))
        assert row is not None
        assert row.content == "retry me"
        assert row.status == "failed"
    await engine.dispose()

async def test_transport_failure_returns_actionable_provider_message(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat-transport.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email="transport@example.com", display_name="Transport", role="editor")
        db.add(user)
        await db.commit()
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="transport-request"),
            app=SimpleNamespace(state=SimpleNamespace(orchestrator=TransportFailingOrchestrator())),
        )
        with pytest.raises(HTTPException) as error:
            await chat(ChatRequest(message="network check"), request, user, db)
        assert error.value.status_code == 503
        assert "Không kết nối được Gemini" in str(error.value.detail)
        assert "transport-request" in str(error.value.detail)
        row = await db.scalar(select(Message))
        assert row is not None
        assert row.status == "failed"
    await engine.dispose()


async def test_transport_failure_after_expiring_commit_never_masks_as_http_500(tmp_path):
    """Regression for the live rollback/MissingGreenlet failure path."""

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat-expired.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=True)
    async with factory() as db:
        user = User(email="expired@example.com", display_name="Expired", role="editor")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="expired-request"),
            app=SimpleNamespace(
                state=SimpleNamespace(orchestrator=SocketPermissionFailingOrchestrator())
            ),
        )
        with pytest.raises(HTTPException) as error:
            await chat(ChatRequest(message="provider network check"), request, user, db)
        assert error.value.status_code == 503
        assert "Không kết nối được Gemini" in str(error.value.detail)
        row = await db.scalar(select(Message))
        assert row is not None and row.status == "failed"
        audit = await db.scalar(select(AuditEvent))
        assert audit is not None
        assert json.loads(audit.result_json)["failure_category"] == "provider_transport"
    await engine.dispose()


async def test_provider_503_is_not_misreported_as_drive_health_or_quota(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat-provider-503.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email="provider@example.com", display_name="Provider", role="editor")
        db.add(user)
        await db.commit()
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="provider-request"),
            app=SimpleNamespace(
                state=SimpleNamespace(orchestrator=ProviderOverloadOrchestrator())
            ),
        )
        with pytest.raises(HTTPException) as error:
            await chat(ChatRequest(message="synthetic provider check"), request, user, db)
        assert error.value.status_code == 503
        assert "không xác nhận" in error.value.detail
        assert "Drive vẫn dùng được" not in error.value.detail
        assert "provider-request" in error.value.detail
    await engine.dispose()


async def test_provider_504_explains_timeout_without_claiming_quota_exhaustion(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat-provider-504.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email="deadline@example.com", display_name="Deadline", role="editor")
        db.add(user)
        await db.commit()
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="deadline-request"),
            app=SimpleNamespace(state=SimpleNamespace(orchestrator=ProviderDeadlineOrchestrator())),
        )
        with pytest.raises(HTTPException) as error:
            await chat(ChatRequest(message="synthetic timeout check"), request, user, db)
        assert error.value.status_code == 503
        assert "quá thời hạn" in error.value.detail
        assert "không phải bằng chứng hết quota" in error.value.detail
        assert "deadline-request" in error.value.detail
        row = await db.scalar(select(Message))
        assert row is not None and row.status == "failed"
        audit = await db.scalar(select(AuditEvent))
        assert audit is not None
        assert json.loads(audit.result_json) == {
            "failure_category": "provider_timeout",
            "provider_code": 504,
        }
        assert "quota" in (audit.error_message or "")
        assert "deadline exceeded" not in (audit.error_message or "")
    await engine.dispose()


async def test_provider_400_is_not_replayed_against_alternate_key(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat-provider-400.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    alternate = CapturingOrchestrator()
    async with factory() as db:
        user = User(email="configuration@example.com", display_name="Configuration", role="editor")
        db.add(user)
        await db.commit()
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="configuration-request"),
            app=SimpleNamespace(
                state=SimpleNamespace(
                    orchestrator=ProviderConfigurationOrchestrator(),
                    resolve_user_alternate_orchestrator=lambda *_args: alternate,
                )
            ),
        )
        with pytest.raises(HTTPException) as error:
            await chat(ChatRequest(message="synthetic configuration check"), request, user, db)
        assert error.value.status_code == 502
        assert "định dạng yêu cầu" in error.value.detail
        assert alternate.calls == []
        audit = await db.scalar(select(AuditEvent))
        assert audit is not None
        assert json.loads(audit.result_json)["failure_category"] == "provider_configuration"
    await engine.dispose()


async def test_chat_boundary_applies_typed_commands_and_persists_clean_message(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat-controls.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    orchestrator = CapturingOrchestrator()
    async with factory() as db:
        user = User(email="controls@example.com", display_name="Controls", role="editor")
        db.add(user)
        await db.commit()
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="controls-request"),
            app=SimpleNamespace(state=SimpleNamespace(orchestrator=orchestrator)),
        )

        response = await chat(
            ChatRequest(message="/drive /research Liệt kê ba tệp gần đây."),
            request,
            user,
            db,
        )

        assert response.answer == "Đã liệt kê."
        assert len(orchestrator.calls) == 1
        call = orchestrator.calls[0]
        assert call["user_message"] == "Liệt kê ba tệp gần đây."
        assert call["controls"] == ChatControls(source="drive", agent="research")
        session = await db.get(ChatSession, response.session_id)
        assert session is not None
        assert session.title == "Liệt kê ba tệp gần đây."
        rows = list(
            (
                await db.scalars(
                    select(Message)
                    .where(Message.session_id == response.session_id)
                    .order_by(Message.created_at.asc())
                )
            ).all()
        )
        assert [row.content for row in rows] == ["Liệt kê ba tệp gần đây.", "Đã liệt kê."]
    await engine.dispose()


async def test_explicit_output_contract_miss_is_persisted_as_incomplete_not_success(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat-incomplete.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email="incomplete@example.com", display_name="Incomplete", role="editor")
        db.add(user)
        await db.commit()
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="incomplete-request"),
            app=SimpleNamespace(state=SimpleNamespace(orchestrator=IncompleteOrchestrator())),
        )

        response = await chat(
            ChatRequest(message="Giải thích chi tiết tối thiểu 500 từ."),
            request,
            user,
            db,
        )

        assistant = await db.scalar(select(Message).where(Message.role == "assistant"))
        audit = await db.scalar(select(AuditEvent))
        assert response.status == "incomplete"
        assert response.trace and all(
            event.get("run_id") == "incomplete-request" for event in response.trace
        )
        assert assistant is not None and assistant.status == "incomplete"
        assert assistant.request_id == "incomplete-request"
        assert response.proposals == []
        assert await db.scalar(select(func.count()).select_from(CreationProposalRecord)) == 0
        assert audit is not None and audit.status == "warning"
        assert json.loads(audit.result_json)["turn_status"] == "incomplete"
    await engine.dispose()


async def test_chat_boundary_persists_only_metadata_trace(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat-trace.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email="trace@example.com", display_name="Trace", role="editor")
        db.add(user)
        await db.commit()
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="trace-request"),
            app=SimpleNamespace(state=SimpleNamespace(orchestrator=PrivateTraceOrchestrator())),
        )
        response = await chat(ChatRequest(message="Read mail"), request, user, db)
        row = await db.scalar(select(Message).where(Message.role == "assistant"))
        assert row is not None
        assert response.trace == [
            {
                "run_id": "trace-request",
                "stage": "planning",
                "status": "success",
                "step_count": 1,
            }
        ]
        assert "private-gmail-canary" not in row.trace_json
        assert json.loads(row.trace_json) == response.trace
    await engine.dispose()


def test_gmail_followup_uses_latest_cited_source_even_with_abbreviated_vietnamese():
    prior = [
        SimpleNamespace(
            role="assistant",
            citations_json=json.dumps(
                [
                    {
                        "web_view_link": "https://mail.google.com/mail/u/0/#all/thread-123456"
                    }
                ]
            ),
        )
    ]

    route = _gmail_followup_route(
        "Giải thích bản chất theo first principles về nội dung đc đề cập.", prior
    )

    assert route == Route("gmail_read_thread", {"thread_id": "thread-123456"})


def test_gmail_followup_can_resolve_email_after_assistant_requested_source():
    prior = [
        SimpleNamespace(role="assistant", citations_json="[]"),
        SimpleNamespace(
            role="user",
            citations_json="[]",
        ),
        SimpleNamespace(
            role="assistant",
            citations_json=json.dumps(
                [
                    {
                        "web_view_link": "https://mail.google.com/mail/u/0/#all/thread-123456"
                    }
                ]
            ),
        ),
    ]

    route = _gmail_followup_route("Tài liệu là email gần nhất đó.", prior)

    assert route == Route("gmail_read_thread", {"thread_id": "thread-123456"})


def test_gmail_followup_does_not_reuse_an_old_source_for_unrelated_message():
    prior = [
        SimpleNamespace(role="assistant", citations_json="[]"),
        SimpleNamespace(
            role="assistant",
            citations_json=json.dumps(
                [
                    {
                        "web_view_link": "https://mail.google.com/mail/u/0/#all/thread-123456"
                    }
                ]
            ),
        ),
    ]

    assert _gmail_followup_route("Giải thích khái niệm này.", prior) is None


async def test_chat_api_passes_persisted_gmail_source_to_followup_orchestrator(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'gmail-followup.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    orchestrator = CapturingOrchestrator()
    async with factory() as db:
        user = User(
            email="gmail-followup@example.com",
            display_name="Gmail follow-up",
            role="editor",
        )
        db.add(user)
        await db.flush()
        session = ChatSession(user_id=user.id)
        db.add(session)
        await db.flush()
        db.add_all(
            [
                Message(
                    user_id=user.id,
                    session_id=session.id,
                    role="user",
                    content="Tóm tắt email gần nhất.",
                ),
                Message(
                    user_id=user.id,
                    session_id=session.id,
                    role="assistant",
                    content="Email mới nhất nói về cách giữ kết quả sau khi lỗi.",
                    citations_json=json.dumps(
                        [
                            {
                                "web_view_link": (
                                    "https://mail.google.com/mail/u/0/#all/thread-123456"
                                )
                            }
                        ]
                    ),
                ),
            ]
        )
        await db.commit()
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="gmail-followup-request"),
            app=SimpleNamespace(state=SimpleNamespace(orchestrator=orchestrator)),
        )

        response = await chat(
            ChatRequest(
                message="Đào sâu nội dung đó theo nguyên lý đầu tiên.",
                session_id=session.id,
            ),
            request,
            user,
            db,
        )

        assert response.session_id == session.id
        assert len(orchestrator.calls) == 1
        assert orchestrator.calls[0]["route_override"] == Route(
            "gmail_read_thread", {"thread_id": "thread-123456"}
        )
    await engine.dispose()


class TimingOutOrchestrator:
    async def run(self, **_kwargs):
        raise TimeoutError("Latency budget exhausted")


async def test_chat_timeout_reports_truthful_message(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat-timeout.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email="timeout@example.com", display_name="Timeout", role="editor")
        db.add(user)
        await db.commit()
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="timeout-request"),
            app=SimpleNamespace(state=SimpleNamespace(orchestrator=TimingOutOrchestrator())),
        )
        with pytest.raises(HTTPException) as error:
            await chat(ChatRequest(message="test timeout"), request, user, db)
        assert error.value.status_code == 503
        assert "Timeout quá 60s" in error.value.detail
        assert "timeout-request" in error.value.detail
        audit = await db.scalar(select(AuditEvent))
        assert audit is not None
        assert json.loads(audit.result_json)["failure_category"] == "provider_timeout"
    await engine.dispose()
