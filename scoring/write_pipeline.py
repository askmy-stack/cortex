"""Central scoring pipeline for all graph writes.

Architecture: Phase 4 — every DecisionEvent must pass ImportanceScorer then
TrustScorer before GraphWriter.write(). This module is the single enforcement
point shared by the Kafka worker, demo seed, and any future write paths.
"""

from __future__ import annotations

from typing import Literal

import structlog

from scoring.cmvk import CrossModelVerificationKernel
from scoring.cmvk_llm import validate_cmvk_backend
from scoring.importance import ImportanceScorer
from scoring.trust_scorer import TrustScorer, is_writable
from shared.models import IMPORTANCE_DISCARD, IMPORTANCE_FULL, DecisionEvent

log = structlog.get_logger(__name__)

WriteRejectReason = Literal[
    "unscored",
    "importance_discard",
    "trust_quarantine",
    "cmvk_disagreement",
]


def assert_scored_for_write(decision: DecisionEvent) -> None:
    """Raise when importance/trust scores were never computed."""
    if decision.importance_score <= 0.0 and decision.trust_score <= 0.0:
        raise ValueError(
            "DecisionEvent must pass ImportanceScorer and TrustScorer before graph write. "
            "Both importance_score and trust_score are unset (0.0)."
        )


def write_reject_reason(decision: DecisionEvent) -> WriteRejectReason | None:
    """Return why a scored decision must not be persisted, or None if writable."""
    assert_scored_for_write(decision)
    if (
        decision.importance_score > IMPORTANCE_FULL
        and decision.status == "under_review"
    ):
        return "cmvk_disagreement"
    if decision.importance_score < IMPORTANCE_DISCARD:
        return "importance_discard"
    if not is_writable(decision.trust_score):
        return "trust_quarantine"
    return None


class DecisionScoringPipeline:
    """Runs importance → CMVK (high-stakes) → trust scoring in the required order."""

    def __init__(
        self,
        importance: ImportanceScorer | None = None,
        trust: TrustScorer | None = None,
        cmvk: CrossModelVerificationKernel | None = None,
    ) -> None:
        self._importance = importance or ImportanceScorer()
        self._trust = trust or TrustScorer()
        if cmvk is None:
            validate_cmvk_backend()
        self._cmvk = cmvk or CrossModelVerificationKernel()

    def score(self, decision: DecisionEvent) -> DecisionEvent:
        """Apply importance, optional CMVK, then trust scoring, in place."""
        self._importance.score(decision)

        if self._cmvk.requires_verification(decision):
            result = self._cmvk.verify(decision)
            if result.approved:
                decision.provenance.verified_by = result.approved_verifier_ids
            else:
                decision.status = "under_review"
                log.info(
                    "write_pipeline.cmvk_rejected",
                    event_id=decision.event_id,
                    importance_score=decision.importance_score,
                    approve_count=len(result.approved_verifier_ids),
                )
                return decision

        self._trust.score(decision)
        log.debug(
            "write_pipeline.scored",
            event_id=decision.event_id,
            importance_score=decision.importance_score,
            trust_score=decision.trust_score,
            verified_by=decision.provenance.verified_by,
        )
        return decision
