"""OpenTelemetry tracing for the Cortex API.

Tracing is enabled when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set (HTTP/protobuf OTLP).
Prometheus metrics remain on ``GET /metrics``; traces export to your collector or SaaS.

Environment:
  OTEL_EXPORTER_OTLP_ENDPOINT — e.g. http://otel-collector:4318/v1/traces
  OTEL_SERVICE_NAME — defaults to ``cortex-api``
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

log = structlog.get_logger(__name__)

_CONFIGURED = False


def setup_telemetry(app: FastAPI) -> bool:
    """Instrument FastAPI with OTLP export when configured.

    Returns True when tracing was enabled, False when skipped (no endpoint).
    Idempotent — safe to call once at import time.
    """
    global _CONFIGURED  # noqa: PLW0603
    if _CONFIGURED:
        return True

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        log.info("telemetry.disabled", reason="OTEL_EXPORTER_OTLP_ENDPOINT unset")
        return False

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    service_name = os.environ.get("OTEL_SERVICE_NAME", "cortex-api").strip() or "cortex-api"
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": os.environ.get("CORTEX_VERSION", "0.1.0"),
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="/metrics,/health",
    )
    _CONFIGURED = True
    log.info("telemetry.enabled", endpoint=endpoint, service_name=service_name)
    return True
