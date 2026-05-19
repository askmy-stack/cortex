"""Tests for sdk/client.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sdk.client import CortexClient


@patch("sdk.client.httpx.Client")
def test_query_calls_post(mock_client_cls: MagicMock) -> None:
    response = MagicMock()
    response.json.return_value = {"total": 0, "results": []}
    response.raise_for_status = MagicMock()

    client_instance = MagicMock()
    client_instance.post.return_value = response
    client_instance.__enter__ = MagicMock(return_value=client_instance)
    client_instance.__exit__ = MagicMock(return_value=False)
    mock_client_cls.return_value = client_instance

    client = CortexClient("http://localhost:8000")
    payload = client.query("why redis?", workspace_id="ws-1")

    assert payload["total"] == 0
    client_instance.post.assert_called_once()
