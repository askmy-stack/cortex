"""Importance scorer — assigns an importance_score to every DecisionEvent.

Architecture: Layer 2 — Extraction Engine (post-extraction scoring).
Decision: D-007 — Importance scoring at ingestion (noise filter).
Decision: D-003 — Every write goes through importance scorer THEN trust scorer.

Scoring model (v0.1 — heuristic, no LLM):
  importance_score = weighted combination of:
    - event_type weight     (decisions > exceptions > rationale > updates > escalations)
    - person_signal         (named people boost signal)
    - system_signal         (named systems boost signal)
    - rationale_signal      (explicit rationale = higher signal)
    - content_length_signal (very short = low signal; medium = peak; very long = slight penalty)
    - supersedes_signal     (replacing a previous decision = high importance)

Thresholds (shared/models.py):
  < 0.30: discard — graph writer must reject
  0.30–0.60: compressed storage
  0.60–0.80: full storage
  > 0.80: full storage + relationship extraction + agent notify
"""

from __future__ import annotations

import math
from typing import NamedTuple

import structlog

from shared.models import (
    IMPORTANCE_COMPRESS,
    IMPORTANCE_DISCARD,
    IMPORTANCE_FULL,
    DecisionEvent,
)

log = structlog.get_logger(__name__)

SCORER_VERSION = "0.1.0"

# ─────────────────────────────────────────────────────────────────────────────
# Signal weights (sum to 1.0)
# ─────────────────────────────────────────────────────────────────────────────

_W_EVENT_TYPE = 0.35
_W_PERSON = 0.20
_W_SYSTEM = 0.20
_W_RATIONALE = 0.15
_W_CONTENT_LENGTH = 0.05
_W_SUPERSEDES = 0.05

# Event type base scores
_EVENT_TYPE_SCORES: dict[str, float] = {
    "decision": 1.0,
    "exception": 0.75,
    "rationale": 0.65,
    "escalation": 0.60,
    "update": 0.45,
}

# Content length scoring (tokens ≈ chars / 4)
_CONTENT_LENGTH_PEAK = 200    # chars — peak signal
_CONTENT_LENGTH_MIN = 20     # chars — below this is noise
_CONTENT_LENGTH_MAX = 2000   # chars — above this has slight penalty


# ─────────────────────────────────────────────────────────────────────────────
# Score breakdown for logging/debugging
# ─────────────────────────────────────────────────────────────────────────────


class ImportanceBreakdown(NamedTuple):
    """Decomposed importance score components."""

    event_type_score: float
    person_score: float
    system_score: float
    rationale_score: float
    content_length_score: float
    supersedes_score: float
    total: float
    band: str


# ─────────────────────────────────────────────────────────────────────────────
# Signal component scorers
# ─────────────────────────────────────────────────────────────────────────────


def _score_event_type(event_type: str) -> float:
    """Base score from event type classification."""
    return _EVENT_TYPE_SCORES.get(event_type, 0.40)


def _score_persons(made_by: list[str]) -> float:
    """Person signal — decisions with named authors score higher.

    Reasoning: anonymous decisions are lower quality signal.
    Caps at 1.0 after 3 named people (marginal value decreases).
    """
    if not made_by:
        return 0.20
    named = [p for p in made_by if p and p != "unknown"]
    if not named:
        return 0.20
    return min(1.0, 0.50 + 0.25 * len(named))


def _score_systems(affects: list[str]) -> float:
    """System signal — decisions affecting named systems are more specific.

    Reasoning: vague decisions ("we changed something") are lower value.
    """
    if not affects:
        return 0.20
    return min(1.0, 0.50 + 0.20 * len(affects))


def _score_rationale(rationale: list[str]) -> float:
    """Rationale signal — explicit reasoning is the gold standard.

    Decisions with recorded rationale are 2x more likely to be useful
    for future agents than bare decisions with no context.
    """
    if not rationale:
        return 0.10
    non_empty = [r for r in rationale if r and len(r.strip()) > 5]
    if not non_empty:
        return 0.10
    return min(1.0, 0.60 + 0.20 * len(non_empty))


