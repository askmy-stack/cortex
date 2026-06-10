"""Tests for scoring/write_pipeline.py."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from scoring.write_pipeline import (
    DecisionScoringPipeline,
    assert_scored_for_write,
    write_reject_reason,
)
from shared.models import IMPORTANCE_DISCARD, IMPORTANCE_FULL, TRUST_QUARANTINED, DecisionEvent, Provenance

NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _decision(**overrides: object) -> DecisionEvent:
    base = DecisionEvent(
        source_raw_event_id="raw-1",
        workspace_id="ws-1",
        event_type="decision",
        content="We decided to migrate payments to CockroachDB for scale.",
        made_by=["alice@company.com"],
        affects=["payments-service"],
        rationale=["Scale ceiling at 10M txn/day"],
        extraction_confidence=0.9,
        provenance=Provenance(
            source="github",
            channel="payments",
            original_timestamp=NOW,
            extractor_version="0.1.0",
            extractor_model="gpt-4o",
            verified_by=[],
            raw_event_id="raw-1",
        ),
        extracted_at=NOW,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_assert_scored_for_write_rejects_unscored() -> None:
    decision = _decision(importance_score=0.0, trust_score=0.0)
    with pytest.raises(ValueError, match="ImportanceScorer and TrustScorer"):
        assert_scored_for_write(decision)


def test_scoring_pipeline_sets_both_scores() -> None:
    importance = MagicMock()
    trust = MagicMock()

    def _set_importance(decision: DecisionEvent) -> DecisionEvent:
        decision.importance_score = 0.75
        return decision

    def _set_trust(decision: DecisionEvent) -> DecisionEvent:
        decision.trust_score = 0.8
        return decision

    importance.score.side_effect = _set_importance
    trust.score.side_effect = _set_trust

    pipeline = DecisionScoringPipeline(importance=importance, trust=trust)
    decision = _decision()
    pipeline.score(decision)

    importance.score.assert_called_once()
    trust.score.assert_called_once()
    assert decision.importance_score == 0.75
    assert decision.trust_score == 0.8


def test_write_reject_reason_importance_discard() -> None:
    decision = _decision(
        importance_score=IMPORTANCE_DISCARD - 0.05,
        trust_score=0.8,
    )
    assert write_reject_reason(decision) == "importance_discard"


def test_write_reject_reason_trust_quarantine() -> None:
    decision = _decision(
        importance_score=0.75,
        trust_score=TRUST_QUARANTINED - 0.05,
    )
    assert write_reject_reason(decision) == "trust_quarantine"


def test_write_reject_reason_none_when_writable() -> None:
    decision = _decision(importance_score=0.75, trust_score=0.8)
    assert write_reject_reason(decision) is None


def test_write_reject_reason_cmvk_disagreement() -> None:
    decision = _decision(
        importance_score=IMPORTANCE_FULL + 0.05,
        trust_score=0.0,
        status="under_review",
    )
    assert write_reject_reason(decision) == "cmvk_disagreement"


def test_scoring_pipeline_runs_cmvk_for_high_importance() -> None:
    importance = MagicMock()
    trust = MagicMock()
    cmvk = MagicMock()
    cmvk.requires_verification.return_value = True
    cmvk.verify.return_value = MagicMock(approved=True, approved_verifier_ids=["v1", "v2"])

    def _set_importance(decision: DecisionEvent) -> DecisionEvent:
        decision.importance_score = IMPORTANCE_FULL + 0.05
        return decision

    importance.score.side_effect = _set_importance

    def _set_trust(decision: DecisionEvent) -> DecisionEvent:
        decision.trust_score = 0.85
        return decision

    trust.score.side_effect = _set_trust

    pipeline = DecisionScoringPipeline(importance=importance, trust=trust, cmvk=cmvk)
    decision = _decision()
    pipeline.score(decision)

    cmvk.verify.assert_called_once()
    trust.score.assert_called_once()
    assert decision.provenance.verified_by == ["v1", "v2"]


def test_scoring_pipeline_skips_trust_on_cmvk_rejection() -> None:
    importance = MagicMock()
    trust = MagicMock()
    cmvk = MagicMock()
    cmvk.requires_verification.return_value = True
    cmvk.verify.return_value = MagicMock(approved=False, approved_verifier_ids=[])

    def _set_importance(decision: DecisionEvent) -> DecisionEvent:
        decision.importance_score = 0.9
        return decision

    importance.score.side_effect = _set_importance

    pipeline = DecisionScoringPipeline(importance=importance, trust=trust, cmvk=cmvk)
    decision = _decision()
    pipeline.score(decision)

    trust.score.assert_not_called()
    assert decision.status == "under_review"
    assert write_reject_reason(decision) == "cmvk_disagreement"
