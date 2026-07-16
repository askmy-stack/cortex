"""Tests for POST /remember."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.remember import _producer, _reset_producer_for_tests


@pytest.fixture(autouse=True)
def _clear_producer_singleton() -> None:
    _reset_producer_for_tests()
    yield
    _reset_producer_for_tests()


@patch("api.remember._producer")
def test_remember_publishes_to_kafka(mock_producer_factory: MagicMock) -> None:
    producer = MagicMock()
    producer.flush.return_value = 0
    mock_producer_factory.return_value = producer

    client = TestClient(app)
    response = client.post(
        "/remember",
        json={
            "workspace_id": "ws-1",
            "content": "We standardized on OpenTelemetry for all new services.",
            "author": "alice",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["topic"] == "cortex.raw.manual.events"
    producer.produce.assert_called_once()


def test_remember_rejects_short_content() -> None:
    client = TestClient(app)
    response = client.post(
        "/remember",
        json={"workspace_id": "ws-1", "content": "too short"},
    )
    assert response.status_code == 422


@patch("api.remember.Producer")
def test_producer_is_lazy_singleton(mock_producer_cls: MagicMock) -> None:
    """Same Producer instance is reused across calls; constructed once."""
    mock_producer_cls.return_value = MagicMock(name="shared-producer")

    first = _producer()
    second = _producer()

    assert first is second
    mock_producer_cls.assert_called_once()
