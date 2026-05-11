"""Tests for connectors/slack/producer.py.

Tests cover:
- RawEvent schema validation from Slack payloads
- URL verification challenge handling
- Skipping bot messages and unsupported event types
- Kafka publish (mocked)
- Edge cases: empty text, missing fields, invalid timestamps
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from connectors.slack.producer import (
    SlackConnector,
    SlackKafkaProducer,
    normalise_slack_event,
)
from shared.models import RawEvent


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

WORKSPACE_ID = "test-workspace"


def _message_payload(
    text: str = "We decided to migrate payments to CockroachDB.",
    user: str = "U12345",
    channel: str = "C-engineering",
    ts: str = "1715000000.000000",
    subtype: str | None = None,
    event_type: str = "message",
) -> dict:
    event: dict = {
        "type": event_type,
        "user": user,
        "text": text,
        "channel": channel,
        "ts": ts,
    }
    if subtype:
        event["subtype"] = subtype
    return {
        "type": "event_callback",
        "team_id": "T99999",
        "event": event,
    }


# ─────────────────────────────────────────────────────────────────────────────
# normalise_slack_event
# ─────────────────────────────────────────────────────────────────────────────


class TestNormaliseSlackEvent:
    def test_valid_message_returns_raw_event(self) -> None:
        payload = _message_payload()
        result = normalise_slack_event(payload, WORKSPACE_ID)

        assert result is not None
        assert isinstance(result, RawEvent)
        assert result.source == "slack"
        assert result.workspace_id == WORKSPACE_ID
        assert result.content == "We decided to migrate payments to CockroachDB."
        assert result.author == "U12345"
        assert result.channel == "C-engineering"
        assert result.event_type == "slack:message"
        assert result.schema_version == "1.0"

    def test_bot_message_returns_none(self) -> None:
        payload = _message_payload(subtype="bot_message")
        assert normalise_slack_event(payload, WORKSPACE_ID) is None

    def test_message_changed_returns_none(self) -> None:
        payload = _message_payload(subtype="message_changed")
        assert normalise_slack_event(payload, WORKSPACE_ID) is None

    def test_message_deleted_returns_none(self) -> None:
        payload = _message_payload(subtype="message_deleted")
        assert normalise_slack_event(payload, WORKSPACE_ID) is None

    def test_empty_text_returns_none(self) -> None:
        payload = _message_payload(text="")
        assert normalise_slack_event(payload, WORKSPACE_ID) is None

    def test_whitespace_only_text_returns_none(self) -> None:
        payload = _message_payload(text="   ")
        assert normalise_slack_event(payload, WORKSPACE_ID) is None

    def test_non_message_event_type_returns_none(self) -> None:
        payload = {
            "type": "event_callback",
            "event": {"type": "reaction_added", "reaction": "thumbsup"},
        }
        assert normalise_slack_event(payload, WORKSPACE_ID) is None

    def test_app_mention_processed(self) -> None:
        payload = _message_payload(event_type="app_mention")
        result = normalise_slack_event(payload, WORKSPACE_ID)
        assert result is not None
        assert result.event_type == "slack:app_mention"

    def test_timestamp_parsed_correctly(self) -> None:
        payload = _message_payload(ts="1715000000.000000")
        result = normalise_slack_event(payload, WORKSPACE_ID)
        assert result is not None
        assert isinstance(result.timestamp, datetime)

    def test_invalid_timestamp_falls_back_to_utcnow(self) -> None:
        payload = _message_payload(ts="invalid-ts")
        result = normalise_slack_event(payload, WORKSPACE_ID)
        assert result is not None
        assert isinstance(result.timestamp, datetime)

    def test_metadata_includes_expected_fields(self) -> None:
        payload = _message_payload(ts="1715000000.000000")
        payload["event"]["thread_ts"] = "1715000000.000000"
        payload["event"]["reply_count"] = 3
        result = normalise_slack_event(payload, WORKSPACE_ID)
        assert result is not None
        assert result.metadata["reply_count"] == 3
        assert result.metadata["thread_ts"] == "1715000000.000000"
        assert result.metadata["team"] == "T99999"

    def test_source_id_includes_channel_and_ts(self) -> None:
        payload = _message_payload(channel="C-general", ts="1715000000.123456")
        result = normalise_slack_event(payload, WORKSPACE_ID)
        assert result is not None
        assert result.source_id == "C-general:1715000000.123456"

    def test_event_id_is_unique(self) -> None:
        payload = _message_payload()
        r1 = normalise_slack_event(payload, WORKSPACE_ID)
        r2 = normalise_slack_event(payload, WORKSPACE_ID)
        assert r1 is not None
        assert r2 is not None
        assert r1.event_id != r2.event_id

    @pytest.mark.parametrize(
        "text",
        [
            "We decided to use Kafka as our single event bus.",
            "Architecture decision: move to CockroachDB for payments.",
            "Exception: the auth service fails when JWT expiry < 60s.",
            "Rationale: Redis chosen for sub-50ms cache latency.",
        ],
    )
    def test_various_decision_texts_produce_valid_raw_events(self, text: str) -> None:
        payload = _message_payload(text=text)
        result = normalise_slack_event(payload, WORKSPACE_ID)
        assert result is not None
        assert result.content == text


# ─────────────────────────────────────────────────────────────────────────────
# SlackKafkaProducer (mocked Kafka)
# ─────────────────────────────────────────────────────────────────────────────


class TestSlackKafkaProducer:
    @patch("connectors.slack.producer.Producer")
    def test_publish_calls_produce(self, mock_producer_cls: MagicMock) -> None:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer

        producer = SlackKafkaProducer(bootstrap_servers="localhost:9092")
        payload = _message_payload()
        raw_event = normalise_slack_event(payload, WORKSPACE_ID)
        assert raw_event is not None

        producer.publish(raw_event)

        mock_producer.produce.assert_called_once()
        call_kwargs = mock_producer.produce.call_args[1]
        assert call_kwargs["topic"] == "cortex.raw.slack.messages"

    @patch("connectors.slack.producer.Producer")
    def test_publish_key_includes_workspace_and_source_id(
        self, mock_producer_cls: MagicMock
    ) -> None:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer

        producer = SlackKafkaProducer(bootstrap_servers="localhost:9092")
        payload = _message_payload(channel="C-eng", ts="111.000")
        raw_event = normalise_slack_event(payload, WORKSPACE_ID)
        assert raw_event is not None

        producer.publish(raw_event)

        call_kwargs = mock_producer.produce.call_args[1]
        expected_key = f"{WORKSPACE_ID}:C-eng:111.000".encode()
        assert call_kwargs["key"] == expected_key

    @patch("connectors.slack.producer.Producer")
    def test_flush_called_on_close(self, mock_producer_cls: MagicMock) -> None:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer

        producer = SlackKafkaProducer(bootstrap_servers="localhost:9092")
        mock_producer.flush.return_value = 0
        producer.close()

        mock_producer.flush.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# SlackConnector (end-to-end flow, mocked Kafka)
# ─────────────────────────────────────────────────────────────────────────────


class TestSlackConnector:
    @patch("connectors.slack.producer.Producer")
    def test_url_verification_returns_challenge(
        self, mock_producer_cls: MagicMock
    ) -> None:
        mock_producer_cls.return_value = MagicMock()
        connector = SlackConnector(workspace_id=WORKSPACE_ID)

        result = connector.handle_event(
            {"type": "url_verification", "challenge": "abc123"}
        )
        assert result == {"challenge": "abc123"}

    @patch("connectors.slack.producer.Producer")
    def test_event_callback_publishes_and_returns_ok(
        self, mock_producer_cls: MagicMock
    ) -> None:
        mock_producer = MagicMock()
        mock_producer_cls.return_value = mock_producer

        connector = SlackConnector(workspace_id=WORKSPACE_ID)
        payload = _message_payload()
        result = connector.handle_event(payload)

        assert result["status"] == "ok"
        assert "event_id" in result
        mock_producer.produce.assert_called_once()

    @patch("connectors.slack.producer.Producer")
    def test_bot_message_returns_skipped(
        self, mock_producer_cls: MagicMock
    ) -> None:
        mock_producer_cls.return_value = MagicMock()
        connector = SlackConnector(workspace_id=WORKSPACE_ID)
        payload = _message_payload(subtype="bot_message")
        result = connector.handle_event(payload)
        assert result["status"] == "skipped"

    @patch("connectors.slack.producer.Producer")
    def test_unrecognised_type_returns_skipped(
        self, mock_producer_cls: MagicMock
    ) -> None:
        mock_producer_cls.return_value = MagicMock()
        connector = SlackConnector(workspace_id=WORKSPACE_ID)
        result = connector.handle_event({"type": "unknown_type"})
        assert result["status"] == "skipped"
