"""Slack connector — transforms Slack events into RawEvent and publishes to Kafka.

Connector design principle (ARCHITECTURE.md, Layer 1):
  - Stateless plugin — no business logic beyond schema normalisation
  - Every event published to: cortex.raw.slack.messages
  - Structured JSON logging via structlog — never print()

Decision: D-001 — Kafka as single event bus.
Topic: cortex.raw.slack.messages
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import structlog
from confluent_kafka import KafkaException, Producer
from pydantic import ValidationError

from shared.models import RawEvent

log = structlog.get_logger(__name__)

KAFKA_TOPIC = "cortex.raw.slack.messages"
SCHEMA_VERSION = "1.0"


# ─────────────────────────────────────────────────────────────────────────────
# Kafka delivery callback
# ─────────────────────────────────────────────────────────────────────────────


def _delivery_callback(err: Any, msg: Any) -> None:
    """Log Kafka delivery result for every published message."""
    if err:
        log.error(
            "kafka.delivery.failed",
            topic=msg.topic(),
            partition=msg.partition(),
            error=str(err),
        )
    else:
        log.info(
            "kafka.delivery.success",
            topic=msg.topic(),
            partition=msg.partition(),
            offset=msg.offset(),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Slack event normaliser
# ─────────────────────────────────────────────────────────────────────────────


def normalise_slack_event(
    payload: dict[str, Any],
    workspace_id: str,
) -> RawEvent | None:
    """Transform a raw Slack Events API payload into a RawEvent.

    Handles:
      - message events (message.channels, message.groups)
      - app_mention events
      - Skips bot messages, retries, and empty content

    Args:
        payload: The raw Slack event payload from the Events API webhook.
        workspace_id: The Cortex workspace identifier for this Slack org.

    Returns:
        RawEvent if the payload is a processable message, None otherwise.
    """
    event = payload.get("event", {})
    event_type = event.get("type", "")

    # Skip non-message events
    if event_type not in {"message", "app_mention"}:
        log.debug("slack.event.skipped", event_type=event_type, reason="not_message")
        return None

    # Skip bot messages (subtype: bot_message) and message edits/deletes
    subtype = event.get("subtype")
    if subtype in {"bot_message", "message_changed", "message_deleted"}:
        log.debug("slack.event.skipped", subtype=subtype, reason="bot_or_edit")
        return None

    text = (event.get("text") or "").strip()
    if not text:
        log.debug("slack.event.skipped", reason="empty_content")
        return None

    # Extract thread context — include parent message ts for threading
    thread_ts = event.get("thread_ts")
    ts = event.get("ts", "")

    # Parse Slack's UNIX timestamp string
    try:
        timestamp = datetime.fromtimestamp(float(ts), tz=UTC) if ts else datetime.now(UTC)
    except (ValueError, TypeError):
        timestamp = datetime.now(UTC)

    author = event.get("user") or event.get("username") or "unknown"
    channel = event.get("channel", "unknown")

    metadata: dict[str, Any] = {
        "ts": ts,
        "thread_ts": thread_ts,
        "reaction_count": len(event.get("reactions", [])),
        "reply_count": event.get("reply_count", 0),
        "channel_type": event.get("channel_type", "unknown"),
        "blocks": event.get("blocks", []),
        "team": payload.get("team_id"),
    }

    try:
        raw_event = RawEvent(
            source="slack",
            source_id=f"{channel}:{ts}",
            workspace_id=workspace_id,
            event_type=f"slack:{event_type}",
            content=text,
            author=author,
            channel=channel,
            timestamp=timestamp,
            metadata=metadata,
            schema_version=SCHEMA_VERSION,
        )
    except ValidationError as exc:
        log.error(
            "slack.event.validation_failed",
            errors=exc.errors(),
            payload_keys=list(payload.keys()),
        )
        return None

    return raw_event


# ─────────────────────────────────────────────────────────────────────────────
# Kafka producer
# ─────────────────────────────────────────────────────────────────────────────


class SlackKafkaProducer:
    """Publishes normalised Slack RawEvents to Kafka.

    Thread-safe. One instance per connector process.
    """

    def __init__(self, bootstrap_servers: str | None = None) -> None:
        """Initialise the Kafka producer.

        Args:
            bootstrap_servers: Kafka broker addresses. Defaults to KAFKA_BOOTSTRAP_SERVERS env var.
        """
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
        log.info("slack.producer.initialized", bootstrap_servers=servers)

    def publish(self, raw_event: RawEvent) -> None:
        """Publish a RawEvent to the Slack Kafka topic.

        Args:
            raw_event: The normalised event to publish.

        Raises:
            KafkaException: If the message cannot be enqueued.
        """
        payload = raw_event.model_dump_json().encode("utf-8")
        key = f"{raw_event.workspace_id}:{raw_event.source_id}".encode()

        try:
            self._producer.produce(
                topic=KAFKA_TOPIC,
                key=key,
                value=payload,
                callback=_delivery_callback,
            )
            self._producer.poll(0)  # Trigger delivery callbacks without blocking
        except KafkaException as exc:
            log.error(
                "kafka.produce.failed",
                topic=KAFKA_TOPIC,
                event_id=raw_event.event_id,
                error=str(exc),
            )
            raise

        log.info(
            "slack.event.published",
            event_id=raw_event.event_id,
            source_id=raw_event.source_id,
            workspace_id=raw_event.workspace_id,
            author=raw_event.author,
            channel=raw_event.channel,
            content_length=len(raw_event.content),
        )

    def flush(self, timeout: float = 10.0) -> None:
        """Flush all pending messages to Kafka.

        Args:
            timeout: Maximum seconds to wait for delivery.
        """
        remaining = self._producer.flush(timeout)
        if remaining > 0:
            log.warning("kafka.flush.incomplete", remaining_messages=remaining)

    def close(self) -> None:
        """Flush and close the producer."""
        self.flush()
        log.info("slack.producer.closed")


# ─────────────────────────────────────────────────────────────────────────────
# Slack Events API webhook handler
# ─────────────────────────────────────────────────────────────────────────────


class SlackConnector:
    """Entry point for the Slack connector.

    Instantiate once per process. Call handle_event() for every incoming
    Slack Events API payload received by the FastAPI webhook endpoint.
    """

    def __init__(
        self,
        workspace_id: str | None = None,
        bootstrap_servers: str | None = None,
    ) -> None:
        """Initialise the Slack connector.

        Args:
            workspace_id: Cortex workspace ID. Defaults to CORTEX_WORKSPACE_ID env var.
            bootstrap_servers: Kafka brokers. Defaults to KAFKA_BOOTSTRAP_SERVERS env var.
        """
        self.workspace_id = workspace_id or os.environ.get(
            "CORTEX_WORKSPACE_ID", "local-dev"
        )
        self._producer = SlackKafkaProducer(bootstrap_servers=bootstrap_servers)
        log.info(
            "slack.connector.initialized",
            workspace_id=self.workspace_id,
        )

    def handle_event(
        self,
        payload: dict[str, Any],
        *,
        slack_retry_num: int | None = None,
    ) -> dict[str, str]:
        """Process an incoming Slack Events API payload.

        Normalises the payload into a RawEvent and publishes to Kafka.

        Args:
            payload: Raw Slack webhook payload (already JSON-parsed).
            slack_retry_num: Value of Slack ``X-Slack-Retry-Num`` header, if present.
                Retries are skipped — the first delivery is processed once.

        Returns:
            {"status": "ok"} on success, {"status": "skipped", "reason": ...} if not applicable.
        """
        # Slack URL verification challenge
        if payload.get("type") == "url_verification":
            challenge = payload.get("challenge", "")
            log.info("slack.url_verification", challenge=challenge[:8])
            return {"challenge": challenge}

        if slack_retry_num is not None and slack_retry_num > 0:
            log.info(
                "slack.event.skipped",
                reason="slack_retry",
                retry_num=slack_retry_num,
            )
            return {"status": "skipped", "reason": "slack_retry"}

        if payload.get("type") == "event_callback":
            raw_event = normalise_slack_event(payload, self.workspace_id)
            if raw_event is None:
                return {"status": "skipped", "reason": "not_processable"}

            self._producer.publish(raw_event)
            self._producer.flush(timeout=5.0)
            return {"status": "ok", "event_id": raw_event.event_id}

        log.debug("slack.payload.unrecognised", payload_type=payload.get("type"))
        return {"status": "skipped", "reason": "unrecognised_type"}

    def close(self) -> None:
        """Flush and close the Kafka producer."""
        self._producer.close()
