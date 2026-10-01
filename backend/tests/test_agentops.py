import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, ChatSession, Message, User
from app.services.agentops import expire_run_traces, sanitize_run_trace


def test_agentops_trace_keeps_operational_metadata_not_user_text():
    private = "private-gmail-body-canary"
    events = [
        {
            "stage": "planning",
            "status": "success",
            "steps": [f"Read {private}", "Summarize"],
            "note": private,
            "error": private,
            "prompt": private,
        },
        {
            "stage": "tool",
            "status": "success",
            "tool": "gmail_read_thread",
            "latency_ms": 42,
            "result": {"body": private},
        },
        {"stage": private, "status": "success", "model": private},
        {"stage": "usage", "total_token_count": 123, "note": private},
    ]

    projected = sanitize_run_trace(events, "run-123")
    assert len(projected) == 3
    assert projected[0] == {
        "run_id": "run-123",
        "stage": "planning",
        "status": "success",
        "step_count": 2,
    }
    assert projected[1]["tool"] == "gmail_read_thread"
    assert projected[1]["latency_ms"] == 42
    assert projected[2]["total_token_count"] == 123
    assert private not in json.dumps(projected)


def test_agentops_trace_rejects_unbounded_or_invalid_fields():
    projected = sanitize_run_trace(
        [
            {
                "stage": "usage",
                "status": "success",
                "total_token_count": "999",
                "latency_ms": -1,
                "agents": ["study_agent", "private user name", "workspace_agent"],
                "steps": ["private"] * 1001,
            }
        ],
        "unsafe run id",
    )
    assert projected == [
        {
            "run_id": "invalid-run-id",
            "stage": "usage",
            "status": "success",
            "agents": ["study_agent", "workspace_agent"],
            "step_count": 1000,
        }
    ]


def test_agentops_output_contract_keeps_only_static_non_content_reason_codes():
    private = "private-gmail-body-canary"
    projected = sanitize_run_trace(
        [
            {
                "stage": "output_contract",
                "status": "degraded",
                "violations": ["above_explicit_word_maximum", private, "missing_action_section"],
                "initial_violations": ["above_explicit_word_maximum", private],
                "reason": private,
            },
            {"stage": "tool", "status": "failed", "violations": ["missing_action_section"]},
        ],
        "run-123",
    )
    assert projected[0]["violations"] == [
        "above_explicit_word_maximum", "missing_action_section"
    ]
    assert projected[0]["initial_violations"] == ["above_explicit_word_maximum"]
    assert "violations" not in projected[1]
    assert private not in json.dumps(projected)


async def test_agentops_30_day_expiration_preserves_chat_and_recent_traces(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'retention.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime(2026, 9, 24, tzinfo=UTC)
    async with factory() as db:
        user = User(email="retention@example.com", display_name="Retention", role="owner")
        db.add(user)
        await db.flush()
        session = ChatSession(user_id=user.id, title="Keep this conversation")
        db.add(session)
        await db.flush()
        old_answer = Message(
            user_id=user.id,
            session_id=session.id,
            role="assistant",
            content="Keep old answer",
            trace_json='[{"stage":"usage","total_token_count":50}]',
            created_at=now - timedelta(days=31),
        )
        recent_answer = Message(
            user_id=user.id,
            session_id=session.id,
            role="assistant",
            content="Keep recent answer and trace",
            trace_json='[{"stage":"usage","total_token_count":25}]',
            created_at=now - timedelta(days=29),
        )
        old_question = Message(
            user_id=user.id,
            session_id=session.id,
            role="user",
            content="Keep old question",
            trace_json='[{"legacy":"not-an-assistant-trace"}]',
            created_at=now - timedelta(days=31),
        )
        db.add_all([old_answer, recent_answer, old_question])
        await db.commit()

        assert await expire_run_traces(db, now=now) == 1
        await db.commit()
        await db.refresh(old_answer)
        await db.refresh(recent_answer)
        await db.refresh(old_question)
        assert old_answer.content == "Keep old answer"
        assert old_answer.trace_json == "[]"
        assert "total_token_count" in recent_answer.trace_json
        assert "not-an-assistant-trace" in old_question.trace_json
        assert await expire_run_traces(db, now=now) == 0
    await engine.dispose()
