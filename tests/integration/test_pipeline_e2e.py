"""End-to-end pipeline test with mocked Kafka and graph dependencies."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from pipeline.extraction_worker import ExtractionWorker
from shared.models import DecisionEvent, Provenance, RawEvent

NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


@patch("pipeline.extraction_worker.GraphWriter")
@patch("pipeline.extraction_worker.TrustScorer")
@patch("pipeline.extraction_worker.ImportanceScorer")
@patch("pipeline.extraction_worker.DecisionExtractor")
@patch("pipeline.extraction_worker.Producer")
@patch("pipeline.extraction_worker.Consumer")
def test_webhook_to_graph_pipeline(
    consumer_cls: MagicMock,
    producer_cls: MagicMock,
    extractor_cls: MagicMock,
    importance_cls: MagicMock,
    trust_cls: MagicMock,
    writer_cls: MagicMock,
) -> None:
    raw_event = RawEvent(
        source="github",
        source_id="org/repo:pr:42",
        workspace_id="ws-1",
        event_type="github:pull_request:merged",
        content="PR merged: migrate payments to CockroachDB",
        author="alice",
        channel="org/repo",
        timestamp=NOW,
    )
    decision = DecisionEvent(
        source_raw_event_id=raw_event.event_id,
        workspace_id="ws-1",
        event_type="decision",
        content="Migrate payments to CockroachDB.",
        made_by=["alice"],
        affects=["payments-service"],
        rationale=["Scale"],
        extraction_confidence=0.92,
        importance_score=0.85,
        trust_score=0.82,
        provenance=Provenance(
            source="github",
            channel="org/repo",
            original_timestamp=NOW,
            extractor_version="0.1.0",
            extractor_model="gpt-4o",
            verified_by=[],
            raw_event_id=raw_event.event_id,
        ),
        extracted_at=NOW,
    )

    extractor_cls.return_value.extract.return_value = decision
    importance_cls.return_value.score.side_effect = lambda item: item
    trust_cls.return_value.score.side_effect = lambda item: item
    writer_cls.return_value.write.return_value = decision.event_id

    worker = ExtractionWorker(bootstrap_servers="localhost:9092")
    assert worker.process_raw_event(raw_event) == decision.event_id
