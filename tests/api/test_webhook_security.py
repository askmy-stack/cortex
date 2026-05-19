"""Webhook security and error paths."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app


def test_github_webhook_missing_event_header() -> None:
    client = TestClient(app)
    response = client.post("/webhooks/github", content=b"{}")
    assert response.status_code == 400


@patch("api.webhooks._get_github_connector")
def test_github_invalid_signature(mock_get: MagicMock) -> None:
    connector = MagicMock()
    connector.handle_event.return_value = {"status": "error", "reason": "invalid_signature"}
    mock_get.return_value = connector

    client = TestClient(app)
    response = client.post(
        "/webhooks/github",
        content=json.dumps({"action": "opened"}).encode(),
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "error"


@patch("api.webhooks._get_slack_connector")
def test_slack_invalid_signature_rejected(mock_get: MagicMock) -> None:
    mock_get.return_value = MagicMock()
    client = TestClient(app)
    with patch.dict("os.environ", {"SLACK_SIGNING_SECRET": "secret"}, clear=False):
        body = b'{"type":"event_callback"}'
        response = client.post(
            "/webhooks/slack",
            content=body,
            headers={
                "X-Slack-Signature": "v0=invalid",
                "X-Slack-Request-Timestamp": "1700000000",
            },
        )
    assert response.status_code == 401
