"""OTLP/HTTP JSON metadata exporter to explicit local Langfuse only.

Builds the wire payload from an allowlist, never from arbitrary SDK attributes,
events, status descriptions, prompt content or resource identity. No redirects.
"""

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

SAFE_NAMES = {"veridra.request", "veridra.agent", "veridra.tool"}
SAFE_ATTRIBUTES = {"request_id", "tool", "http_status", "outcome"}


def local_endpoint(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname
        not in {"localhost", "127.0.0.1", "::1", "host.docker.internal", "langfuse-web"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("Langfuse export requires an explicit local HTTP base URL")
    return url.rstrip("/") + "/api/public/otel/v1/traces"


def metadata_payload(spans) -> dict:
    safe = []
    for span in spans:
        if span.name not in SAFE_NAMES:
            continue
        attrs = []
        for key, value in span.attributes.items():
            if key in SAFE_ATTRIBUTES:
                attrs.append({"key": key, "value": {"stringValue": str(value)[:200]}})
        attrs.append({"key": "langfuse.observation.type", "value": {"stringValue": "span"}})
        item = {
            "traceId": f"{span.context.trace_id:032x}",
            "spanId": f"{span.context.span_id:016x}",
            "name": span.name,
            "kind": 1,
            "startTimeUnixNano": str(span.start_time),
            "endTimeUnixNano": str(span.end_time),
            "attributes": attrs,
        }
        if span.parent:
            item["parentSpanId"] = f"{span.parent.span_id:016x}"
        safe.append(item)
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [{"key": "service.name", "value": {"stringValue": "veridra"}}]
                },
                "scopeSpans": [{"scope": {"name": "veridra.operations"}, "spans": safe}],
            }
        ]
    }


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LocalLangfuseExporter(SpanExporter):
    def __init__(self, base_url: str, credentials_file: Path):
        self.endpoint = local_endpoint(base_url)
        values = json.loads(credentials_file.read_text(encoding="utf-8"))
        public, secret = values["public_key"], values["secret_key"]
        if not public.startswith("pk-lf-") or not secret.startswith("sk-lf-"):
            raise ValueError("Invalid local Langfuse credentials")
        encoded = base64.b64encode(f"{public}:{secret}".encode()).decode()
        self.headers = {
            "Authorization": "Basic " + encoded,
            "Content-Type": "application/json",
            "x-langfuse-ingestion-version": "4",
        }
        # Do not send local telemetry/authentication through an environment proxy.
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def expire_metadata(self, now=None) -> int:
        """Delete only allowlisted old root traces in this key-scoped local project.

        Uses the free public API, not the enterprise retention feature. Bounded
        batches; failures propagate to the retention health flag without contents.
        """
        cutoff = (now or datetime.now(UTC)) - timedelta(days=30)
        base = self.endpoint.removesuffix("/otel/v1/traces")
        removed = 0
        cursor = None
        for _ in range(10):
            query = {
                "isRootObservation": "true",
                "toStartTime": cutoff.isoformat(),
                "fields": "basic",
                "limit": 1000,
            }
            if cursor:
                query["cursor"] = cursor
            request = Request(base + "/v2/observations?" + urlencode(query), headers=self.headers)
            with self.opener.open(request, timeout=3) as response:
                result = json.loads(response.read(2_000_000))
            ids = []
            for row in result.get("data", []):
                if row.get("name") not in SAFE_NAMES:
                    continue
                started = datetime.fromisoformat(
                    str(row.get("startTime", "")).replace("Z", "+00:00")
                )
                if started.tzinfo is not None and started < cutoff and row.get("traceId"):
                    ids.append(row["traceId"])
            ids = list(dict.fromkeys(ids))
            if ids:
                delete = Request(
                    base + "/traces",
                    data=json.dumps({"traceIds": ids}).encode(),
                    headers=self.headers,
                    method="DELETE",
                )
                with self.opener.open(delete, timeout=3) as response:
                    response.read(16384)
                removed += len(ids)
            cursor = result.get("meta", {}).get("cursor")
            if not cursor:
                break
        return removed

    def export(self, spans):
        payload = metadata_payload(spans)
        if not payload["resourceSpans"][0]["scopeSpans"][0]["spans"]:
            return SpanExportResult.SUCCESS
        request = Request(
            self.endpoint, data=json.dumps(payload).encode(), headers=self.headers, method="POST"
        )
        try:
            with self.opener.open(request, timeout=3) as response:
                body = json.loads(response.read(16384) or b"{}")
                if int(body.get("partialSuccess", {}).get("rejectedSpans", 0)) > 0:
                    return SpanExportResult.FAILURE
                return SpanExportResult.SUCCESS
        except (HTTPError, URLError, OSError, ValueError):
            return SpanExportResult.FAILURE
