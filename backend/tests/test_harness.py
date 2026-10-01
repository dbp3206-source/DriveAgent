from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.dependencies import get_current_user
from app.api.harness import _nearest_rank_percentile, _runtime_audit_stats, router
from app.core.config import get_settings
from app.db.models import (
    AuditEvent,
    Base,
    ChatSession,
    DocumentChunk,
    DriveFileIndex,
    LongTermMemory,
    Message,
    User,
)
from app.db.session import get_db
from app.services.rag import index_fingerprint
from app.tools.calculator import calculator_tool_definitions
from app.tools.registry import ToolRegistry


def test_nearest_rank_percentile_handles_small_and_large_samples():
    assert _nearest_rank_percentile([], 0.95) is None
    assert _nearest_rank_percentile([20, 10], 0.95) == 20
    assert _nearest_rank_percentile(list(range(1, 101)), 0.95) == 95
    with pytest.raises(ValueError, match="percentile"):
        _nearest_rank_percentile([10, 20], 0)


def test_runtime_audit_stats_excludes_history_started_rows_and_normalizes_timezone():
    audits = [
        AuditEvent(
            request_id="current-success",
            tool_name="list_drive_files",
            status="success",
            latency_ms=20,
            created_at=datetime(2026, 9, 14, 12, 1),
        ),
        AuditEvent(
            request_id="current-error",
            tool_name="read_drive_file",
            status="error",
            latency_ms=80,
            created_at=datetime(2026, 9, 14, 12, 2, tzinfo=UTC),
        ),
        AuditEvent(
            request_id="unfinished",
            tool_name="read_drive_file",
            status="started",
            created_at=datetime(2026, 9, 14, 12, 3),
        ),
        AuditEvent(
            request_id="historical-denied",
            tool_name="send_gmail",
            status="denied",
            latency_ms=5,
            created_at=datetime(2026, 9, 14, 11, 59),
        ),
    ]

    stats = _runtime_audit_stats(audits, "2026-09-14T12:00:00+00:00")

    assert stats == {
        "started_at": "2026-09-14T12:00:00+00:00",
        "sample_size": 2,
        "success_count": 1,
        "error_count": 1,
        "denied_count": 0,
        "success_rate": 0.5,
        "latency_p50_ms": 50.0,
        "latency_p95_ms": 80,
        "latency_sample_size": 2,
    }
    assert _runtime_audit_stats(audits, "not-a-timestamp")["sample_size"] == 0


