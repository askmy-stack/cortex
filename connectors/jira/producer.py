"""Jira connector — transforms Jira webhook payloads into RawEvents.

Handles:
  - jira:issue_created
  - jira:issue_updated  (status transitions, priority changes, field updates)
  - jira:issue_commented
  - jira:sprint_started / sprint_closed  (important org rhythm signals)

Architecture (ARCHITECTURE.md, Layer 1):
  Stateless — no business logic beyond schema normalisation.
  Publishes to Kafka topic: cortex.raw.jira.events

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

KAFKA_TOPIC = "cortex.raw.jira.events"
SCHEMA_VERSION = "1.0"


def verify_jira_signature(
    payload_bytes: bytes,
    signature_header: str,
    secret: str,
) -> bool:
    """Verify a Jira webhook HMAC-SHA256 signature (X-Hub-Signature header).

    Args:
        payload_bytes: Raw request body bytes.
        signature_header: Value of the X-Hub-Signature header (``sha256=...``).
        secret: Configured Jira webhook secret.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)

_HANDLED_EVENTS = frozenset(
    {
        "jira:issue_created",
        "jira:issue_updated",
        "jira:issue_commented",
        "jira:sprint_started",
        "jira:sprint_closed",
    }
)

# Status transitions that carry signal for the extractor
_SIGNAL_TRANSITIONS = frozenset(
    {
        "In Progress",
        "Done",
        "Closed",
        "Resolved",
        "Won't Do",
        "Cancelled",
        "Blocked",
    }
)


# ─────────────────────────────────────────────────────────────────────────────
# Timestamp helpers
# ─────────────────────────────────────────────────────────────────────────────


def _parse_jira_timestamp(ts: str | None) -> datetime:
    """Parse Jira ISO 8601 timestamp (with timezone offset)."""
    if not ts:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now(UTC)


# ─────────────────────────────────────────────────────────────────────────────
# Jira event normalisers
# ─────────────────────────────────────────────────────────────────────────────


def _normalise_issue_created(
    payload: dict[str, Any],
    workspace_id: str,
) -> RawEvent | None:
    """Normalise a jira:issue_created event."""
    issue = payload.get("issue", {})
    fields = issue.get("fields", {})

    summary = fields.get("summary", "")
    description = fields.get("description") or ""
    if isinstance(description, dict):
        description = _extract_adf_text(description)

    content = f"New Jira issue: {summary}"
    if description:
        content += f"\n\n{description[:500]}"

    reporter = _get_account_name(fields.get("reporter"))
    issue_key = issue.get("key", "")
    project_key = (fields.get("project") or {}).get("key", "unknown")
    issue_type = (fields.get("issuetype") or {}).get("name", "Issue")
    priority = (fields.get("priority") or {}).get("name", "Medium")

    return RawEvent(
        source="jira",
        source_id=issue_key,
        workspace_id=workspace_id,
        event_type="jira:issue_created",
        content=content,
        author=reporter,
        channel=project_key,
        timestamp=_parse_jira_timestamp(fields.get("created")),
        metadata={
            "issue_key": issue_key,
            "issue_type": issue_type,
            "priority": priority,
            "project_key": project_key,
            "labels": fields.get("labels", []),
            "components": [
                c.get("name") for c in fields.get("components", [])
            ],
            "fix_versions": [
                v.get("name") for v in fields.get("fixVersions", [])
            ],
        },
        schema_version=SCHEMA_VERSION,
    )


def _normalise_issue_updated(
    payload: dict[str, Any],
    workspace_id: str,
) -> RawEvent | None:
    """Normalise a jira:issue_updated event — only signal-carrying changes."""
    issue = payload.get("issue", {})
    fields = issue.get("fields", {})
    changelog = payload.get("changelog", {})
    items: list[dict] = changelog.get("items", [])

    # Filter to signal-carrying field changes
    signal_changes: list[str] = []
    for item in items:
        field = item.get("field", "")
        from_str = item.get("fromString") or ""
        to_str = item.get("toString") or ""

        if field == "status" and to_str in _SIGNAL_TRANSITIONS:
            signal_changes.append(f"Status changed: {from_str} → {to_str}")
        elif field == "priority":
            signal_changes.append(f"Priority changed: {from_str} → {to_str}")
        elif field == "assignee":
            signal_changes.append(f"Assigned to: {to_str}")
        elif field == "resolution" and to_str:
            signal_changes.append(f"Resolved as: {to_str}")

    if not signal_changes:
        log.debug("jira.issue_updated.skipped", reason="no_signal_changes")
        return None

    issue_key = issue.get("key", "")
    summary = fields.get("summary", "")
    project_key = (fields.get("project") or {}).get("key", "unknown")
    user = _get_account_name(payload.get("user"))

    content = f"Jira issue updated: {issue_key} {summary}\n" + "\n".join(
        f"- {c}" for c in signal_changes
    )

    return RawEvent(
        source="jira",
        source_id=f"{issue_key}:update:{changelog.get('id', '')}",
        workspace_id=workspace_id,
        event_type="jira:issue_updated",
        content=content,
        author=user,
        channel=project_key,
        timestamp=_parse_jira_timestamp(fields.get("updated")),
        metadata={
            "issue_key": issue_key,
            "changes": signal_changes,
            "project_key": project_key,
            "changelog_id": changelog.get("id", ""),
        },
        schema_version=SCHEMA_VERSION,
    )


