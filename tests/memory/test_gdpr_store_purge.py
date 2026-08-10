"""Unit tests for Qdrant + Timescale GDPR purge helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from memory.episodic import purge_raw_events_for_person
from memory.semantic import delete_decision_vectors


@patch("memory.semantic._client")
def test_delete_decision_vectors_uses_deterministic_point_ids(mock_client: MagicMock) -> None:
    client = MagicMock()
    mock_client.return_value = client
    deleted = delete_decision_vectors(["dec-1", "dec-2"], "ws-1")
    assert deleted == 2
    client.delete.assert_called_once()
    kwargs = client.delete.call_args.kwargs
    assert len(kwargs["points_selector"]) == 2


@patch("memory.semantic._client", return_value=None)
def test_delete_decision_vectors_noop_when_disabled(_mock: MagicMock) -> None:
    assert delete_decision_vectors(["dec-1"], "ws-1") == 0


@patch("memory.episodic._timescale_dsn", return_value=None)
def test_purge_raw_events_noop_without_dsn(_mock: MagicMock) -> None:
    assert purge_raw_events_for_person("ws-1", "alice@x.com") == 0