async def test_harness_uses_owned_data_and_feedback_is_upserted(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'harness.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(router)
    registry = ToolRegistry()
    for definition in calculator_tool_definitions():
        registry.register(definition)
    app.state.registry = registry
    app.state.orchestrator = SimpleNamespace()

    async with factory() as db:
        owner = User(email="owner@test.invalid", display_name="Owner", role="owner")
        other = User(email="other@test.invalid", display_name="Other", role="owner")
        db.add_all([owner, other])
        await db.flush()
        owned_session = ChatSession(user_id=owner.id, title="Owned")
        other_session = ChatSession(user_id=other.id, title="Private")
        db.add_all([owned_session, other_session])
        await db.flush()
        answer = Message(
            user_id=owner.id,
            session_id=owned_session.id,
            role="assistant",
            content="Answer",
            request_id="run-correlation-1",
            trace_json=(
                '[{"stage":"output_guard","status":"corrected","run_id":"run-correlation-1",'
                '"rule":"explicit_unsourced_claim_restriction","affected_lines":2}]'
            ),
        )
        private_answer = Message(
            user_id=other.id,
            session_id=other_session.id,
            role="assistant",
            content="Private",
        )
        old_answer = Message(
            user_id=owner.id,
            session_id=owned_session.id,
            role="assistant",
            content="Old answer stays in chat history",
            request_id="old-run-outside-agentops-window",
            trace_json='[{"stage":"usage","total_token_count":9000}]',
            created_at=datetime.now(UTC) - timedelta(days=31),
        )
        db.add_all(
            [
                answer,
                private_answer,
                old_answer,
                AuditEvent(
                    request_id="old-failed-task",
                    user_id=owner.id,
                    role="owner",
                    tool_name="agent_task",
                    status="error",
                    created_at=datetime.now(UTC) - timedelta(days=31),
                ),
                AuditEvent(
                    request_id="failed-owned-run",
                    user_id=owner.id,
                    role="owner",
                    tool_name="agent_task",
                    arguments_json='{"session_id":"owned-session"}',
                    status="error",
                    error_message="private provider detail must not enter the dashboard",
                    latency_ms=321,
                ),
                AuditEvent(
                    request_id="failed-private-run",
                    user_id=other.id,
                    role="owner",
                    tool_name="agent_task",
                    status="error",
                ),
                LongTermMemory(
                    user_id=owner.id,
                    kind="preference",
                    content="Concise",
                    normalized_hash="owned",
                ),
                LongTermMemory(
                    user_id=other.id,
                    kind="preference",
                    content="Private",
                    normalized_hash="other",
                ),
                DriveFileIndex(
                    user_id=owner.id,
                    drive_file_id="current-file",
                    name="Current",
                    mime_type="text/plain",
                    content_hash=index_fingerprint("current body", get_settings()),
                    chunk_count=1,
                ),
                DriveFileIndex(
                    user_id=owner.id,
                    drive_file_id="stale-file",
                    name="Stale",
                    mime_type="text/plain",
                    content_hash="legacy-parser-hash",
                    chunk_count=1,
                ),
                DocumentChunk(
                    id="current-chunk",
                    user_id=owner.id,
                    drive_file_id="current-file",
                    file_name="Current",
                    mime_type="text/plain",
                    chunk_index=0,
                    content="Current body",
                    token_terms_json="[]",
                    embedding_json="[]",
                ),
                DocumentChunk(
                    id="stale-chunk",
                    user_id=owner.id,
                    drive_file_id="stale-file",
                    file_name="Stale",
                    mime_type="text/plain",
                    chunk_index=0,
                    content="Legacy body",
                    token_terms_json="[]",
                    embedding_json="[]",
                ),
            ]
        )
        await db.commit()

        async def current_user():
            return owner

        async def session():
            async with factory() as request_db:
                yield request_db

        app.dependency_overrides[get_current_user] = current_user
        app.dependency_overrides[get_db] = session
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            overview = (await client.get("/api/harness/overview")).json()
            assert overview["telemetry_window"]["days"] == 30
            assert overview["telemetry_window"]["external_exporter"] is False
            assert all(
                run.get("run_id") != "old-run-outside-agentops-window"
                for run in overview["recent_runs"]
            )
            assert all(
                run.get("run_id") != "old-failed-task" for run in overview["recent_runs"]
            )
            assert (await db.get(Message, old_answer.id)).content == (
                "Old answer stays in chat history"
            )
            assert overview["context"] == {"sessions": 1, "active_memories": 1}
            assert overview["rag"] == {"indexed_files": 1, "indexed_chunks": 1}
            assert overview["tools"]["total"] == 1
            assert overview["evaluation"]["feedback_count"] == 0
            assert overview["evaluation"]["recent_output_quality"]["presentation_only"] == 1
            contracts = overview["evaluation"]["answer_contract_benchmark"]
            assert contracts["passed"] == contracts["total"] == 16
            assert contracts["live_model_checked"] is False
            assert contracts["coverage"]["answer_key_cases"] == 16
            answer_run = next(
                run for run in overview["recent_runs"] if run.get("run_id") == "run-correlation-1"
            )
            assert all("answer_preview" not in run for run in overview["recent_runs"])
            assert answer_run["output_quality"]["verification"]["status"] == (
                "presentation_only"
            )
            assert answer_run["events"][0] == {
                "stage": "output_guard",
                "status": "corrected",
                "rule": "explicit_unsourced_claim_restriction",
                "affected_lines": 2,
                "run_id": "run-correlation-1",
            }
            failed_run = next(
                run for run in overview["recent_runs"] if run.get("run_id") == "failed-owned-run"
            )
            assert failed_run["events"] == [
                {
                    "stage": "agent_task",
                    "status": "error",
                    "run_id": "failed-owned-run",
                    "latency_ms": 321,
                }
            ]
            assert "private provider detail" not in str(overview["recent_runs"])
            assert "failed-private-run" not in str(overview["recent_runs"])
            assert overview["runtime"]["runtime_pid"] > 0
            assert overview["runtime"]["runtime_started_at"] is None
            assert overview["evaluation"]["current_runtime"]["sample_size"] == 0
            assert overview["evaluation"]["evaluated_at_utc"].endswith("+00:00")
            lineage = overview["evaluation"]["metric_lineage"]
            assert lineage["audit"]["row_limit"] == 100
            assert lineage["audit"]["success_denominator"] == 0
            assert lineage["audit"]["latency_sample_size"] == 0
            assert lineage["audit"]["latency_p95_method"].startswith("nearest-rank")
            assert lineage["feedback"]["helpful_denominator"] == 0
            assert lineage["recent_output"]["sample_size"] == 1
            assert lineage["citation_integrity"]["denominator"] == 0

            contract_cases = (await client.get("/api/harness/answer-contract-eval")).json()
            assert contract_cases["total"] == 16
            assert contract_cases["live_model_checked"] is False
            assert all(case["candidate_passed"] for case in contract_cases["cases"])

            url = f"/api/harness/feedback/{answer.id}"
            assert (await client.post(url, json={"rating": "helpful"})).status_code == 200
            assert (
                await client.post(url, json={"rating": "notlish", "reasons": []})
            ).status_code == 422
            assert (
                await client.post(
                    f"/api/harness/feedback/{private_answer.id}",
                    json={"rating": "helpful"},
                )
            ).status_code == 404
            assert (
                await client.post(url, json={"rating": "not_helpful", "reasons": ["too_short"]})
            ).status_code == 200
            updated = (await client.get("/api/harness/overview")).json()
            assert updated["evaluation"]["feedback_count"] == 1
            assert updated["evaluation"]["helpful_rate"] == 0.0
            assert updated["evaluation"]["metric_lineage"]["feedback"]["helpful_count"] == 0
            assert updated["evaluation"]["metric_lineage"]["feedback"]["helpful_denominator"] == 1
        assert engine.sync_engine.pool.checkedout() == 0
    await engine.dispose()


async def test_harness_survives_malformed_trace_and_usage_values(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'malformed.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(router)
    app.state.registry = ToolRegistry()
    app.state.orchestrator = SimpleNamespace()

    async with factory() as db:
        owner = User(email="owner@test.invalid", display_name="Owner", role="owner")
        db.add(owner)
        await db.flush()
        session = ChatSession(user_id=owner.id, title="Malformed")
        db.add(session)
        await db.flush()
        db.add_all(
            [
                Message(
                    user_id=owner.id,
                    session_id=session.id,
                    role="assistant",
                    content="Một câu trả lời vẫn xem được.",
                    trace_json="not-json",
                    citations_json="also-not-json",
                ),
                Message(
                    user_id=owner.id,
                    session_id=session.id,
                    role="assistant",
                    content="Một câu khác.",
                    trace_json='[{"stage":"usage","total_token_count":"unknown"}]',
                ),
            ]
        )
        await db.commit()

        async def current_user():
            return owner

        async def request_db():
            async with factory() as scoped:
                yield scoped

        app.dependency_overrides[get_current_user] = current_user
        app.dependency_overrides[get_db] = request_db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/harness/overview")

        assert response.status_code == 200
        assert response.json()["evaluation"]["quality_audit"]["trace_parseable"] == 2
    await engine.dispose()
