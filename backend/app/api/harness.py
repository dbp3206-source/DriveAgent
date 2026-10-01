"""Inspectable Harness and evaluation data derived from the current user's real runs."""

import json
import os
import re
from datetime import UTC, datetime, timedelta
from math import ceil
from pathlib import Path
from statistics import median
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DbSession
from app.auth.permissions import permissions_for_role
from app.core.config import get_settings
from app.core.json_utils import json_list
from app.db.models import (
    AuditEvent,
    ChatSession,
    DocumentChunk,
    DriveFileIndex,
    LongTermMemory,
    Message,
    ResponseFeedback,
)
from app.services.embeddings import EMBEDDING_DIMENSION
from app.services.evaluation import (
    evaluate_text_answer,
    run_adversarial_mutation_regression,
    run_answer_contract_benchmark,
    run_output_quality_regression,
    run_routing_regression,
)
from app.services.protocols import READ_TOOLS
from app.services.rag import is_current_index_hash
from app.services.relational_skills import skill_store

router = APIRouter(prefix="/api/harness", tags=["harness"])

_BUSINESS_BENCHMARK_PATH = (
    Path(__file__).resolve().parents[2] / "evals" / "results" / "business_live_latest.json"
)


def _automated_business_benchmark() -> dict[str, object]:
    """Load a publisher-validated summary without exposing answer content."""

    try:
        payload = json.loads(_BUSINESS_BENCHMARK_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"measured": False, "sample_size": 0, "pass_rate": None}
    sample_size = payload.get("sample_size")
    passed = payload.get("passed")
    rate = payload.get("pass_rate")
    if (
        payload.get("schema_version") != 1
        or not isinstance(sample_size, int)
        or sample_size <= 0
        or not isinstance(passed, int)
        or not isinstance(rate, (int, float))
        or passed < 0
        or passed > sample_size
        or rate < 0
        or rate > 1
    ):
        return {"measured": False, "sample_size": 0, "pass_rate": None}
    return {
        "measured": True,
        "sample_size": sample_size,
        "passed": passed,
        "pass_rate": float(rate),
        "average_screening_score": payload.get("average_screening_score"),
        "requested_model": payload.get("requested_model"),
        "published_at_utc": payload.get("published_at_utc"),
        "manifest_sha256": payload.get("manifest_sha256"),
        "report_sha256": payload.get("report_sha256"),
        "scope": payload.get("scope"),
    }


def _nearest_rank_percentile(values: list[int], percentile: float) -> int | None:
    """Return a reproducible nearest-rank percentile for a nonempty sample."""

    if not values:
        return None
    if not 0 < percentile <= 1:
        raise ValueError("percentile must be greater than 0 and at most 1")
    ordered = sorted(values)
    return ordered[ceil(percentile * len(ordered)) - 1]


def _runtime_audit_stats(
    audits: list[AuditEvent], runtime_started_at: str | None
) -> dict[str, object]:
    """Summarize completed audit events created by the current server process.

    SQLite can return naive datetimes even though the model declares timezone
    awareness. Normalizing both sides to naive UTC keeps the comparison
    deterministic without rewriting the stored audit history.
    """

    started_at: datetime | None = None
    if runtime_started_at:
        try:
            parsed = datetime.fromisoformat(runtime_started_at)
            started_at = (
                parsed.astimezone(UTC).replace(tzinfo=None)
                if parsed.tzinfo is not None
                else parsed
            )
        except ValueError:
            pass

    def as_naive_utc(value: datetime) -> datetime:
        return (
            value.astimezone(UTC).replace(tzinfo=None)
            if value.tzinfo is not None
            else value
        )

    current = [
        row
        for row in audits
        if started_at is not None
        and row.created_at is not None
        and as_naive_utc(row.created_at) >= started_at
        and row.status != "started"
    ]
    latencies = sorted(row.latency_ms for row in current if row.latency_ms is not None)
    success_count = sum(row.status == "success" for row in current)
    return {
        "started_at": runtime_started_at,
        "sample_size": len(current),
        "success_count": success_count,
        "error_count": sum(row.status == "error" for row in current),
        "denied_count": sum(row.status == "denied" for row in current),
        "success_rate": round(success_count / len(current), 4) if current else None,
        "latency_p50_ms": median(latencies) if latencies else None,
        "latency_p95_ms": _nearest_rank_percentile(latencies, 0.95),
        "latency_sample_size": len(latencies),
    }


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: Literal["helpful", "not_helpful"]
    reasons: list[
        Literal["incorrect", "missing_source", "hard_to_follow", "too_short", "too_long", "other"]
    ] = Field(default_factory=list, max_length=4)
    comment: str | None = Field(default=None, max_length=1000)


