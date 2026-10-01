"""Privacy-bounded Prometheus metrics for local AgentOps monitoring."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from hmac import compare_digest

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import CollectorRegistry, Counter, Gauge, generate_latest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import AuditEvent, Message
from app.db.session import SessionFactory
from app.services.relational_circuit import open_circuit_count

router = APIRouter(tags=["agentops"])


def _authorized(request: Request) -> bool:
    settings = get_settings()
    if settings.is_local_environment:
        return True
    expected = settings.metrics_bearer_token
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    return bool(expected and supplied and compare_digest(expected, supplied))


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics(request: Request) -> Response:
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Metrics token required")
    cutoff = (datetime.now(UTC) - timedelta(days=30)).replace(tzinfo=None)
    async with SessionFactory() as db:
        audits = list(
            (await db.scalars(select(AuditEvent).where(AuditEvent.created_at >= cutoff))).all()
        )
        traces = list(
            (
                await db.scalars(
                    select(Message.trace_json).where(
                        Message.role == "assistant",
                        Message.created_at >= cutoff,
                        Message.trace_json != "[]",
                    )
                )
            ).all()
        )
    registry = CollectorRegistry()
    requests = Counter(
        "drive_agent_tool_requests_total",
        "Tool requests completed in the retained window.",
        ("tool", "status"),
        registry=registry,
    )
    latency = Gauge(
        "drive_agent_tool_latency_ms_sum",
        "Cumulative tool latency in milliseconds in the retained window.",
        ("tool",),
        registry=registry,
    )
    tokens = Gauge(
        "drive_agent_model_tokens_total",
        "Model token usage in retained run traces.",
        ("kind",),
        registry=registry,
    )
    runs = Gauge(
        "drive_agent_observed_runs",
        "Assistant runs containing privacy-bounded telemetry.",
        registry=registry,
    )
    estimated_cost = Gauge(
        "drive_agent_model_estimated_cost_usd_total",
        "Estimated model cost for retained traces using operator-configured prices.",
        registry=registry,
    )
    cost_per_run = Gauge(
        "drive_agent_model_estimated_cost_usd_per_run",
        "Estimated model cost divided by observed run count.",
        registry=registry,
    )
    cache_hits = Gauge(
        "veridra_model_cache_hits_total",
        "Privacy-safe model/tool cache hit count in retained traces.",
        registry=registry,
    )
    circuits_open = Gauge(
        "veridra_gemini_circuits_open",
        "Number of credential-scoped Gemini capability circuits currently open.",
        registry=registry,
    )
    for row in audits:
        if row.status == "started":
            continue
        requests.labels(tool=row.tool_name, status=row.status).inc()
        latency.labels(tool=row.tool_name).inc(row.latency_ms or 0)
    run_count = 0
    prompt_tokens = output_tokens = cache_hit_count = 0
    for raw in traces:
        try:
            events = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        run_count += 1
        for event in events if isinstance(events, list) else []:
            if not isinstance(event, dict):
                continue
            if event.get("cache_hit") is True:
                cache_hit_count += 1
            if event.get("stage") != "usage":
                continue
            prompt_tokens += int(event.get("prompt_token_count") or 0)
            output_tokens += int(event.get("candidates_token_count") or 0)
    runs.set(run_count)
    tokens.labels(kind="prompt").set(prompt_tokens)
    tokens.labels(kind="output").set(output_tokens)
    cache_hits.set(cache_hit_count)
    settings = get_settings()
    open_count = await asyncio.to_thread(
        open_circuit_count, settings, now=datetime.now(UTC).timestamp()
    )
    circuits_open.set(open_count)
    cost = (
        prompt_tokens * settings.gemini_input_usd_per_million
        + output_tokens * settings.gemini_output_usd_per_million
    ) / 1_000_000
    estimated_cost.set(cost)
    cost_per_run.set(cost / run_count if run_count else 0)
    return Response(
        generate_latest(registry),
        media_type="text/plain; version=0.0.4; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )
