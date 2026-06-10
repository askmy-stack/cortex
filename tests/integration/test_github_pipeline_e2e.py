"""GitHub-specific pipeline integration test — extract → score → graph write."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from pipeline.extraction_worker import ExtractionWorker
from shared.models import DecisionEvent, Provenance, RawEvent

NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _github_raw() -> RawEvent:
    return RawEvent(
        source="github",
        source_id="acme/payments:pr:42",
        workspace_id="local-dev",
        event_type="github:pull_request:merged",
        content="PR merged: Decision: migrate payments to CockroachDB\n\nApproved for EU launch.",
        author="priya",
        channel="acme/payments",
        timestamp=NOW,
    )


def _github_decision(raw: RawEvent) -> DecisionEvent:
    return DecisionEvent(
        source_raw_event_id=raw.event_id,
        workspace_id=raw.workspace_id,
        event_type="decision",
        content="Migrate payments to CockroachDB for multi-region scale.",
        made_by=["priya"],
        affects=["payments-service"],
        rationale=["EU launch blocked by Postgres failover gaps."],
        extraction_confidence=0.9,
        importance_score=0.0,
        trust_score=0.0,
        provenance=Provenance(
            source="github",
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
@patch("pipeline.extraction_worker.TrustScorer")
@patch("pipeline.extraction_worker.ImportanceScorer")
@patch("pipeline.extraction_worker.DecisionExtractor")
@patch("pipeline.extraction_worker.Producer")
@patch("pipeline.extraction_worker.Consumer")
def test_github_pr_through_worker_scores_before_write(
    consumer_cls: MagicMock,
    producer_cls: MagicMock,
    extractor_cls: MagicMock,
    importance_cls: MagicMock,
    trust_cls: MagicMock,
    writer_cls: MagicMock,
) -> None:
    """GitHub RawEvent runs extract → importance → trust → Neo4j write in order."""
    raw_event = _github_raw()
    decision = _github_decision(raw_event)

    def _apply_importance(d: DecisionEvent) -> DecisionEvent:
        d.importance_score = 0.82
        return d

    def _apply_trust(d: DecisionEvent) -> DecisionEvent:
        d.trust_score = 0.76
        return d

    extractor_cls.return_value.extract.return_value = decision
    importance_cls.return_value.score.side_effect = _apply_importance
    trust_cls.return_value.score.side_effect = _apply_trust
    writer_cls.return_value.write.return_value = decision.event_id

    worker = ExtractionWorker(bootstrap_servers="localhost:9092")
    event_id = worker.process_raw_event(raw_event)

    assert event_id == decision.event_id
    extractor_cls.return_value.extract.assert_called_once_with(raw_event)
    importance_cls.return_value.score.assert_called_once()
    trust_cls.return_value.score.assert_called_once()
    writer_cls.return_value.write.assert_called_once_with(decision)
