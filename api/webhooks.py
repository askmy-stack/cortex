"""Webhook ingress routes for connector plugins."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, status

from connectors.github.producer import GitHubConnector
from connectors.jira.producer import JiraConnector
from connectors.linear.producer import LinearConnector
from connectors.slack.producer import SlackConnector

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_slack_connector: SlackConnector | None = None
_github_connector: GitHubConnector | None = None
_jira_connector: JiraConnector | None = None
_linear_connector: LinearConnector | None = None


def _get_slack_connector() -> SlackConnector:
    global _slack_connector
    if _slack_connector is None:
        _slack_connector = SlackConnector()
    return _slack_connector


def _get_github_connector() -> GitHubConnector:
    global _github_connector
    if _github_connector is None:
        _github_connector = GitHubConnector()
    return _github_connector


def _get_jira_connector() -> JiraConnector:
    global _jira_connector
    if _jira_connector is None:
        _jira_connector = JiraConnector()
    return _jira_connector


def _get_linear_connector() -> LinearConnector:
    global _linear_connector
    if _linear_connector is None:
        _linear_connector = LinearConnector()
    return _linear_connector


def _parse_json_body(body: bytes) -> Any:
    """Decode a raw webhook body into JSON, returning HTTP 400 on malformed input."""
    try:
        return json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON payload",
        ) from exc


def _reject_invalid_signature(result: dict[str, Any]) -> dict[str, Any]:
    """Translate a connector's invalid-signature result into a 401 response."""
    if result.get("reason") == "invalid_signature":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )
    return result


def _verify_slack_signature(
    body: bytes,
    timestamp: str | None,
    signature: str | None,
    signing_secret: str,
) -> bool:
    if not timestamp or not signature:
        return False
    try:
        if abs(time.time() - int(timestamp)) > 60 * 5:
            return False
    except ValueError:
        return False

    base = f"v0:{timestamp}:{body.decode('utf-8')}".encode()
    expected = "v0=" + hmac.new(
        signing_secret.encode(),
        base,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/slack")
async def slack_webhook(
    request: Request,
    x_slack_signature: str | None = Header(default=None, alias="X-Slack-Signature"),
    x_slack_request_timestamp: str | None = Header(
        default=None,
        alias="X-Slack-Request-Timestamp",
    ),
    x_slack_retry_num: str | None = Header(default=None, alias="X-Slack-Retry-Num"),
) -> dict[str, Any]:
    """Receive Slack Events API callbacks."""
    body = await request.body()
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    if signing_secret and not _verify_slack_signature(
        body,
        x_slack_request_timestamp,
        x_slack_signature,
        signing_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Slack signature",
        )

    payload = _parse_json_body(body)
    retry_num: int | None = None
    if x_slack_retry_num is not None:
        try:
            retry_num = int(x_slack_retry_num)
        except ValueError:
            retry_num = None
    result = _get_slack_connector().handle_event(payload, slack_retry_num=retry_num)
    if "challenge" in result:
        return result
    return result


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(
        default=None,
        alias="X-Hub-Signature-256",
    ),
) -> dict[str, Any]:
    """Receive GitHub webhook payloads."""
    body = await request.body()
    payload = _parse_json_body(body)
    if x_github_event is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-GitHub-Event header",
        )
    return _reject_invalid_signature(
        _get_github_connector().handle_event(
            payload,
            event_type=x_github_event,
            signature=x_hub_signature_256,
            raw_body=body,
        )
    )


@router.post("/jira")
async def jira_webhook(
    request: Request,
    x_hub_signature: str | None = Header(default=None, alias="X-Hub-Signature"),
) -> dict[str, Any]:
    """Receive Jira webhook payloads."""
    body = await request.body()
    payload = _parse_json_body(body)
    return _reject_invalid_signature(
        _get_jira_connector().handle_event(
            payload,
            signature=x_hub_signature,
            raw_body=body,
        )
    )


@router.post("/linear")
async def linear_webhook(
    request: Request,
    linear_signature: str | None = Header(default=None, alias="Linear-Signature"),
) -> dict[str, Any]:
    """Receive Linear webhook payloads."""
    body = await request.body()
    payload = _parse_json_body(body)
    return _reject_invalid_signature(
        _get_linear_connector().handle_event(
            payload,
            signature=linear_signature,
            raw_body=body,
        )
    )
