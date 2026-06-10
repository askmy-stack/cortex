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
    assert client_instance.post.call_args.kwargs["headers"]["X-Cortex-Roles"] == "authenticated"


@patch("sdk.client.httpx.Client")
def test_query_uses_bearer_when_api_key_set(mock_client_cls: MagicMock) -> None:
    response = MagicMock()
    response.json.return_value = {"total": 0, "results": []}
    response.raise_for_status = MagicMock()

    client_instance = MagicMock()
    client_instance.post.return_value = response
    client_instance.__enter__ = MagicMock(return_value=client_instance)
    client_instance.__exit__ = MagicMock(return_value=False)
    mock_client_cls.return_value = client_instance

    client = CortexClient("http://localhost:8000", api_key="sk_test")
    client.query("why redis?", workspace_id="ws-1")

    headers = client_instance.post.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer sk_test"
    assert "X-Cortex-Roles" not in headers
