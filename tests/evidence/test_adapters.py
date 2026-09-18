"""Tests for V2 Claim/Evidence models and DecisionEvent adapters."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from evidence.adapters import (
    claim_evidence_bundle,
    decision_to_claim,
    decision_to_evidence,
    evidence_graph_enabled,
)
from shared.models import DecisionEvent, Provenance
from shared.v2_models import Claim, Evidence, ReliabilityDecision


def _decision(**kwargs: object) -> DecisionEvent:
    now = datetime.now(UTC)
    base = dict(
        source_raw_event_id="raw-1",
        workspace_id="ws-1",
        event_type="decision",
        content="Migrate payments to CockroachDB.",
        made_by=["priya@"],
        affects=["payments-service"],
        rationale=["scale"],
        extraction_confidence=0.9,
        importance_score=0.8,
        trust_score=0.85,
        provenance=Provenance(
            source="slack",
            channel="#eng",
            original_timestamp=now,
            extractor_version="0.1.0",
            extractor_model="gpt-4o",
            raw_event_id="raw-1",
        ),
        extracted_at=now,
    )
    base.update(kwargs)
    return DecisionEvent(**base)  # type: ignore[arg-type]


def test_decision_to_claim_links_decision_id() -> None:
    d = _decision()
    claim = decision_to_claim(d)
    assert isinstance(claim, Claim)
    assert claim.decision_id == d.event_id
    assert claim.workspace_id == "ws-1"
    assert claim.subject == "payments-service"
    assert claim.status == "ACTIVE"
    assert claim.assertion_type == "ASSERTED"


def test_low_confidence_marked_derived() -> None:
    d = _decision(extraction_confidence=0.5)
    assert decision_to_claim(d).assertion_type == "DERIVED"


def test_agent_manual_marked_inferred() -> None:
    now = datetime.now(UTC)
    d = _decision(
        provenance=Provenance(
            source="manual",
            channel="api",
            original_timestamp=now,
            extractor_version="0.1.0",
            extractor_model="agent-inferred",
            raw_event_id="raw-2",
        )
    )
    assert decision_to_claim(d).assertion_type == "INFERRED"


def test_decision_to_evidence_authority_by_source() -> None:
    d = _decision()
    ev = decision_to_evidence(d)
    assert isinstance(ev, Evidence)
    assert ev.authority_class == "casual_chat"
    assert ev.content_hash


def test_github_source_higher_authority() -> None:
    now = datetime.now(UTC)
    d = _decision(
        provenance=Provenance(
            source="github",
            channel="repo",
            original_timestamp=now,
            extractor_version="0.1.0",
            extractor_model="gpt-4o",
            raw_event_id="pr-1",
        )
    )
    ev = decision_to_evidence(d)
    assert ev.authority_class == "merged_PR"
    assert ev.authority_score >= 0.7


def test_bundle_respects_feature_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_EVIDENCE_GRAPH", "false")
    assert evidence_graph_enabled() is False
    bundle = claim_evidence_bundle(_decision())
    assert bundle["enabled"] is False
    assert bundle["relation"] == "SUPPORTS"
    monkeypatch.setenv("CORTEX_EVIDENCE_GRAPH", "true")
    assert claim_evidence_bundle(_decision())["enabled"] is True


def test_reliability_decision_model() -> None:
    rd = ReliabilityDecision(
        workspace_id="ws-1",
        memory_confidence=0.9,
        action_confidence=0.2,
        risk="HIGH_IMPACT_WRITE",
        decision="BLOCK",
        reason_codes=["STALE_PROCEDURE"],
    )
    assert rd.decision == "BLOCK"
