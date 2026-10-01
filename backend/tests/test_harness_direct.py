"""Direct integration coverage for the learning dashboard's real aggregation path.

The HTTP tests exercise authentication and response serialization.  This test calls
the aggregation function with a temporary SQLite database so calculations, lineage,
and feedback upserts are verified without a live Gemini or Google request.
"""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import harness
from app.core.config import Settings
from app.db.models import (
    AuditEvent,
    Base,
    ChatSession,
    DocumentChunk,
    DriveFileIndex,
    LongTermMemory,
    Message,
    ResponseFeedback,
    User,
)
from app.services.rag import index_fingerprint
from app.tools.calculator import calculator_tool_definitions
from app.tools.registry import ToolRegistry


def test_automated_business_benchmark_requires_valid_published_shape(tmp_path, monkeypatch):
    missing = tmp_path / "missing.json"
    monkeypatch.setattr(harness, "_BUSINESS_BENCHMARK_PATH", missing)
    assert harness._automated_business_benchmark() == {
        "measured": False,
        "sample_size": 0,
        "pass_rate": None,
    }

    published = tmp_path / "business.json"
    published.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sample_size": 3,
                "passed": 3,
                "pass_rate": 1.0,
                "average_screening_score": 98.0,
                "scope": "Curated oracle cases only.",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(harness, "_BUSINESS_BENCHMARK_PATH", published)
    result = harness._automated_business_benchmark()
    assert result["measured"] is True
    assert result["sample_size"] == 3
    assert result["pass_rate"] == 1.0


@pytest.mark.asyncio
async def test_overview_aggregates_owned_runtime_rag_feedback_and_lineage(tmp_path):
    """The dashboard must only report the current user's retrievable evidence."""

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'harness-direct.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'harness-direct.db'}",
    )
    registry = ToolRegistry()
    for definition in calculator_tool_definitions():
        registry.register(definition)
    now = datetime.now(UTC)

    try:
        async with factory() as db:
            user = User(
                email="dashboard@example.test", display_name="Dashboard", role="super_admin"
            )
            db.add(user)
            await db.flush()
            session = ChatSession(user_id=user.id, title="Kế hoạch")
            db.add(session)
            await db.flush()
            question = Message(
                user_id=user.id,
                session_id=session.id,
                role="user",
                content="Tóm tắt kế hoạch từ tài liệu",
                created_at=now - timedelta(seconds=30),
            )
            answer = Message(
                user_id=user.id,
                session_id=session.id,
                role="assistant",
                content="## Kết luận\n\n- Kế hoạch đã sẵn sàng. [1]",
                citations_json=json.dumps(
                    [{"file_id": "file-current", "file_name": "Kế hoạch"}], ensure_ascii=False
                ),
                trace_json=json.dumps(
                    [
                        {"stage": "routing", "status": "success", "agent": "study"},
                        {
                            "stage": "usage",
                            "prompt_token_count": 10,
                            "candidates_token_count": 8,
                            "total_token_count": 18,
                        },
                    ]
                ),
                created_at=now - timedelta(seconds=10),
            )
            db.add_all(
                [
                    question,
                    answer,
                    LongTermMemory(
                        user_id=user.id,
                        kind="preference",
                        content="Ưu tiên bảng khi so sánh",
                        normalized_hash="dashboard-memory",
                    ),
                    DriveFileIndex(
                        user_id=user.id,
                        drive_file_id="file-current",
                        name="Kế hoạch",
                        mime_type="text/plain",
                        content_hash=index_fingerprint("Nguồn hiện tại", settings),
                        chunk_count=1,
                    ),
                    DriveFileIndex(
                        user_id=user.id,
                        drive_file_id="file-stale",
                        name="Cũ",
                        mime_type="text/plain",
                        content_hash="stale-index",
                        chunk_count=1,
                    ),
                    DocumentChunk(
                        id="dashboard-current-chunk",
                        user_id=user.id,
                        drive_file_id="file-current",
                        file_name="Kế hoạch",
                        mime_type="text/plain",
                        chunk_index=0,
                        content="Nguồn hiện tại",
                    ),
                    DocumentChunk(
                        id="dashboard-stale-chunk",
                        user_id=user.id,
                        drive_file_id="file-stale",
                        file_name="Cũ",
                        mime_type="text/plain",
                        chunk_index=0,
                        content="Nguồn cũ",
                    ),
                    AuditEvent(
                        request_id="tool-success",
                        user_id=user.id,
                        tool_name="list_drive_files",
                        status="success",
                        latency_ms=25,
                        created_at=now - timedelta(seconds=5),
                    ),
                    AuditEvent(
                        request_id="task-success",
                        user_id=user.id,
                        tool_name="agent_task",
                        status="success",
                        latency_ms=40,
                        created_at=now - timedelta(seconds=4),
                    ),
                    AuditEvent(
                        request_id="still-running",
                        user_id=user.id,
                        tool_name="read_drive_file",
                        status="started",
                        created_at=now - timedelta(seconds=3),
                    ),
                ]
            )
            await db.flush()
            db.add(
                ResponseFeedback(
                    user_id=user.id,
                    message_id=answer.id,
                    rating=1,
                    reasons_json='["other"]',
                )
            )
            await db.commit()
            request = SimpleNamespace(
                app=SimpleNamespace(
                    state=SimpleNamespace(
                        registry=registry,
                        orchestrator=SimpleNamespace(),
                        runtime_started_at=(now - timedelta(minutes=1)).isoformat(),
                    )
                )
            )

            with patch("app.api.harness.get_settings", return_value=settings):
                result = await harness.overview(request, user, db)

                assert result["context"] == {"sessions": 1, "active_memories": 1}
                assert result["rag"] == {"indexed_files": 1, "indexed_chunks": 1}
                assert result["tools"]["total"] == 1
                assert result["evaluation"]["tool_success_rate"] == 1.0
                assert result["evaluation"]["task_success_rate"] is None
                assert result["evaluation"]["task_success_measurement"] == (
                    "not_measured_without_oracle_or_human_review"
                )
                assert result["evaluation"]["task_execution_success_rate"] == 1.0
                assert result["evaluation"]["task_execution_success_count"] == 1
                assert result["evaluation"]["metric_lineage"]["tasks"][
                    "business_task_success"
                ].startswith("N/A")
                assert result["evaluation"]["current_runtime"]["sample_size"] == 2
                assert result["evaluation"]["usage"] == {
                    "prompt_tokens": 10,
                    "output_tokens": 8,
                    "total_tokens": 18,
                    "measured_runs": 1,
                }
                assert result["evaluation"]["quality_audit"]["grounded_citation_rate"] == 1.0
                assert result["recent_runs"][0]["events"][0]["stage"] == "routing"
                assert result["evaluation"]["feedback_reasons"]["other"] == 1
                assert result["evaluation"]["metric_lineage"]["audit"]["success_denominator"] == 1

                updated = await harness.save_feedback(
                    answer.id,
                    harness.FeedbackRequest(
                        rating="not_helpful", reasons=["too_short"], comment="  Cần cụ thể hơn.  "
                    ),
                    user,
                    db,
                )
            assert updated == {"message_id": answer.id, "rating": "not_helpful"}
            feedback = await db.scalar(
                select(ResponseFeedback).where(ResponseFeedback.message_id == answer.id)
            )
            assert feedback is not None
            assert feedback.rating == -1
            assert feedback.comment == "Cần cụ thể hơn."
    finally:
        await engine.dispose()
