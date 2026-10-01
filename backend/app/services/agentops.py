"""Privacy-bounded local AgentOps run metadata.

The agent's internal trace can contain free-form plan steps or notes. Persist
and return only a small, typed operational projection; chat content remains in
the chat record under its own lifecycle, never duplicated into telemetry.
"""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message

SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,96}\Z")
ALLOWED_STAGES = {
    "agent",
    "agent_handoff",
    "agent_selection",
    "context",
    "control_resolution",
    "deterministic_analysis",
    "model",
    "multi_agent",
    "orchestration",
    "output_contract",
    "output_guard",
    "plan",
    "planning",
    "presentation",
    "presentation_framework",
    "source_selection",
    "structured_repair",
    "synthesis",
    "tool",
    "tool_cache",
    "usage",
}
ALLOWED_STATUSES = {
    "cancelled",
    "corrected",
    "degraded",
    "denied",
    "error",
    "failed",
    "failure",
    "fallback",
    "ready",
    "routed",
    "running",
    "success",
    "tool_call",
    "warning",
}
IDENTIFIER_FIELDS = (
    "stage",
    "status",
    "tool",
    "agent",
    "from",
    "to",
    "model",
    "requested_model",
    "actual_model",
    "fallback_model",
    "rule",
    "mode",
)
COUNT_FIELDS = (
    "latency_ms",
    "prompt_token_count",
    "candidates_token_count",
    "total_token_count",
    "cached_content_token_count",
    "thoughts_token_count",
    "model_call_count",
    "provider_code",
    "affected_lines",
    "removed_lines",
    "step_count",
)
FLAG_FIELDS = ("cache_hit",)
ALLOWED_OUTPUT_VIOLATIONS = {
    "below_explicit_word_minimum",
    "above_explicit_word_maximum",
    "below_explicit_bullet_minimum",
    "below_explicit_numbered_step_minimum",
    "below_explicit_heading_minimum",
    "missing_explicit_markdown_table",
    "citation_markers_changed",
    "numeric_claims_added",
    "source_sections_dropped",
    "rewrite_truncated",
    "missing_action_section",
    "numeric_comparison_inconsistent",
}
RETENTION_DAYS = 30


def sanitize_run_trace(events: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    """Project untrusted trace values into bounded, non-content metadata."""

    safe_run_id = run_id if SAFE_IDENTIFIER.fullmatch(run_id) else "invalid-run-id"
    sanitized = []
    for event in events[:100]:
        if not isinstance(event, dict):
            continue
        item: dict[str, Any] = {"run_id": safe_run_id}
        for field in IDENTIFIER_FIELDS:
            value = event.get(field)
            if isinstance(value, str) and SAFE_IDENTIFIER.fullmatch(value):
                if field == "stage" and value not in ALLOWED_STAGES:
                    continue
                if field == "status" and value not in ALLOWED_STATUSES:
                    continue
                item[field] = value
        for field in COUNT_FIELDS:
            value = event.get(field)
            if type(value) is int and 0 <= value <= 10**12:
                item[field] = value
        for field in FLAG_FIELDS:
            value = event.get(field)
            if type(value) is bool:
                item[field] = value
        if item.get("stage") == "output_contract":
            for field in ("violations", "initial_violations"):
                values = event.get(field)
                if isinstance(values, list):
                    accepted = [
                        value for value in values[:8]
                        if isinstance(value, str) and value in ALLOWED_OUTPUT_VIOLATIONS
                    ]
                    if accepted:
                        item[field] = accepted
        for field in ("agents", "tools"):
            values = event.get(field)
            if isinstance(values, list):
                item[field] = [
                    value
                    for value in values[:16]
                    if isinstance(value, str) and SAFE_IDENTIFIER.fullmatch(value)
                ]
        steps = event.get("steps")
        if isinstance(steps, list):
            item["step_count"] = min(len(steps), 1000)
        if "stage" in item:
            sanitized.append(item)
    return sanitized


async def expire_run_traces(db: AsyncSession, *, now: datetime | None = None) -> int:
    """Erase only expired assistant trace metadata, preserving chat and audits."""

    current = now or datetime.now(UTC)
    cutoff = (current.astimezone(UTC) - timedelta(days=RETENTION_DAYS)).replace(tzinfo=None)
    result = await db.execute(
        update(Message)
        .where(
            Message.role == "assistant",
            Message.created_at < cutoff,
            Message.trace_json != "[]",
        )
        .values(trace_json="[]")
        .execution_options(synchronize_session=False)
    )
    return int(result.rowcount or 0)
