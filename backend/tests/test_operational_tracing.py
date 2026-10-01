import json

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from app.services.operational_tracing import MetadataExporter


def test_local_export_preserves_parent_and_drops_private_fields(tmp_path):
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(MetadataExporter(tmp_path)))
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("veridra.request") as root:
        root.set_attribute("request_id", "safe-request")
        root.set_attribute("prompt", "private content")
        with tracer.start_as_current_span("veridra.tool") as child:
            child.set_attribute("tool", "gmail_read_thread")
            child.set_attribute("api_key", "secret")
    rows = [
        json.loads(line)
        for path in tmp_path.glob("*.jsonl")
        for line in path.read_text().splitlines()
    ]
    assert rows[0]["parent_span_id"] == rows[1]["span_id"]
    assert rows[0]["trace_id"] == rows[1]["trace_id"]
    assert "private" not in json.dumps(rows)
    assert "secret" not in json.dumps(rows)
