"""Tests for pipeline/extraction_worker.py."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from pipeline.extraction_worker import ExtractionWorker, _BoundedSeenCache
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
@patch("pipeline.extraction_worker.DecisionScoringPipeline")
@patch("pipeline.extraction_worker.DecisionExtractor")
@patch("pipeline.extraction_worker.Producer")
@patch("pipeline.extraction_worker.Consumer")
def test_process_raw_event_writes_and_publishes(
    consumer_cls: MagicMock,
    producer_cls: MagicMock,
    extractor_cls: MagicMock,
    scoring_cls: MagicMock,
    writer_cls: MagicMock,
) -> None:
    extractor = extractor_cls.return_value
    extractor.extract.return_value = _decision()
    scoring = scoring_cls.return_value
    scoring.score.side_effect = lambda decision: decision
    writer = writer_cls.return_value
    writer.write.return_value = "decision-1"

    worker = ExtractionWorker(bootstrap_servers="localhost:9092")
    event_id = worker.process_raw_event(_raw_event())

    assert event_id == "decision-1"
    scoring.score.assert_called_once()
    writer.write.assert_called_once()
    producer_cls.return_value.produce.assert_called_once()


@patch("pipeline.extraction_worker.persist_quarantine")
@patch("pipeline.extraction_worker.GraphWriter")
@patch("pipeline.extraction_worker.DecisionScoringPipeline")
@patch("pipeline.extraction_worker.DecisionExtractor")
@patch("pipeline.extraction_worker.Producer")
@patch("pipeline.extraction_worker.Consumer")
def test_process_raw_event_quarantines_low_trust(
    consumer_cls: MagicMock,
    producer_cls: MagicMock,
    extractor_cls: MagicMock,
    scoring_cls: MagicMock,
    writer_cls: MagicMock,
    quarantine_mock: MagicMock,
) -> None:
    decision = _decision()
    decision.trust_score = 0.1
    decision.importance_score = 0.75
    extractor_cls.return_value.extract.return_value = decision
    scoring_cls.return_value.score.side_effect = lambda d: d

    worker = ExtractionWorker(bootstrap_servers="localhost:9092")
    assert worker.process_raw_event(_raw_event()) is None
    writer_cls.return_value.write.assert_not_called()
    producer_cls.return_value.produce.assert_not_called()
    quarantine_mock.assert_called_once()


@patch("pipeline.extraction_worker.GraphWriter")
@patch("pipeline.extraction_worker.DecisionScoringPipeline")
@patch("pipeline.extraction_worker.DecisionExtractor")
@patch("pipeline.extraction_worker.Producer")
@patch("pipeline.extraction_worker.Consumer")
def test_process_raw_event_discards_low_importance(
    consumer_cls: MagicMock,
    producer_cls: MagicMock,
    extractor_cls: MagicMock,
    scoring_cls: MagicMock,
    writer_cls: MagicMock,
) -> None:
    decision = _decision()
    decision.importance_score = 0.1
    decision.trust_score = 0.8
    extractor_cls.return_value.extract.return_value = decision
    scoring_cls.return_value.score.side_effect = lambda d: d

    worker = ExtractionWorker(bootstrap_servers="localhost:9092")
    assert worker.process_raw_event(_raw_event()) is None
    writer_cls.return_value.write.assert_not_called()


def test_bounded_seen_cache_evicts_lru() -> None:
    """The dedup cache must drop the oldest entry once capacity is reached."""
    cache = _BoundedSeenCache(capacity=3)
    cache.add("a")
    cache.add("b")
    cache.add("c")
    cache.add("d")
    assert "a" not in cache
    assert "b" in cache
    assert "c" in cache
    assert "d" in cache
    assert len(cache) == 3


def test_bounded_seen_cache_promotes_on_hit() -> None:
    """``__contains__`` should mark the key as most-recently-used."""
    cache = _BoundedSeenCache(capacity=2)
    cache.add("a")
    cache.add("b")
    assert "a" in cache  # promotes "a" — "b" is now the LRU
    cache.add("c")
    assert "a" in cache
    assert "b" not in cache
    assert "c" in cache