def _normalise_issue_commented(
    payload: dict[str, Any],
    workspace_id: str,
) -> RawEvent | None:
    """Normalise a jira:issue_commented event."""
    issue = payload.get("issue", {})
    fields = issue.get("fields", {})
    comment = payload.get("comment", {})

    body = comment.get("body") or ""
    if isinstance(body, dict):
        body = _extract_adf_text(body)
    body = body.strip()

    if not body:
        return None

    issue_key = issue.get("key", "")
    summary = fields.get("summary", "")
    project_key = (fields.get("project") or {}).get("key", "unknown")
    author = _get_account_name(comment.get("author"))

    content = f"Comment on {issue_key} ({summary}):\n{body[:500]}"

    return RawEvent(
        source="jira",
        source_id=f"{issue_key}:comment:{comment.get('id', '')}",
        workspace_id=workspace_id,
        event_type="jira:issue_commented",
        content=content,
        author=author,
        channel=project_key,
        timestamp=_parse_jira_timestamp(comment.get("created")),
        metadata={
            "issue_key": issue_key,
            "comment_id": comment.get("id", ""),
            "project_key": project_key,
        },
        schema_version=SCHEMA_VERSION,
    )


def _normalise_sprint(
    payload: dict[str, Any],
    workspace_id: str,
    event_name: str,
) -> RawEvent | None:
    """Normalise sprint_started / sprint_closed events."""
    sprint = payload.get("sprint", {})
    sprint_name = sprint.get("name", "Unknown Sprint")
    sprint_id = str(sprint.get("id", ""))
    board_id = str(sprint.get("originBoardId", ""))
    goal = sprint.get("goal") or ""

    action = "started" if event_name == "jira:sprint_started" else "closed"
    content = f"Sprint {action}: {sprint_name}"
    if goal:
        content += f"\nGoal: {goal}"

    ts_field = "startDate" if action == "started" else "endDate"
    timestamp = _parse_jira_timestamp(sprint.get(ts_field))

    return RawEvent(
        source="jira",
        source_id=f"sprint:{sprint_id}:{action}",
        workspace_id=workspace_id,
        event_type=event_name,
        content=content,
        author="jira-system",
        channel=f"board:{board_id}",
        timestamp=timestamp,
        metadata={
            "sprint_id": sprint_id,
            "sprint_name": sprint_name,
            "board_id": board_id,
            "goal": goal,
            "state": sprint.get("state", ""),
        },
        schema_version=SCHEMA_VERSION,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────


def _get_account_name(user: dict | None) -> str:
    """Extract canonical user identifier from Jira user object."""
    if not user:
        return "unknown"
    return (
        user.get("emailAddress")
        or user.get("displayName")
        or user.get("accountId", "unknown")
    )


def _extract_adf_text(adf: dict) -> str:
    """Recursively extract plain text from Atlassian Document Format (ADF).

    ADF is the rich-text format Jira uses for descriptions and comments.
    We flatten it to plain text for the extractor.
    """
    texts: list[str] = []
    for node in adf.get("content", []):
        if node.get("type") == "text":
            texts.append(node.get("text", ""))
        elif "content" in node:
            texts.append(_extract_adf_text(node))
    return " ".join(t for t in texts if t)


# ─────────────────────────────────────────────────────────────────────────────
# Public normaliser entry point
# ─────────────────────────────────────────────────────────────────────────────


def normalise_jira_event(
    payload: dict[str, Any],
    event_name: str,
    workspace_id: str,
) -> RawEvent | None:
    """Route a Jira webhook to the correct normaliser.

    Args:
        payload: Parsed Jira webhook JSON body.
        event_name: Jira webhookEvent field value.
        workspace_id: Cortex workspace identifier.

    Returns:
        RawEvent if processable, None otherwise.
    """
    if event_name not in _HANDLED_EVENTS:
        log.debug("jira.event.skipped", event_name=event_name, reason="not_handled")
        return None

    try:
        if event_name == "jira:issue_created":
            return _normalise_issue_created(payload, workspace_id)
        if event_name == "jira:issue_updated":
            return _normalise_issue_updated(payload, workspace_id)
        if event_name == "jira:issue_commented":
            return _normalise_issue_commented(payload, workspace_id)
        if event_name in {"jira:sprint_started", "jira:sprint_closed"}:
            return _normalise_sprint(payload, workspace_id, event_name)
    except (KeyError, ValidationError) as exc:
        log.error(
            "jira.event.normalisation_failed",
            event_name=event_name,
            error=str(exc),
        )

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Kafka producer
# ─────────────────────────────────────────────────────────────────────────────


def _delivery_callback(err: Any, msg: Any) -> None:
    if err:
        log.error("kafka.delivery.failed", topic=msg.topic(), error=str(err))
    else:
        log.info(
            "kafka.delivery.success",
            topic=msg.topic(),
            partition=msg.partition(),
            offset=msg.offset(),
        )


class JiraKafkaProducer:
    """Publishes normalised Jira RawEvents to Kafka."""

    def __init__(self, bootstrap_servers: str | None = None) -> None:
        servers = bootstrap_servers or os.environ.get(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self._producer = Producer(
            {
                "bootstrap.servers": servers,
                "acks": "all",
                "retries": 5,
                "retry.backoff.ms": 300,
                "delivery.timeout.ms": 30000,
                "enable.idempotence": True,
                "compression.type": "snappy",
                "batch.size": 16384,
                "linger.ms": 100,
            }
        )
        log.info("jira.producer.initialized", bootstrap_servers=servers)

    def publish(self, raw_event: RawEvent) -> None:
        key = f"{raw_event.workspace_id}:{raw_event.source_id}".encode()
        payload = raw_event.model_dump_json().encode("utf-8")
        try:
            self._producer.produce(
                topic=KAFKA_TOPIC,
                key=key,
                value=payload,
                callback=_delivery_callback,
            )
            self._producer.poll(0)
        except KafkaException as exc:
            log.error(
                "kafka.produce.failed",
                topic=KAFKA_TOPIC,
                event_id=raw_event.event_id,
                error=str(exc),
            )
            raise

        log.info(
            "jira.event.published",
            event_id=raw_event.event_id,
            source_id=raw_event.source_id,
            event_type=raw_event.event_type,
        )

    def flush(self, timeout: float = 10.0) -> None:
        remaining = self._producer.flush(timeout)
        if remaining > 0:
            log.warning("kafka.flush.incomplete", remaining_messages=remaining)

    def close(self) -> None:
        self.flush()
        log.info("jira.producer.closed")


# ─────────────────────────────────────────────────────────────────────────────
# Jira connector
# ─────────────────────────────────────────────────────────────────────────────


class JiraConnector:
    """Entry point for the Jira connector.

    Instantiate once per process. Call handle_event() for every incoming
    Jira webhook payload.
    """

    def __init__(
        self,
        workspace_id: str | None = None,
        bootstrap_servers: str | None = None,
        webhook_secret: str | None = None,
    ) -> None:
        self.workspace_id = workspace_id or os.environ.get(
            "CORTEX_WORKSPACE_ID", "local-dev"
        )
        self._webhook_secret = webhook_secret or os.environ.get(
            "JIRA_WEBHOOK_SECRET",
            "",
        )
        self._producer = JiraKafkaProducer(bootstrap_servers=bootstrap_servers)
        log.info("jira.connector.initialized", workspace_id=self.workspace_id)

    def handle_event(
        self,
        payload: dict[str, Any],
        signature: str | None = None,
        raw_body: bytes | None = None,
    ) -> dict[str, str]:
        """Process an incoming Jira webhook payload.

        Args:
            payload: Parsed Jira webhook JSON body.
            signature: X-Hub-Signature header value (optional, for verification).
            raw_body: Raw request body bytes for signature verification.

        Returns:
            {"status": "ok", "event_id": ...} | {"status": "skipped", ...}
        """
        # When a secret is configured, verification is mandatory.
        if self._webhook_secret and not (
            signature
            and raw_body
            and verify_jira_signature(raw_body, signature, self._webhook_secret)
        ):
            log.warning("jira.webhook.signature_invalid")
            return {"status": "error", "reason": "invalid_signature"}

        event_name = payload.get("webhookEvent", "")

        raw_event = normalise_jira_event(payload, event_name, self.workspace_id)
        if raw_event is None:
            return {"status": "skipped", "reason": "not_processable"}

        self._producer.publish(raw_event)
        return {"status": "ok", "event_id": raw_event.event_id}

    def close(self) -> None:
        self._producer.close()