def _score_content_length(content: str) -> float:
    """Content length signal — uses a bell curve around optimal length.

    Too short (< 20 chars): noise, not a real decision.
    Optimal (~200 chars): clear, concise decision.
    Too long (> 2000 chars): may be padded or unstructured.
    """
    length = len(content.strip())

    if length < _CONTENT_LENGTH_MIN:
        return 0.10

    if length <= _CONTENT_LENGTH_PEAK:
        return 0.40 + 0.60 * (length / _CONTENT_LENGTH_PEAK)

    if length <= _CONTENT_LENGTH_MAX:
        return 1.0 - 0.30 * math.log(length / _CONTENT_LENGTH_PEAK) / math.log(
            _CONTENT_LENGTH_MAX / _CONTENT_LENGTH_PEAK
        )

    return 0.60


def _score_supersedes(replaces: str | None) -> float:
    """Supersedes signal — replacing a previous decision signals intentionality."""
    return 1.0 if replaces else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Importance scorer
# ─────────────────────────────────────────────────────────────────────────────


class ImportanceScorer:
    """Assigns importance_score to DecisionEvents before graph write.

    Usage:
        scorer = ImportanceScorer()
        scored_decision = scorer.score(decision)
        # scored_decision.importance_score is now set
    """

    def __init__(self) -> None:
        log.info("importance_scorer.initialized", version=SCORER_VERSION)

    def score(self, decision: DecisionEvent) -> DecisionEvent:
        """Compute and assign importance_score to a DecisionEvent.

        Modifies decision.importance_score in-place (returns same object).
        Logs a full breakdown of signal components.

        Args:
            decision: DecisionEvent with extraction_confidence already set.

        Returns:
            The same DecisionEvent with importance_score populated.
        """
        breakdown = self.score_with_breakdown(decision)

        decision.importance_score = breakdown.total

        log.info(
            "importance_scorer.scored",
            event_id=decision.event_id,
            event_type=decision.event_type,
            importance_score=breakdown.total,
            band=breakdown.band,
            event_type_score=breakdown.event_type_score,
            person_score=breakdown.person_score,
            system_score=breakdown.system_score,
            rationale_score=breakdown.rationale_score,
            content_length_score=breakdown.content_length_score,
            supersedes_score=breakdown.supersedes_score,
        )

        return decision

    def score_with_breakdown(self, decision: DecisionEvent) -> ImportanceBreakdown:
        """Compute importance score and return full signal breakdown.

        Useful for tests and debugging. Does NOT mutate the decision.

        Args:
            decision: The DecisionEvent to score.

        Returns:
            ImportanceBreakdown with all component scores and final total.
        """
        et_score = _score_event_type(decision.event_type)
        person_score = _score_persons(decision.made_by)
        system_score = _score_systems(decision.affects)
        rationale_score = _score_rationale(decision.rationale)
        content_score = _score_content_length(decision.content)
        supersedes_score = _score_supersedes(decision.replaces)

        # Weighted sum
        total = (
            _W_EVENT_TYPE * et_score
            + _W_PERSON * person_score
            + _W_SYSTEM * system_score
            + _W_RATIONALE * rationale_score
            + _W_CONTENT_LENGTH * content_score
            + _W_SUPERSEDES * supersedes_score
        )

        # Clamp to [0, 1]
        total = max(0.0, min(1.0, round(total, 4)))

        band = _importance_band(total)

        return ImportanceBreakdown(
            event_type_score=round(et_score, 4),
            person_score=round(person_score, 4),
            system_score=round(system_score, 4),
            rationale_score=round(rationale_score, 4),
            content_length_score=round(content_score, 4),
            supersedes_score=round(supersedes_score, 4),
            total=total,
            band=band,
        )


def _importance_band(score: float) -> str:
    """Classify score into storage band."""
    if score < IMPORTANCE_DISCARD:
        return "discard"
    if score < IMPORTANCE_COMPRESS:
        return "compress"
    if score < IMPORTANCE_FULL:
        return "full"
    return "full_notify"
