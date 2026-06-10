"""Tests for api/telemetry.py."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from fastapi import FastAPI

import api.telemetry as telemetry_module
from api.telemetry import setup_telemetry


def _install_fake_otel_modules(instrumentor_cls: MagicMock) -> None:
    """Inject stub opentelemetry modules (optional dep may be absent in CI)."""
    trace_mod = MagicMock()
    exporter_mod = MagicMock(OTLPSpanExporter=MagicMock())
    resource_mod = MagicMock(Resource=MagicMock(create=MagicMock(return_value="resource")))
    provider_mod = MagicMock(TracerProvider=MagicMock(return_value=MagicMock()))
    export_mod = MagicMock(BatchSpanProcessor=MagicMock())

    sys.modules["opentelemetry"] = MagicMock(trace=trace_mod)
    sys.modules["opentelemetry.instrumentation"] = MagicMock()
    sys.modules["opentelemetry.instrumentation.fastapi"] = MagicMock(
        FastAPIInstrumentor=instrumentor_cls,
    )
    sys.modules["opentelemetry.exporter"] = MagicMock()
    sys.modules["opentelemetry.exporter.otlp"] = MagicMock()
    sys.modules["opentelemetry.exporter.otlp.proto"] = MagicMock()
    sys.modules["opentelemetry.exporter.otlp.proto.http"] = MagicMock()
    sys.modules["opentelemetry.exporter.otlp.proto.http.trace_exporter"] = exporter_mod
    sys.modules["opentelemetry.sdk"] = MagicMock()
    sys.modules["opentelemetry.sdk.resources"] = resource_mod
    sys.modules["opentelemetry.sdk.trace"] = provider_mod
    sys.modules["opentelemetry.sdk.trace.export"] = export_mod


def test_setup_telemetry_skipped_without_endpoint(monkeypatch) -> None:
    telemetry_module._CONFIGURED = False
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    app = FastAPI()
    assert setup_telemetry(app) is False


def test_setup_telemetry_enables_with_endpoint(monkeypatch) -> None:
    telemetry_module._CONFIGURED = False
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "cortex-api-test")
    app = FastAPI()

    instrumentor_cls = MagicMock()
    with patch.dict(sys.modules, {}, clear=False):
        _install_fake_otel_modules(instrumentor_cls)
        assert setup_telemetry(app) is True
        instrumentor_cls.instrument_app.assert_called_once()
