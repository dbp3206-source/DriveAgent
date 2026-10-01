"""Verify an actual application HTTP request arrives in local Langfuse."""

import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

from app.core.config import get_settings
from app.services.local_otlp import LocalLangfuseExporter

root = Path(__file__).resolve().parents[1]
identity = "QA-APP-" + str(uuid4())
with urlopen(
    Request("http://127.0.0.1:8000/api/health", headers={"X-Request-ID": identity}),
    timeout=10,
) as response:
    status = response.status
trace_id = None
for path in get_settings().data_dir.joinpath("otel").glob("*.jsonl"):
    for line in path.read_text(encoding="utf-8").splitlines()[-1000:]:
        row = json.loads(line)
        if row.get("attributes", {}).get("request_id") == identity:
            trace_id = row["trace_id"]
if not trace_id:
    raise RuntimeError("Actual application trace not found")
exporter = LocalLangfuseExporter(
    "http://127.0.0.1:3035", root / "ops/secrets/langfuse-export.json"
)
rows = []
for _ in range(30):
    request = Request(
        f"http://127.0.0.1:3035/api/public/v2/observations?traceId={trace_id}&fields=basic,metadata,io",
        headers=exporter.headers,
    )
    with exporter.opener.open(request, timeout=8) as response:
        rows = json.loads(response.read()).get("data", [])
    if rows:
        break
    time.sleep(1)
report = {
    "application_http_status": status,
    "trace_id": trace_id,
    "observations": len(rows),
    "passed": status == 200
    and len(rows) == 1
    and rows[0].get("name") == "veridra.request",
    "model_calls": 0,
    "cloud_writes": 0,
}
(root / "design-work/qa/app-langfuse-20260930.json").write_text(
    json.dumps(report, indent=2)
)
print(json.dumps(report, indent=2))
raise SystemExit(int(not report["passed"]))
