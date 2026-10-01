"""Synthetic OTel ingestion/readback; no model calls or private source content."""

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.request import Request
from uuid import uuid4

from app.services.local_otlp import LocalLangfuseExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

ROOT = Path(__file__).resolve().parents[1]


def main():
    exporter = LocalLangfuseExporter(
        "http://127.0.0.1:3035", ROOT / "ops/secrets/langfuse-export.json"
    )
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter, schedule_delay_millis=500))
    tracer = provider.get_tracer("veridra.operations")
    with tracer.start_as_current_span("veridra.request") as root:
        trace_id = f"{root.get_span_context().trace_id:032x}"
        root.set_attribute("request_id", "QA-" + str(uuid4()))
        root.set_attribute("prompt", "private-canary-not-exported")
        with tracer.start_as_current_span("veridra.tool") as child:
            child.set_attribute("tool", "calculator")
            child.set_attribute("api_key", "private-canary-not-exported")
    flushed = provider.force_flush(timeout_millis=10000)
    observations = []
    status = 0
    for _ in range(45):
        request = Request(
            f"http://127.0.0.1:3035/api/public/v2/observations?traceId={trace_id}&fields=basic,metadata,io",
            headers=exporter.headers,
        )
        with exporter.opener.open(request, timeout=8) as response:
            status = response.status
            observations = json.loads(response.read()).get("data", [])
        if len(observations) >= 2:
            break
        time.sleep(1)
    names = sorted(row.get("name", "") for row in observations)
    private_absent = "private-canary" not in json.dumps(observations)
    aged_ns = int((datetime.now(UTC) - timedelta(days=31)).timestamp() * 1e9)
    aged = tracer.start_span("veridra.request", start_time=aged_ns)
    aged_id = f"{aged.get_span_context().trace_id:032x}"
    aged.end(end_time=aged_ns + 1_000_000)
    provider.force_flush(timeout_millis=10000)

    def rows_for(identity):
        req = Request(
            f"http://127.0.0.1:3035/api/public/v2/observations?traceId={identity}&fields=basic",
            headers=exporter.headers,
        )
        with exporter.opener.open(req, timeout=8) as result:
            return json.loads(result.read()).get("data", [])

    aged_visible = False
    for _ in range(30):
        if rows_for(aged_id):
            aged_visible = True
            break
        time.sleep(1)
    removed = exporter.expire_metadata()
    retention_passed = False
    for _ in range(30):
        if not rows_for(aged_id):
            retention_passed = (
                aged_visible and removed > 0 and len(rows_for(trace_id)) == 2
            )
            break
        time.sleep(1)
    report = {
        "flushed": flushed,
        "http_status": status,
        "observation_count": len(observations),
        "names": names,
        "trace_id": trace_id,
        "private_content_absent": private_absent,
        "retention_aged_trace_removed_current_trace_kept": retention_passed,
        "passed": flushed
        and status == 200
        and len(observations) == 2
        and names == ["veridra.request", "veridra.tool"]
        and private_absent
        and retention_passed,
        "model_calls": 0,
        "cloud_writes": 0,
        "destination": "local Langfuse only",
    }
    (ROOT / "design-work/qa/langfuse-local-20260930.json").write_text(
        json.dumps(report, indent=2)
    )
    print(json.dumps(report, indent=2))
    provider.shutdown()
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
