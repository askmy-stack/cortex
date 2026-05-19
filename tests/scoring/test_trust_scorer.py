"""Tests for scoring/trust_scorer.py."""

from __future__ import annotations

from datetime import UTC, datetime

from scoring.trust_scorer import TrustScorer, is_injectable, is_writable
from shared.models import TRUST_LOW_CONFIDENCE, TRUST_QUARANTINED, DecisionEvent, Provenance

NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _decision(confidence: float = 0.9, source: str = "github") -> DecisionEvent:
    return DecisionEvent(
        source_raw_event_id="raw-1",
        workspace_id="ws-1",
        event_type="decision",
        content="We decided to migrate payments to CockroachDB.",
        extraction_confidence=confidence,
        provenance=Provenance(
            source=source,
            channel="payments",
            original_timestamp=NOW,
            extractor_version="0.1.0",
            extractor_model="gpt-4o",
            verified_by=[],
            raw_event_id="raw-1",
        ),
        extracted_at=NOW,
    )


def test_trust_scorer_sets_score() -> None:
    scorer = TrustScorer()
    decision = _decision()
    scored = scorer.score(decision)
    assert 0.0 <= scored.trust_score <= 1.0


def test_verifier_boost_increases_trust() -> None:
    scorer = TrustScorer()
    base = scorer.score_with_breakdown(_decision()).total
    verified = _decision()
    verified.provenance.verified_by = ["verifier-1", "verifier-2"]
    boosted = scorer.score_with_breakdown(verified).total
    assert boosted >= base


def test_writable_and_injectable_thresholds() -> None:
    assert not is_writable(TRUST_QUARANTINED - 0.01)
    assert is_writable(TRUST_QUARANTINED)
    assert not is_injectable(TRUST_LOW_CONFIDENCE - 0.01)
    assert is_injectable(TRUST_LOW_CONFIDENCE)
