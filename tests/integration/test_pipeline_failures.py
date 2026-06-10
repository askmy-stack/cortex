"""Pipeline failure paths — discard, quarantine, extractor miss."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from pipeline.extraction_worker import ExtractionWorker
from shared.models import IMPORTANCE_DISCARD, DecisionEvent, Provenance, RawEvent

NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _raw() -> RawEvent:
    return RawEvent(
        source="slack",
        source_id="C1:123",
        workspace_id="ws-1",
        event_type="slack:message",
        content="lunch at noon?",
        author="bob",
        channel="C-random",
        timestamp=NOW,
    )


@patch("pipeline.extraction_worker.GraphWriter")
@patch("pipeline.extraction_worker.TrustScorer")
@patch("pipeline.extraction_worker.ImportanceScorer")
@patch("pipeline.extraction_worker.DecisionExtractor")
@patch("pipeline.extraction_worker.Producer")
@patch("pipeline.extraction_worker.Consumer")
def test_extractor_returns_none_skips_write(
    consumer_cls: MagicMock,
    producer_cls: MagicMock,
    extractor_cls: MagicMock,
    importance_cls: MagicMock,
    trust_cls: MagicMock,
    writer_cls: MagicMock,
) -> None:
    extractor_cls.return_value.extract.return_value = None
    worker = ExtractionWorker(bootstrap_servers="localhost:9092")
    assert worker.process_raw_event(_raw()) is None
    writer_cls.return_value.write.assert_not_called()


@patch("pipeline.extraction_worker.GraphWriter")
@patch("pipeline.extraction_worker.TrustScorer")
@patch("pipeline.extraction_worker.ImportanceScorer")
@patch("pipeline.extraction_worker.DecisionExtractor")
@patch("pipeline.extraction_worker.Producer")
@patch("pipeline.extraction_worker.Consumer")
def test_low_importance_discarded_before_write(
    consumer_cls: MagicMock,
    producer_cls: MagicMock,
    extractor_cls: MagicMock,
    importance_cls: MagicMock,
    trust_cls: MagicMock,
    writer_cls: MagicMock,
) -> None:
    raw = _raw()
    decision = DecisionEvent(
        source_raw_event_id=raw.event_id,
        workspace_id="ws-1",
        event_type="decision",
        content="noise",
        made_by=["bob"],
        affects=[],
        rationale=[],
        extraction_confidence=0.5,
        importance_score=IMPORTANCE_DISCARD - 0.01,
        trust_score=0.9,
        provenance=Provenance(
            source="slack",
            channel="C-random",
            original_timestamp=NOW,
            extractor_version="0.1.0",
            extractor_model="gpt-4o",
            raw_event_id=raw.event_id,
        ),
        extracted_at=NOW,
    )
    extractor_cls.return_value.extract.return_value = decision
    importance_cls.return_value.score.side_effect = lambda item: item
    trust_cls.return_value.score.side_effect = lambda item: item
    writer_cls.return_value.write.side_effect = ValueError("below discard threshold")

    worker = ExtractionWorker(bootstrap_servers="localhost:9092")
    assert worker.process_raw_event(raw) is None
    writer_cls.return_value.write.assert_called_once()


@patch("pipeline.extraction_worker.GraphWriter")
@patch("pipeline.extraction_worker.TrustScorer")
@patch("pipeline.extraction_worker.ImportanceScorer")
@patch("pipeline.extraction_worker.DecisionExtractor")
@patch("pipeline.extraction_worker.Producer")
@patch("pipeline.extraction_worker.Consumer")
def test_invalid_message_routed_to_dlq(
    consumer_cls: MagicMock,
    producer_cls: MagicMock,
    extractor_cls: MagicMock,
    importance_cls: MagicMock,
    trust_cls: MagicMock,
    writer_cls: MagicMock,
) -> None:
    worker = ExtractionWorker(bootstrap_servers="localhost:9092")
    message = MagicMock()
    message.error.return_value = None
    message.value.return_value = b"not-json{"
    message.key.return_value = b"k1"
    message.topic.return_value = "cortex.raw.slack.messages"

    worker._handle_message(message)

    producer_cls.return_value.produce.assert_called_once()
    assert producer_cls.return_value.produce.call_args.kwargs["topic"] == "cortex.dlq.raw"
