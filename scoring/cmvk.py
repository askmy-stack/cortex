"""Cross-Model Verification Kernel (CMVK) — majority voting for high-stakes writes.

Architecture: Phase 4 — events with importance > IMPORTANCE_FULL (0.8) require
verification by three independent verifiers before graph write. Majority vote
(2/3) required; disagreement quarantines the event for human review.

Decision: D-006 — Bayesian trust scoring with CMVK majority voting.

Production: set ``CORTEX_CMVK_BACKEND=openai`` or ``ollama`` for three LLM
verifiers (see ``scoring/cmvk_llm.py``). Default ``heuristic`` keeps dev/test
paths at zero API cost.
"""

from __future__ import annotations

import os
from typing import Protocol

import structlog

from shared.models import IMPORTANCE_FULL, DecisionEvent

log = structlog.get_logger(__name__)

CMVK_VERSION = "0.2.0"
CMVK_VERIFIER_COUNT = 3
CMVK_MAJORITY = 2


class VerifierVote:
    """Single verifier outcome."""

    __slots__ = ("verifier_id", "approved", "rationale")

    def __init__(self, verifier_id: str, approved: bool, rationale: str) -> None:
        self.verifier_id = verifier_id
        self.approved = approved
        self.rationale = rationale


class CMVKResult:
    """Aggregated CMVK outcome for one decision."""

    __slots__ = ("approved", "votes", "approved_verifier_ids")

    def __init__(
        self,
        approved: bool,
        votes: tuple[VerifierVote, ...],
        approved_verifier_ids: list[str],
    ) -> None:
        self.approved = approved
        self.votes = votes
        self.approved_verifier_ids = approved_verifier_ids


class DecisionVerifier(Protocol):
    """Pluggable verifier — LLM-backed in production, heuristic in dev."""

    verifier_id: str

    def verify(self, decision: DecisionEvent) -> VerifierVote: ...


class HeuristicDecisionVerifier:
    """Deterministic verifier stand-in for LLM verifiers (dev/test)."""

    def __init__(self, verifier_id: str, min_confidence: float, require_rationale: bool) -> None:
        self.verifier_id = verifier_id
        self._min_confidence = min_confidence
        self._require_rationale = require_rationale

    def verify(self, decision: DecisionEvent) -> VerifierVote:
        if len(decision.content.strip()) < 20:
            return VerifierVote(self.verifier_id, False, "content too short")
        if decision.extraction_confidence < self._min_confidence:
            return VerifierVote(
                self.verifier_id,
                False,
                f"confidence below {self._min_confidence}",
            )
        if not decision.made_by:
            return VerifierVote(self.verifier_id, False, "no authors")
        if self._require_rationale and not decision.rationale:
            return VerifierVote(self.verifier_id, False, "missing rationale")
        if not decision.affects and not decision.rationale:
            return VerifierVote(self.verifier_id, False, "no affects or rationale")
        return VerifierVote(self.verifier_id, True, "heuristic checks passed")


def default_heuristic_verifiers() -> list[HeuristicDecisionVerifier]:
    """Three independent heuristic verifiers with slightly different strictness."""
    return [
        HeuristicDecisionVerifier("cmvk-heuristic-a", min_confidence=0.50, require_rationale=False),
        HeuristicDecisionVerifier("cmvk-heuristic-b", min_confidence=0.55, require_rationale=False),
        HeuristicDecisionVerifier("cmvk-heuristic-c", min_confidence=0.50, require_rationale=True),
    ]


def build_default_verifiers() -> list[DecisionVerifier]:
    """Select verifier set from ``CORTEX_CMVK_BACKEND`` (default: heuristic)."""
    backend = os.environ.get("CORTEX_CMVK_BACKEND", "heuristic").lower()
    if backend == "heuristic":
        return default_heuristic_verifiers()
    if backend in {"openai", "ollama"}:
        from scoring.cmvk_llm import build_llm_verifiers

        return build_llm_verifiers(backend)
    log.warning("cmvk.unknown_backend", backend=backend, fallback="heuristic")
    return default_heuristic_verifiers()


class CrossModelVerificationKernel:
    """Runs CMVK majority voting when importance exceeds the high-stakes threshold."""

    def __init__(
        self,
        verifiers: list[DecisionVerifier] | None = None,
        *,
        enabled: bool | None = None,
    ) -> None:
        self._verifiers = verifiers or build_default_verifiers()
        if enabled is None:
            enabled = os.environ.get("CORTEX_CMVK_ENABLED", "true").lower() in {
                "1",
                "true",
                "yes",
            }
        self._enabled = enabled
        log.info(
            "cmvk.initialized",
            version=CMVK_VERSION,
            enabled=self._enabled,
            verifier_count=len(self._verifiers),
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def requires_verification(self, decision: DecisionEvent) -> bool:
        """Return True when CMVK must run before write."""
        return self._enabled and decision.importance_score > IMPORTANCE_FULL

    def verify(self, decision: DecisionEvent) -> CMVKResult:
        """Run all verifiers and apply majority vote."""
        votes = tuple(v.verify(decision) for v in self._verifiers)
        approved_ids = [v.verifier_id for v in votes if v.approved]
        approved = len(approved_ids) >= CMVK_MAJORITY

        log.info(
            "cmvk.verified",
            event_id=decision.event_id,
            importance_score=decision.importance_score,
            approved=approved,
            approve_count=len(approved_ids),
            majority_required=CMVK_MAJORITY,
            votes=[{"id": v.verifier_id, "approved": v.approved} for v in votes],
        )

        return CMVKResult(
            approved=approved,
            votes=votes,
            approved_verifier_ids=approved_ids,
        )