@router.post("/feedback/{message_id}")
async def save_feedback(
    message_id: str,
    payload: FeedbackRequest,
    user: CurrentUser,
    db: DbSession,
):
    message = await db.scalar(
        select(Message).where(
            Message.id == message_id,
            Message.user_id == user.id,
            Message.role == "assistant",
        )
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu trả lời.")
    row = await db.scalar(
        select(ResponseFeedback).where(
            ResponseFeedback.user_id == user.id,
            ResponseFeedback.message_id == message_id,
        )
    )
    value = 1 if payload.rating == "helpful" else -1
    if row is None:
        row = ResponseFeedback(user_id=user.id, message_id=message_id, rating=value)
        db.add(row)
    row.rating = value
    row.reasons_json = json.dumps(payload.reasons, ensure_ascii=False)
    row.comment = payload.comment.strip() if payload.comment else None
    await db.commit()
    return {"message_id": message_id, "rating": payload.rating}


@router.get("/overview")
async def overview(request: Request, user: CurrentUser, db: DbSession):
    settings = get_settings()
    # A bounded AgentOps view is distinct from the retention of chat history
    # and operational audit records. Those sources must not be deleted here.
    telemetry_window_days = 30
    telemetry_cutoff = (datetime.now(UTC) - timedelta(days=telemetry_window_days)).replace(
        tzinfo=None
    )
    allowed = permissions_for_role(user.role)
    definitions = request.app.state.registry.definitions()
    tools = [
        {
            "name": item.name,
            "description": item.description,
            "available": item.required_permissions <= allowed,
            "requires_approval": item.requires_user_action,
            "permissions": sorted(item.required_permissions),
            "oauth_scopes": sorted(item.required_oauth_scopes),
            "max_attempts": item.max_attempts,
            "timeout_seconds": item.timeout_seconds,
        }
        for item in definitions
    ]

    async def count(model, *conditions):
        query = select(func.count()).select_from(model).where(*conditions)
        return int(await db.scalar(query) or 0)

    session_count = await count(ChatSession, ChatSession.user_id == user.id)
    memory_count = await count(
        LongTermMemory,
        LongTermMemory.user_id == user.id,
        LongTermMemory.is_archived.is_(False),
    )
    # Harness metrics must describe retrievable knowledge, not historical rows left
    # behind for safe interrupted re-index recovery.  The RAG search path applies
    # the same pipeline-version gate, so the learning dashboard cannot imply that
    # stale parser/embedding data is ready to answer questions.
    index_rows = list(
        (
            await db.scalars(
                select(DriveFileIndex).where(DriveFileIndex.user_id == user.id)
            )
        ).all()
    )
    current_file_ids = [
        row.drive_file_id
        for row in index_rows
        if is_current_index_hash(row.content_hash, settings)
    ]
    indexed_files = len(current_file_ids)
    indexed_chunks = (
        await count(
            DocumentChunk,
            DocumentChunk.user_id == user.id,
            DocumentChunk.drive_file_id.in_(current_file_ids),
        )
        if current_file_ids
        else 0
    )

    audits = list(
        (
            await db.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.user_id == user.id,
                    AuditEvent.created_at >= telemetry_cutoff,
                )
                .order_by(AuditEvent.created_at.desc())
                .limit(100)
            )
        ).all()
    )
    completed = [
        row for row in audits if row.status != "started" and row.tool_name != "agent_task"
    ]
    task_completed = [
        row for row in audits if row.status != "started" and row.tool_name == "agent_task"
    ]
    successes = sum(row.status == "success" for row in completed)
    task_successes = sum(row.status == "success" for row in task_completed)
    latencies = sorted(row.latency_ms for row in completed if row.latency_ms is not None)
    runtime_started_at = getattr(request.app.state, "runtime_started_at", None)
    current_runtime = _runtime_audit_stats(audits, runtime_started_at)

    feedback_rows = list(
        (
            await db.scalars(
                select(ResponseFeedback)
                .where(
                    ResponseFeedback.user_id == user.id,
                    ResponseFeedback.updated_at >= telemetry_cutoff,
                )
                .order_by(ResponseFeedback.updated_at.desc())
            )
        ).all()
    )
    helpful = sum(row.rating > 0 for row in feedback_rows)
    feedback_reasons = {
        "incorrect": 0,
        "missing_source": 0,
        "hard_to_follow": 0,
        "too_short": 0,
        "too_long": 0,
        "other": 0,
    }
    for row in feedback_rows:
        try:
            for reason in json_list(row.reasons_json):
                if reason in feedback_reasons:
                    feedback_reasons[reason] += 1
        except (TypeError, json.JSONDecodeError):
            continue
    traces = list(
        (
            await db.scalars(
                select(Message.trace_json)
                .where(
                    Message.user_id == user.id,
                    Message.role == "assistant",
                    Message.created_at >= telemetry_cutoff,
                )
                .order_by(Message.created_at.desc())
                .limit(50)
            )
        ).all()
    )
    usage = {"prompt_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    measured_runs = 0
    quality = {
        "responses": len(traces),
        "nonempty": 0,
        "trace_parseable": 0,
        "grounded_with_valid_citations": 0,
        "grounded_responses": 0,
    }
    message_rows = list(
        (
            await db.execute(
                select(Message.content, Message.citations_json, Message.trace_json)
                .where(
                    Message.user_id == user.id,
                    Message.role == "assistant",
                    Message.created_at >= telemetry_cutoff,
                )
                .order_by(Message.created_at.desc())
                .limit(50)
            )
        ).all()
    )
    quality["responses"] = len(message_rows)
    for content, citations_json, trace_json in message_rows:
        quality["nonempty"] += int(bool(content and content.strip()))
        try:
            citations = json_list(citations_json)
            trace = json_list(trace_json)
            quality["trace_parseable"] += int(isinstance(trace, list))
            if citations:
                quality["grounded_responses"] += 1
                # A Drive citation is still navigable when Google omits
                # ``webViewLink``: the UI can derive the canonical file URL
                # from ``file_id``.  Requiring the optional field made valid
                # grounded answers look broken in the quality dashboard.
                valid = all(item.get("file_id") and item.get("file_name") for item in citations)
                # Retrieval may return more evidence candidates than the final
                # answer needs. Integrity means every citation marker used by
                # the answer resolves to the attached evidence list; it does
                # not require citing every candidate that was retrieved.
                markers = [int(value) for value in re.findall(r"\[(\d+)\]", content or "")]
                markers_resolve = bool(markers) and all(
                    1 <= value <= len(citations) for value in markers
                )
                quality["grounded_with_valid_citations"] += int(valid and markers_resolve)
        except (TypeError, ValueError, AttributeError, json.JSONDecodeError):
            pass
    for trace_json in traces:
        has_usage = False
        for event in json_list(trace_json):
            if not isinstance(event, dict):
                continue
            if event.get("stage") != "usage":
                continue
            has_usage = True
            for source, target in (
                ("prompt_token_count", "prompt_tokens"),
                ("candidates_token_count", "output_tokens"),
                ("total_token_count", "total_tokens"),
            ):
                try:
                    usage[target] += int(event.get(source) or 0)
                except (TypeError, ValueError):
                    continue
        measured_runs += int(has_usage)

    evaluated_at = datetime.now(UTC).isoformat()
    latency_p50 = median(latencies) if latencies else None
    latency_p95 = _nearest_rank_percentile(latencies, 0.95)
    routing_eval = run_routing_regression()
    output_eval = run_output_quality_regression()
    contract_eval = run_answer_contract_benchmark()
    mutation_eval = run_adversarial_mutation_regression()
    business_benchmark = _automated_business_benchmark()
    skills = skill_store(settings).list(user.id)
    recent_rows = list(
        (
            await db.execute(
                select(
                    Message.id,
                    Message.session_id,
                    Message.content,
                    Message.citations_json,
                    Message.trace_json,
                    Message.created_at,
                    Message.request_id,
                )
                .where(
                    Message.user_id == user.id,
                    Message.role == "assistant",
                    Message.created_at >= telemetry_cutoff,
                )
                .order_by(Message.created_at.desc())
                .limit(6)
            )
        ).all()
    )
    recent_runs = []
    for (
        message_id,
        session_id,
        content,
        citations_json,
        trace_json,
        created_at,
        request_id,
    ) in recent_rows:
        try:
            run_trace = json_list(trace_json)
            run_citations = json_list(citations_json)
        except (TypeError, json.JSONDecodeError):
            continue
        events = []
        for event in run_trace[:30]:
            if not isinstance(event, dict):
                continue
            events.append(
                {
                    key: event.get(key)
                    for key in (
                        "stage",
                        "status",
                        "tool",
                        "from",
                        "to",
                        "agent",
                        "reason",
                        "rule",
                        "removed_lines",
                        "affected_lines",
                        "latency_ms",
                        "run_id",
                    )
                    if event.get(key) is not None
                }
            )
        question = await db.scalar(
            select(Message.content)
            .where(
                Message.user_id == user.id,
                Message.session_id == session_id,
                Message.role == "user",
                Message.created_at <= created_at,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        output_quality = evaluate_text_answer(
            question or "",
            content,
            run_citations if isinstance(run_citations, list) else [],
        )
        recent_runs.append(
            {
                "message_id": message_id,
                "run_id": request_id,
                "created_at": (
                    (
                        created_at.replace(tzinfo=UTC)
                        if created_at.tzinfo is None
                        else created_at.astimezone(UTC)
                    )
                    .isoformat()
                    .replace("+00:00", "Z")
                ),
                "citations": len(run_citations) if isinstance(run_citations, list) else 0,
                "output_quality": output_quality,
                "events": events,
            }
        )
    quality_runs = list(recent_runs)
    # Failed/cancelled roots have no assistant Message row, so they otherwise
    # disappear from the run view. Surface only a safe synthetic event from the
    # user's own task audit; do not include prompt, answer, or provider payloads.
    known_run_ids = {item["run_id"] for item in recent_runs if item.get("run_id")}
    failed_tasks = list(
        (
            await db.execute(
                select(
                    AuditEvent.id,
                    AuditEvent.request_id,
                    AuditEvent.status,
                    AuditEvent.created_at,
                    AuditEvent.latency_ms,
                )
                .where(
                    AuditEvent.user_id == user.id,
                    AuditEvent.tool_name == "agent_task",
                    AuditEvent.status.in_(["error", "denied", "warning"]),
                    AuditEvent.created_at >= telemetry_cutoff,
                )
                .order_by(AuditEvent.created_at.desc())
                .limit(20)
            )
        ).all()
    )
    for audit_id, request_id, status, created_at, latency_ms in failed_tasks:
        if not request_id or request_id in known_run_ids:
            continue
        normalized_created_at = (
            created_at.replace(tzinfo=UTC)
            if created_at.tzinfo is None
            else created_at.astimezone(UTC)
        )
        run_status = "cancelled" if status == "warning" else status
        recent_runs.append(
            {
                "message_id": audit_id,
                "run_id": request_id,
                "created_at": normalized_created_at.isoformat().replace("+00:00", "Z"),
                "citations": 0,
                "events": [
                    {
                        "stage": "agent_task",
                        "status": run_status,
                        "run_id": request_id,
                        **({"latency_ms": latency_ms} if latency_ms is not None else {}),
                    }
                ],
            }
        )
        known_run_ids.add(request_id)
    recent_runs.sort(key=lambda item: item["created_at"], reverse=True)
    recent_runs = recent_runs[:6]
    return {
        "runtime": {
            "orchestrator": settings.orchestrator_backend,
            "orchestrator_class": type(request.app.state.orchestrator).__name__,
            "runtime_pid": os.getpid(),
            "runtime_started_at": runtime_started_at,
            "primary_model": settings.gemini_chat_model,
            "fallback_model": settings.gemini_fallback_model,
            "embedding_model": settings.gemini_embedding_model,
            "embedding_dimensions": EMBEDDING_DIMENSION,
        },
        "telemetry_window": {
            "days": telemetry_window_days,
            "cutoff_utc": telemetry_cutoff.replace(tzinfo=UTC).isoformat(),
            "scope": "local user metadata read window; source retention is separately governed",
            "external_exporter": False,
        },
        "context": {"sessions": session_count, "active_memories": memory_count},
        "rag": {"indexed_files": indexed_files, "indexed_chunks": indexed_chunks},
        "tools": {
            "total": len(tools),
            "available": sum(item["available"] for item in tools),
            "approval_required": sum(item["requires_approval"] for item in tools),
            "items": tools,
        },
        "creation": {
            "google_outputs": ["Docs", "Sheets", "Gmail"],
            "skills": len(skills),
            "approval_flow": "preview → digest → approve → execute → verify",
        },
        "orchestration": {
            "stages": ["planning", "routing", "tool", "synthesis", "recovery"],
            "checkpoint": (
                "LangGraph SQLite"
                if settings.orchestrator_backend == "langgraph"
                else "ADK session"
            ),
        },
        "recent_runs": recent_runs,
        "protocols": {
            "mcp": {"enabled": True, "mode": "read_only", "tools": sorted(READ_TOOLS)},
            "a2a": {"enabled": True, "mode": "read_only", "tools": sorted(READ_TOOLS)},
            "multi_agent_runtime": settings.orchestrator_backend == "adk",
        },
        "evaluation": {
            "evaluated_at_utc": evaluated_at,
            "routing_regression": {
                key: value for key, value in routing_eval.items() if key != "cases"
            },
            "output_quality_regression": {
                key: value for key, value in output_eval.items() if key != "cases"
            },
            "answer_contract_benchmark": {
                key: value for key, value in contract_eval.items() if key != "cases"
            },
            "adversarial_mutation_regression": {
                key: value for key, value in mutation_eval.items() if key != "cases"
            },
            "automated_business_benchmark": business_benchmark,
            "recent_output_quality": {
                "measured": len(quality_runs),
                "average_score": round(
                    sum(item["output_quality"]["score"] for item in quality_runs)
                    / len(quality_runs),
                    1,
                )
                if quality_runs
                else None,
                "passed": sum(item["output_quality"]["passed"] for item in quality_runs),
                "presentation_only": sum(
                    item["output_quality"]["verification"]["status"] == "presentation_only"
                    for item in quality_runs
                ),
                "answer_key_checked": sum(
                    item["output_quality"]["verification"]["status"]
                    == "answer_key_constraints_checked"
                    for item in quality_runs
                ),
                "citation_unverified": sum(
                    item["output_quality"]["verification"]["citation_status"]
                    in {"unverified", "marker_only_unverified", "binding_failed"}
                    for item in quality_runs
                ),
                "scope": (
                    "Điểm trình bày; không chứng minh factual correctness hoặc semantic entailment."
                ),
            },
            "audit_sample_size": len(completed),
            "task_sample_size": len(task_completed),
            # agent_task audit status only proves that the execution path
            # returned, not that the user's business objective was met.
            "task_success_rate": None,
            "task_success_count": None,
            "task_success_measurement": "not_measured_without_oracle_or_human_review",
            "task_execution_success_rate": (
                round(task_successes / len(task_completed), 4) if task_completed else None
            ),
            "task_execution_success_count": task_successes,
            "current_runtime": current_runtime,
            "tool_success_rate": round(successes / len(completed), 4) if completed else None,
            "latency_p50_ms": latency_p50,
            "latency_p95_ms": latency_p95,
            "feedback_count": len(feedback_rows),
            "helpful_rate": round(helpful / len(feedback_rows), 4) if feedback_rows else None,
            "feedback_reasons": feedback_reasons,
            "usage": {**usage, "measured_runs": measured_runs},
            "quality_audit": {
                **quality,
                "nonempty_rate": round(quality["nonempty"] / quality["responses"], 4)
                if quality["responses"]
                else None,
                "trace_integrity_rate": round(quality["trace_parseable"] / quality["responses"], 4)
                if quality["responses"]
                else None,
                "grounded_citation_rate": round(
                    quality["grounded_with_valid_citations"] / quality["grounded_responses"],
                    4,
                )
                if quality["grounded_responses"]
                else None,
            },
            "quality_note": (
                "Chưa đủ phản hồi để kết luận chất lượng câu trả lời. "
                "Golden routing chỉ đo điều hướng, không đo độ đúng của đáp án."
                if len(feedback_rows) < 10
                else "Chỉ số phản hồi là tín hiệu trải nghiệm, không thay thế golden eval."
            ),
            "metric_lineage": {
                "audit": {
                    "source": "audit_events của tài khoản hiện tại trong 30 ngày",
                    "ordering": "created_at giảm dần",
                    "row_limit": 100,
                    "rows_returned": len(audits),
                    "completed_sample_size": len(completed),
                    "success_count": successes,
                    "success_denominator": len(completed),
                    "success_formula": "success_count / completed_sample_size",
                    "scope": "tool executions only; agent_task is reported separately",
                    "latency_sample_size": len(latencies),
                    "latency_p50_method": "median",
                    "latency_p95_method": "nearest-rank: sorted[ceil(0.95 × n) - 1]",
                },
                "tasks": {
                    "source": "agent_task audit_events của tài khoản hiện tại trong 30 ngày",
                    "completed_sample_size": len(task_completed),
                    "execution_success_count": task_successes,
                    "execution_success_denominator": len(task_completed),
                    "execution_success_formula": (
                        "agent_task audit rows with status=success / completed agent_task rows"
                    ),
                    "business_task_success": "N/A; requires an oracle or human review",
                    "automated_business_benchmark": {
                        "source": "publisher-validated local summary linked by SHA-256",
                        "sample_size": business_benchmark.get("sample_size"),
                        "passed": business_benchmark.get("passed"),
                        "pass_rate": business_benchmark.get("pass_rate"),
                        "manifest_sha256": business_benchmark.get("manifest_sha256"),
                        "report_sha256": business_benchmark.get("report_sha256"),
                        "scope": business_benchmark.get("scope"),
                    },
                },
                "current_runtime": {
                    "source": (
                        "audit_events trong 30 ngày từ runtime_started_at "
                        "của tiến trình hiện tại"
                    ),
                    "started_at": runtime_started_at,
                    "completed_sample_size": current_runtime["sample_size"],
                    "success_count": current_runtime["success_count"],
                    "error_count": current_runtime["error_count"],
                    "denied_count": current_runtime["denied_count"],
                    "latency_sample_size": current_runtime["latency_sample_size"],
                    "limitation": "chỉ gồm tối đa 100 audit mới nhất đã tải",
                },
                "feedback": {
                    "source": "response_feedback của tài khoản hiện tại trong 30 ngày",
                    "population_size": len(feedback_rows),
                    "helpful_count": helpful,
                    "helpful_denominator": len(feedback_rows),
                    "helpful_formula": "helpful_count / population_size",
                },
                "recent_output": {
                    "source": "các câu trả lời assistant trong 30 ngày của tài khoản hiện tại",
                    "row_limit": 6,
                    "sample_size": len(quality_runs),
                    "scope": "điểm trình bày quan sát được; không chứng minh đúng sự thật",
                },
                "citation_integrity": {
                    "source": "tối đa 50 câu trả lời assistant mới nhất của tài khoản hiện tại",
                    "row_limit": 50,
                    "response_sample_size": quality["responses"],
                    "responses_with_citations": quality["grounded_responses"],
                    "valid_cited_responses": quality["grounded_with_valid_citations"],
                    "denominator": quality["grounded_responses"],
                    "formula": "valid cited responses / responses with citations",
                    "limitation": "kiểm marker/file metadata; không kiểm tra entailment ngữ nghĩa",
                },
                "evaluated_at_utc": evaluated_at,
                "timezone": "UTC",
            },
        },
    }


@router.get("/routing-eval")
async def routing_evaluation(_user: CurrentUser):
    """Expose case-level evidence without calling Gemini or external services."""

    return run_routing_regression()


@router.get("/output-quality-eval")
async def output_quality_evaluation(_user: CurrentUser):
    """Expose case-level output rubric evidence without spending model quota."""

    return run_output_quality_regression()


@router.get("/answer-contract-eval")
async def answer_contract_evaluation(_user: CurrentUser):
    """Expose explicit reference-answer contracts; this never calls Gemini."""

    return run_answer_contract_benchmark()


@router.get("/adversarial-mutation-eval")
async def adversarial_mutation_evaluation(_user: CurrentUser):
    """Expose known-bad evaluator mutations; this is not a live-product score."""

    return run_adversarial_mutation_regression()
