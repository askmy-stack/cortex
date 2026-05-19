"""Trust scorer — Bayesian confidence for DecisionEvents before graph write.

Architecture: Layer 2 — Extraction Engine (post-importance scoring).
Decision: D-006 — Bayesian trust scoring with provenance chain.
"""

from __future__ import annotations

from typing import NamedTuple

import structlog

from shared.models import (
    TRUST_LOW_CONFIDENCE,
    TRUST_QUARANTINED,
    DecisionEvent,
)

log = structlog.get_logger(__name__)

SCORER_VERSION = "0.1.0"

_SOURCE_PRIOR: dict[str, float] = {
    "slack": 0.55,
    "github": 0.65,
    "jira": 0.60,
    "linear": 0.60,
    "meeting": 0.50,
    "cicd": 0.55,
}
_DEFAULT_SOURCE_PRIOR = 0.50
_VERIFIER_BOOST = 0.08
_VERIFIER_CAP = 0.25


class TrustBreakdown(NamedTuple):
    """Decomposed trust score components."""

    extraction_confidence: float
    source_prior: float
    verifier_boost: float
    total: float
    band: str


class TrustScorer:
    """Assigns trust_score to DecisionEvents after importance scoring."""

    def __init__(self) -> None:
        log.info("trust_scorer.initialized", version=SCORER_VERSION)

    def score(self, decision: DecisionEvent) -> DecisionEvent:
        """Compute and assign trust_score on the DecisionEvent."""
        breakdown = self.score_with_breakdown(decision)
        decision.trust_score = breakdown.total
        log.info(
            "trust_scorer.scored",
            event_id=decision.event_id,
            trust_score=breakdown.total,
            band=breakdown.band,
            extraction_confidence=breakdown.extraction_confidence,
            source_prior=breakdown.source_prior,
            verifier_boost=breakdown.verifier_boost,
        )
        return decision

    def score_with_breakdown(self, decision: DecisionEvent) -> TrustBreakdown:
        """Return trust components without mutating the decision."""
        extraction_confidence = decision.extraction_confidence
        source_prior = _SOURCE_PRIOR.get(
            decision.provenance.source,
            _DEFAULT_SOURCE_PRIOR,
        )
        verifier_boost = min(
            _VERIFIER_CAP,
            len(decision.provenance.verified_by) * _VERIFIER_BOOST,
        )

        # Bayesian-style combination: prior updated by extraction confidence and corroboration.
        posterior = 1.0 - (1.0 - source_prior) * (1.0 - extraction_confidence)
        total = posterior + verifier_boost
        total = max(0.0, min(1.0, round(total, 4)))

        return TrustBreakdown(
            extraction_confidence=round(extraction_confidence, 4),
            source_prior=round(source_prior, 4),
            verifier_boost=round(verifier_boost, 4),
            total=total,
            band=_trust_band(total),
        )


def _trust_band(score: float) -> str:
    if score < TRUST_QUARANTINED:
        return "quarantined"
    if score < TRUST_LOW_CONFIDENCE:
        return "low_confidence"
    return "trusted"


def is_injectable(trust_score: float) -> bool:
    """Return True when a decision may be injected into agent context."""
    return trust_score >= TRUST_LOW_CONFIDENCE


def is_writable(trust_score: float) -> bool:
    """Return True when a decision may be persisted to the graph."""
    return trust_score >= TRUST_QUARANTINED
