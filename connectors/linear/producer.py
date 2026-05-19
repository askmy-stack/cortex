"""Linear connector — transforms Linear webhook payloads into RawEvents.

Handles:
  - Issue create / update
  - Comment create

Publishes to Kafka topic: cortex.raw.linear.events
Decision: D-001 — Kafka as single event bus.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import UTC, datetime
from typing import Any

import structlog
from confluent_kafka import KafkaException, Producer
from pydantic import ValidationError

from shared.models import RawEvent

log = structlog.get_logger(__name__)

KAFKA_TOPIC = "cortex.raw.linear.events"
SCHEMA_VERSION = "1.0"

_HANDLED_TYPES = frozenset({"Issue", "Comment"})


def verify_linear_signature(
    payload_bytes: bytes,
    signature_header: str,
    secret: str,
) -> bool:
    """Verify Linear webhook HMAC-SHA256 signature."""
    if not signature_header or not secret:
        return False
    expected = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _parse_timestamp(ts: str | None) -> datetime:
    if not ts:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now(UTC)


def _normalise_issue(payload: dict[str, Any], workspace_id: str) -> RawEvent | None:
    action = payload.get("action", "")
    data = payload.get("data", {})
    if action not in {"create", "update"}:
        return None

    issue_id = data.get("id", "")
    title = data.get("title", "")
    description = (data.get("description") or "")[:500]
    team = (data.get("team") or {}).get("key", "linear")
    state = (data.get("state") or {}).get("name", "")
    content = f"Issue {action}: {title}"
    if description:
        content += f"\n\n{description}"
    if state:
        content += f"\n(state: {state})"

    author = (data.get("creator") or {}).get("email") or (
        (data.get("assignee") or {}).get("email") or "unknown"
    )

    return RawEvent(
        source="linear",
        source_id=f"linear:issue:{issue_id}",
        workspace_id=workspace_id,
        event_type=f"linear:issue:{action}",
        content=content,
        author=author,
        channel=team,
        timestamp=_parse_timestamp(data.get("updatedAt") or data.get("createdAt")),
        metadata={
            "issue_id": issue_id,
            "identifier": data.get("identifier"),
            "priority": data.get("priority"),
            "state": state,
            "labels": [lb.get("name") for lb in data.get("labels", [])],
        },
        schema_version=SCHEMA_VERSION,
    )


def _normalise_comment(payload: dict[str, Any], workspace_id: str) -> RawEvent | None:
    if payload.get("action") != "create":
        return None
    data = payload.get("data", {})
    body = (data.get("body") or "")[:800]
    if not body.strip():
        return None
    issue = data.get("issue") or {}
    issue_id = issue.get("id", "unknown")
    author = (data.get("user") or {}).get("email", "unknown")
    team = (issue.get("team") or {}).get("key", "linear")

    return RawEvent(
        source="linear",
        source_id=f"linear:comment:{data.get('id', '')}",
        workspace_id=workspace_id,
        event_type="linear:comment:create",
        content=f"Comment on {issue.get('identifier', issue_id)}: {body}",
        author=author,
        channel=team,
        timestamp=_parse_timestamp(data.get("createdAt")),
        metadata={"issue_id": issue_id, "comment_id": data.get("id")},
        schema_version=SCHEMA_VERSION,
    )


def normalise_linear_event(
    payload: dict[str, Any],
    workspace_id: str,
) -> RawEvent | None:
    """Route a Linear webhook payload to the correct normaliser."""
    event_type = payload.get("type", "")
    if event_type not in _HANDLED_TYPES:
        log.debug("linear.event.skipped", event_type=event_type)
        return None
    try:
        if event_type == "Issue":
            return _normalise_issue(payload, workspace_id)
        return _normalise_comment(payload, workspace_id)
    except (KeyError, ValidationError) as exc:
        log.error("linear.event.normalisation_failed", error=str(exc))
        return None


class LinearKafkaProducer:
    """Publishes normalised Linear RawEvents to Kafka."""

    def __init__(self, bootstrap_servers: str | None = None) -> None:
        servers = bootstrap_servers or os.environ.get(
            "KAFKA_BOOTSTRAP_SERVERS",
            "localhost:9092",
        )
        self._producer = Producer(
            {
                "bootstrap.servers": servers,
                "acks": "all",
                "enable.idempotence": True,
            }
        )

    def publish(self, raw_event: RawEvent) -> None:
        key = f"{raw_event.workspace_id}:{raw_event.source_id}".encode()
        self._producer.produce(
            topic=KAFKA_TOPIC,
            key=key,
            value=raw_event.model_dump_json().encode("utf-8"),
        )
        self._producer.poll(0)

    def flush(self, timeout: float = 10.0) -> None:
        self._producer.flush(timeout)

    def close(self) -> None:
        self.flush()


class LinearConnector:
    """Entry point for the Linear connector."""

    def __init__(
        self,
        workspace_id: str | None = None,
        bootstrap_servers: str | None = None,
        webhook_secret: str | None = None,
    ) -> None:
        self.workspace_id = workspace_id or os.environ.get(
            "CORTEX_WORKSPACE_ID",
            "local-dev",
        )
        self._webhook_secret = webhook_secret or os.environ.get(
            "LINEAR_WEBHOOK_SECRET",
            "",
        )
        self._producer = LinearKafkaProducer(bootstrap_servers=bootstrap_servers)
        log.info(
            "linear.connector.initialized",
            workspace_id=self.workspace_id,
        )

    def handle_event(
        self,
        payload: dict[str, Any],
        signature: str | None = None,
        raw_body: bytes | None = None,
    ) -> dict[str, str]:
        if self._webhook_secret and signature and raw_body:
            if not verify_linear_signature(raw_body, signature, self._webhook_secret):
                return {"status": "error", "reason": "invalid_signature"}

        raw_event = normalise_linear_event(payload, self.workspace_id)
        if raw_event is None:
            return {"status": "skipped", "reason": "not_processable"}

        try:
            self._producer.publish(raw_event)
        except KafkaException as exc:
            log.error("linear.kafka_failed", error=str(exc))
            return {"status": "error", "reason": "kafka_publish_failed"}

        return {"status": "ok", "event_id": raw_event.event_id}

    def close(self) -> None:
        self._producer.close()
