"""Tests for api/telemetry.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI

import api.telemetry as telemetry_module
from api.telemetry import setup_telemetry


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

    with patch("opentelemetry.instrumentation.fastapi.FastAPIInstrumentor") as instrumentor:
        instrumentor.instrument_app = MagicMock()
        assert setup_telemetry(app) is True
        instrumentor.instrument_app.assert_called_once()
