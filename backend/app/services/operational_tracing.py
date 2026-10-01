"""OpenTelemetry spans with metadata-only local export and 30-day retention.

No prompt, arguments, mail body, exception text, identity or API key is exported.
An explicitly configured local-only Langfuse exporter is optional.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

_lock = Lock()
_init_lock = Lock()
_provider = None
_local_exporter = None
logger = logging.getLogger(__name__)


class MetadataExporter(SpanExporter):
    def __init__(self, root: Path):
        self.root = root

    def export(self, spans):
        try:
            with _lock:
                self.root.mkdir(parents=True, exist_ok=True)
                now = datetime.now(UTC)
                for path in self.root.glob("trace-????????.jsonl"):
                    if datetime.fromtimestamp(path.stat().st_mtime, UTC) < now - timedelta(days=30):
                        path.unlink()
                path = self.root / f"trace-{now:%Y%m%d}.jsonl"
                with path.open("a", encoding="utf-8") as stream:
                    for span in spans:
                        attrs = {
                            key: value
                            for key, value in span.attributes.items()
                            if key in {"request_id", "tool", "http_status", "outcome"}
                        }
                        stream.write(
                            json.dumps(
                                {
                                    "name": span.name,
                                    "trace_id": f"{span.context.trace_id:032x}",
                                    "span_id": f"{span.context.span_id:016x}",
                                    "parent_span_id": f"{span.parent.span_id:016x}"
                                    if span.parent
                                    else None,
                                    "start_ns": span.start_time,
                                    "end_ns": span.end_time,
                                    "attributes": attrs,
                                }
                            )
                            + "\n"
                        )
            return SpanExportResult.SUCCESS
        except OSError:
            logger.warning("Local span export unavailable; no user content logged")
            return SpanExportResult.FAILURE


def tracer():
    global _provider, _local_exporter
    with _init_lock:
        if _provider is not None:
            return _provider.get_tracer("veridra.operations")
        from app.core.config import get_settings

        provider = TracerProvider()
        provider.add_span_processor(
            SimpleSpanProcessor(MetadataExporter(get_settings().data_dir / "otel"))
        )
        settings = get_settings()
        if settings.langfuse_local_url and settings.langfuse_credentials_file:
            from app.services.local_otlp import LocalLangfuseExporter

            try:
                _local_exporter = LocalLangfuseExporter(
                    settings.langfuse_local_url, settings.langfuse_credentials_file
                )
                provider.add_span_processor(
                    BatchSpanProcessor(
                        _local_exporter,
                        max_queue_size=256,
                        max_export_batch_size=32,
                        schedule_delay_millis=1000,
                    )
                )
            except (OSError, ValueError, KeyError):
                logger.warning(
                    "Optional local Langfuse exporter unavailable; local traces retained"
                )
        _provider = provider
    return _provider.get_tracer("veridra.operations")


def expire_local_langfuse_metadata():
    return _local_exporter.expire_metadata() if _local_exporter is not None else 0


def flush_operational_traces():
    if _provider is not None:
        return _provider.force_flush(timeout_millis=5000)
    return True
