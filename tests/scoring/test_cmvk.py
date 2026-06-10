"""Tests for scoring/cmvk.py."""

from __future__ import annotations

from datetime import UTC, datetime

from scoring.cmvk import (
    CMVK_MAJORITY,
    CrossModelVerificationKernel,
    HeuristicDecisionVerifier,
    VerifierVote,
)
from shared.models import IMPORTANCE_FULL, DecisionEvent, Provenance

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
        importance_score=IMPORTANCE_FULL + 0.05,
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


class _FixedVerifier:
    def __init__(self, verifier_id: str, approved: bool) -> None:
        self.verifier_id = verifier_id
        self._approved = approved

    def verify(self, decision: DecisionEvent) -> VerifierVote:
        return VerifierVote(self.verifier_id, self._approved, "fixed")


def test_requires_verification_above_threshold() -> None:
    kernel = CrossModelVerificationKernel(enabled=True)
    assert kernel.requires_verification(_decision(importance_score=IMPORTANCE_FULL + 0.01))
    assert not kernel.requires_verification(_decision(importance_score=IMPORTANCE_FULL))
    assert not kernel.requires_verification(_decision(importance_score=0.75))


def test_majority_vote_approves_with_two_of_three() -> None:
    kernel = CrossModelVerificationKernel(
        verifiers=[
            _FixedVerifier("v1", True),
            _FixedVerifier("v2", True),
            _FixedVerifier("v3", False),
        ],
        enabled=True,
    )
    result = kernel.verify(_decision())
    assert result.approved
    assert result.approved_verifier_ids == ["v1", "v2"]
    assert len(result.votes) == 3


def test_majority_vote_rejects_with_one_of_three() -> None:
    kernel = CrossModelVerificationKernel(
        verifiers=[
            _FixedVerifier("v1", True),
            _FixedVerifier("v2", False),
            _FixedVerifier("v3", False),
        ],
        enabled=True,
    )
    result = kernel.verify(_decision())
    assert not result.approved
    assert result.approved_verifier_ids == ["v1"]


def test_heuristic_verifiers_approve_well_formed_decision() -> None:
    kernel = CrossModelVerificationKernel(enabled=True)
    result = kernel.verify(_decision())
    assert result.approved
    assert len(result.approved_verifier_ids) >= CMVK_MAJORITY


def test_heuristic_verifiers_reject_sparse_decision() -> None:
    kernel = CrossModelVerificationKernel(enabled=True)
    sparse = _decision(
        content="ok",
        made_by=[],
        affects=[],
        rationale=[],
        extraction_confidence=0.2,
    )
    result = kernel.verify(sparse)
    assert not result.approved


def test_disabled_kernel_skips_verification_requirement() -> None:
    kernel = CrossModelVerificationKernel(enabled=False)
    assert not kernel.requires_verification(_decision(importance_score=0.95))
