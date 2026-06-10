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
    # Forged/invalid signatures are rejected with 401 (not a 200 error body).
    assert response.status_code == 401


def test_github_missing_signature_with_secret_rejected() -> None:
    from connectors.github.producer import GitHubConnector

    conn = GitHubConnector(webhook_secret="topsecret")
    # Secret configured but no signature supplied → must be rejected, not skipped.
    result = conn.handle_event({"action": "opened"}, event_type="pull_request")
    assert result["reason"] == "invalid_signature"


def test_jira_signature_roundtrip() -> None:
    from connectors.jira.producer import verify_jira_signature

    secret = "jira-secret"
    body = b'{"webhookEvent":"jira:issue_created"}'
    good = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_jira_signature(body, good, secret) is True
    assert verify_jira_signature(body, "sha256=wrong", secret) is False
    assert verify_jira_signature(body, "md5=nope", secret) is False


def test_jira_missing_signature_with_secret_rejected() -> None:
    from connectors.jira.producer import JiraConnector

    conn = JiraConnector(webhook_secret="jira-secret")
    result = conn.handle_event({"webhookEvent": "jira:issue_created"})
    assert result["reason"] == "invalid_signature"


def test_linear_missing_signature_with_secret_rejected() -> None:
    from connectors.linear.producer import LinearConnector

    conn = LinearConnector(webhook_secret="linear-secret")
    result = conn.handle_event({"type": "Issue", "action": "create", "data": {}})
    assert result["reason"] == "invalid_signature"


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
