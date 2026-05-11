"""Tests for pipeline/extraction_worker.py."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from pipeline.extraction_worker import ExtractionWorker
from shared.models import DecisionEvent, Provenance, RawEvent

NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _raw_event() -> RawEvent:
    return RawEvent(
        source="slack",
        source_id="msg-1",
        workspace_id="ws-1",
        event_type="slack:message",
        content="We decided to migrate payments to CockroachDB.",
        author="alice@company.com",
        channel="C-engineering",
        timestamp=NOW,
    )


def _decision() -> DecisionEvent:
    return DecisionEvent(
        source_raw_event_id="raw-1",
        workspace_id="ws-1",
        event_type="decision",
        content="We decided to migrate payments to CockroachDB.",
        made_by=["alice@company.com"],
        affects=["payments-service"],
        rationale=["Scale ceiling"],
        extraction_confidence=0.95,
        importance_score=0.8,
        trust_score=0.8,
        provenance=Provenance(
            source="slack",
            channel="C-engineering",
            original_timestamp=NOW,
            extractor_version="0.1.0",
            extractor_model="gpt-4o",
            verified_by=[],
            raw_event_id="raw-1",
        ),
        extracted_at=NOW,
    )


@patch("pipeline.extraction_worker.GraphWriter")
@patch("pipeline.extraction_worker.TrustScorer")
@patch("pipeline.extraction_worker.ImportanceScorer")
@patch("pipeline.extraction_worker.DecisionExtractor")
@patch("pipeline.extraction_worker.Producer")
@patch("pipeline.extraction_worker.Consumer")
def test_process_raw_event_writes_and_publishes(
    consumer_cls: MagicMock,
    producer_cls: MagicMock,
    extractor_cls: MagicMock,
    importance_cls: MagicMock,
    trust_cls: MagicMock,
    writer_cls: MagicMock,
) -> None:
    extractor = extractor_cls.return_value
    extractor.extract.return_value = _decision()
    importance = importance_cls.return_value
    importance.score.side_effect = lambda decision: decision
    trust = trust_cls.return_value
    trust.score.side_effect = lambda decision: decision
    writer = writer_cls.return_value
    writer.write.return_value = "decision-1"

    worker = ExtractionWorker(bootstrap_servers="localhost:9092")
    event_id = worker.process_raw_event(_raw_event())

    assert event_id == "decision-1"
    writer.write.assert_called_once()
    producer_cls.return_value.produce.assert_called_once()
