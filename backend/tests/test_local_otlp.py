import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.error import URLError

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

from app.services.local_otlp import (
    LocalLangfuseExporter,
    NoRedirect,
    local_endpoint,
    metadata_payload,
)


def exporter(tmp_path):
    credentials = tmp_path / "credentials.json"
    credentials.write_text(json.dumps({"public_key": "pk-lf-test", "secret_key": "sk-lf-test"}))
    return LocalLangfuseExporter("http://127.0.0.1:3035", credentials)


def response(body):
    result = Mock()
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    result.read.return_value = json.dumps(body).encode()
    return result


@pytest.mark.parametrize(
    "body,expected",
    [
        ({}, SpanExportResult.SUCCESS),
        ({"partialSuccess": {"rejectedSpans": "1"}}, SpanExportResult.FAILURE),
    ],
)
def test_export_handles_server_result_without_private_attributes(tmp_path, body, expected):
    service = exporter(tmp_path)
    service.opener = Mock()
    service.opener.open.return_value = response(body)
    span = SimpleNamespace(
        name="veridra.request",
        attributes={"prompt": "private"},
        context=SimpleNamespace(trace_id=1, span_id=2),
        parent=None,
        start_time=1,
        end_time=2,
    )
    assert service.export([span]) == expected
    assert b"private" not in service.opener.open.call_args.args[0].data
    service.opener.open.side_effect = URLError("private-error")
    assert service.export([span]) == SpanExportResult.FAILURE
    assert service.export([]) == SpanExportResult.SUCCESS


def test_expire_only_old_allowlisted_roots_in_local_project(tmp_path):
    service = exporter(tmp_path)
    service.opener = Mock()
    service.opener.open.side_effect = [
        response(
            {
                "data": [
                    {
                        "name": "veridra.request",
                        "startTime": "2026-08-01T00:00:00Z",
                        "traceId": "old",
                    },
                    {
                        "name": "another-app",
                        "startTime": "2026-08-01T00:00:00Z",
                        "traceId": "other",
                    },
                    {
                        "name": "veridra.request",
                        "startTime": "2026-09-30T00:00:00Z",
                        "traceId": "new",
                    },
                ]
            }
        ),
        response({}),
    ]
    assert service.expire_metadata(datetime(2026, 9, 30, tzinfo=UTC)) == 1
    request = service.opener.open.call_args.args[0]
    assert request.method == "DELETE"
    assert json.loads(request.data) == {"traceIds": ["old"]}
    assert NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.test") is None


def test_invalid_local_credentials_are_rejected(tmp_path):
    credentials = tmp_path / "invalid.json"
    credentials.write_text('{"public_key":"other", "secret_key":"other"}')
    with pytest.raises(ValueError):
        LocalLangfuseExporter("http://localhost:3035", credentials)


@pytest.mark.parametrize(
    "url",
    [
        "https://cloud.langfuse.com",
        "http://example.com",
        "http://localhost@evil.test",
        "http://localhost?secret=x",
    ],
)
def test_export_cannot_send_to_remote_or_credential_url(url):
    with pytest.raises(ValueError):
        local_endpoint(url)


def test_otlp_wire_payload_preserves_parent_and_removes_private_content():
    rows = []

    class Collector(SpanExporter):
        def export(self, spans):
            rows.extend(spans)
            return SpanExportResult.SUCCESS

    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(Collector()))
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("veridra.request") as parent:
        parent.set_attribute("prompt", "private-mail-body")
        with tracer.start_as_current_span("veridra.tool") as child:
            child.set_attribute("api_key", "private-api-key")
            child.set_attribute("tool", "calculator")
            child.add_event("private-event", {"input": "private-event-body"})
    payload = metadata_payload(rows)
    encoded = json.dumps(payload)
    assert "private" not in encoded
    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert spans[0]["parentSpanId"] == spans[1]["spanId"]
    assert spans[0]["traceId"] == spans[1]["traceId"]
    assert local_endpoint("http://127.0.0.1:3035").endswith("/api/public/otel/v1/traces")
