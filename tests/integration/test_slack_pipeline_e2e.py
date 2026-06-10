"""Slack-specific pipeline integration test — extract → score → graph write."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from pipeline.extraction_worker import ExtractionWorker
from shared.models import DecisionEvent, Provenance, RawEvent

NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _slack_raw() -> RawEvent:
    return RawEvent(
        source="slack",
        source_id="C-engineering:1715000000.000000",
        workspace_id="local-dev",
        event_type="slack:message",
        content="We decided to migrate payments to CockroachDB for multi-region scale.",
        author="U12345",
        channel="C-engineering",
        timestamp=NOW,
    )


def _slack_decision(raw: RawEvent) -> DecisionEvent:
    return DecisionEvent(
        source_raw_event_id=raw.event_id,
        workspace_id=raw.workspace_id,
        event_type="decision",
        content="Migrate payments to CockroachDB for multi-region scale.",
        made_by=["U12345"],
        affects=["payments-service"],
        rationale=["Postgres failover gaps in eu-west."],
        extraction_confidence=0.88,
        importance_score=0.0,
        trust_score=0.0,
        provenance=Provenance(
            source="slack",
            channel=raw.channel,
            original_timestamp=raw.timestamp,
            extractor_version="0.1.0",
            extractor_model="test",
            verified_by=[],
            raw_event_id=raw.event_id,
        ),
        extracted_at=NOW,
    )


@patch("pipeline.extraction_worker.GraphWriter")
@patch("pipeline.extraction_worker.DecisionScoringPipeline")
@patch("pipeline.extraction_worker.DecisionExtractor")
@patch("pipeline.extraction_worker.Producer")
@patch("pipeline.extraction_worker.Consumer")
def test_slack_message_through_worker_scores_before_write(
    consumer_cls: MagicMock,
    producer_cls: MagicMock,
    extractor_cls: MagicMock,
    scoring_cls: MagicMock,
    writer_cls: MagicMock,
) -> None:
    """Slack RawEvent runs extract → importance → trust → Neo4j write in order."""
    raw_event = _slack_raw()
    decision = _slack_decision(raw_event)

    def _apply_scores(d: DecisionEvent) -> DecisionEvent:
        d.importance_score = 0.85
        d.trust_score = 0.78
        return d

    extractor_cls.return_value.extract.return_value = decision
    scoring_cls.return_value.score.side_effect = _apply_scores
    writer_cls.return_value.write.return_value = decision.event_id

    worker = ExtractionWorker(bootstrap_servers="localhost:9092")
    assert worker.process_raw_event(raw_event) == decision.event_id

    extractor_cls.return_value.extract.assert_called_once_with(raw_event)
    scoring_cls.return_value.score.assert_called_once()
    writer_cls.return_value.write.assert_called_once()

    written = writer_cls.return_value.write.call_args[0][0]
    assert written.importance_score == 0.85
    assert written.trust_score == 0.78
    assert written.provenance.source == "slack"

    out_producer = producer_cls.return_value
    out_producer.produce.assert_called_once()
    assert out_producer.produce.call_args[1]["topic"] == "cortex.extracted.decisions"
