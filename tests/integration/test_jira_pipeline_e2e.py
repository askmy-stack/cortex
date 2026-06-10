"""Jira-specific pipeline integration test — extract → score → graph write."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from pipeline.extraction_worker import ExtractionWorker
from shared.models import DecisionEvent, Provenance, RawEvent

NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _jira_raw() -> RawEvent:
    return RawEvent(
        source="jira",
        source_id="ENG-123:comment:10001",
        workspace_id="local-dev",
        event_type="jira:issue_commented",
        content="Comment on ENG-123 (Billing architecture decision):\nWe decided to adopt event sourcing.",
        author="Alex Chen",
        channel="ENG",
        timestamp=NOW,
    )


def _jira_decision(raw: RawEvent) -> DecisionEvent:
    return DecisionEvent(
        source_raw_event_id=raw.event_id,
        workspace_id=raw.workspace_id,
        event_type="decision",
        content="Adopt event sourcing for billing.",
        made_by=["Alex Chen"],
        affects=["billing"],
        rationale=["Audit requirements blocked monolith release."],
        extraction_confidence=0.87,
        importance_score=0.0,
        trust_score=0.0,
        provenance=Provenance(
            source="jira",
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
def test_jira_comment_through_worker_scores_before_write(
    consumer_cls: MagicMock,
    producer_cls: MagicMock,
    extractor_cls: MagicMock,
    importance_cls: MagicMock,
    trust_cls: MagicMock,
    writer_cls: MagicMock,
) -> None:
    """Jira RawEvent runs extract → importance → trust → Neo4j write in order."""
    raw_event = _jira_raw()
    decision = _jira_decision(raw_event)

    def _apply_importance(d: DecisionEvent) -> DecisionEvent:
        d.importance_score = 0.8
        return d

    def _apply_trust(d: DecisionEvent) -> DecisionEvent:
        d.trust_score = 0.74
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
