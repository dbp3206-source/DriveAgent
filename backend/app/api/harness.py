"""Inspectable Harness and evaluation data derived from the current user's real runs."""

import json
import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DbSession
from app.auth.permissions import permissions_for_role
from app.core.config import get_settings
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
from app.services.evaluation import run_routing_regression
from app.services.protocols import READ_TOOLS
from app.services.skills import SkillStore
from app.services.visuals import VisualStore

router = APIRouter(prefix="/api/harness", tags=["harness"])


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
    indexed_files = await count(DriveFileIndex, DriveFileIndex.user_id == user.id)
    indexed_chunks = await count(DocumentChunk, DocumentChunk.user_id == user.id)

    audits = list(
        (
            await db.scalars(
                select(AuditEvent)
                .where(AuditEvent.user_id == user.id)
                .order_by(AuditEvent.created_at.desc())
                .limit(100)
            )
        ).all()
    )
    completed = [row for row in audits if row.status != "started"]
    successes = sum(row.status == "success" for row in completed)
    latencies = sorted(row.latency_ms for row in completed if row.latency_ms is not None)

    feedback_rows = list(
        (
            await db.scalars(
                select(ResponseFeedback)
                .where(ResponseFeedback.user_id == user.id)
                .order_by(ResponseFeedback.updated_at.desc())
            )
        ).all()
    )
    helpful = sum(row.rating > 0 for row in feedback_rows)
    traces = list(
        (
            await db.scalars(
                select(Message.trace_json)
                .where(Message.user_id == user.id, Message.role == "assistant")
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
                .where(Message.user_id == user.id, Message.role == "assistant")
                .order_by(Message.created_at.desc())
                .limit(50)
            )
        ).all()
    )
    quality["responses"] = len(message_rows)
    for content, citations_json, trace_json in message_rows:
        quality["nonempty"] += int(bool(content.strip()))
        try:
            citations = json.loads(citations_json or "[]")
            trace = json.loads(trace_json or "[]")
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
                markers = [int(value) for value in re.findall(r"\[(\d+)\]", content)]
                markers_resolve = bool(markers) and all(
                    1 <= value <= len(citations) for value in markers
                )
                quality["grounded_with_valid_citations"] += int(valid and markers_resolve)
        except (TypeError, json.JSONDecodeError):
            pass
    for trace_json in traces:
        has_usage = False
        for event in json.loads(trace_json or "[]"):
            if event.get("stage") != "usage":
                continue
            has_usage = True
            for source, target in (
                ("prompt_token_count", "prompt_tokens"),
                ("candidates_token_count", "output_tokens"),
                ("total_token_count", "total_tokens"),
            ):
                usage[target] += int(event.get(source) or 0)
        measured_runs += int(has_usage)

    p95_index = max(0, int(len(latencies) * 0.95) - 1)
    routing_eval = run_routing_regression()
    visuals = VisualStore(settings.data_dir).list(user.id)
    skills = SkillStore(settings.data_dir).list(user.id)
    return {
        "runtime": {
            "orchestrator": settings.orchestrator_backend,
            "orchestrator_class": type(request.app.state.orchestrator).__name__,
            "primary_model": settings.gemini_chat_model,
            "fallback_model": settings.gemini_fallback_model,
            "embedding_model": settings.gemini_embedding_model,
            "embedding_dimensions": EMBEDDING_DIMENSION,
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
            "google_outputs": ["Docs", "Slides", "Sheets"],
            "visuals": len(visuals),
            "skills": len(skills),
            "approval_flow": "preview → digest → approve → execute → verify",
            "local_visual_formats": ["PNG", "SVG"],
        },
        "orchestration": {
            "stages": ["planning", "routing", "tool", "synthesis", "recovery"],
            "checkpoint": (
                "LangGraph SQLite"
                if settings.orchestrator_backend == "langgraph"
                else "ADK session"
            ),
        },
        "protocols": {
            "mcp": {"enabled": True, "mode": "read_only", "tools": sorted(READ_TOOLS)},
            "a2a": {"enabled": True, "mode": "read_only", "tools": sorted(READ_TOOLS)},
            "multi_agent_runtime": settings.orchestrator_backend == "adk",
        },
        "evaluation": {
            "routing_regression": {
                key: value for key, value in routing_eval.items() if key != "cases"
            },
            "audit_sample_size": len(completed),
            "tool_success_rate": round(successes / len(completed), 4) if completed else None,
            "latency_p50_ms": latencies[len(latencies) // 2] if latencies else None,
            "latency_p95_ms": latencies[p95_index] if latencies else None,
            "feedback_count": len(feedback_rows),
            "helpful_rate": round(helpful / len(feedback_rows), 4) if feedback_rows else None,
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
        },
    }


@router.get("/routing-eval")
async def routing_evaluation(_user: CurrentUser):
    """Expose case-level evidence without calling Gemini or external services."""

    return run_routing_regression()
