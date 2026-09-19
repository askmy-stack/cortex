"""Adapters between V1 DecisionEvent and V2 Claim/Evidence."""

from __future__ import annotations

import hashlib
import os
from typing import Any

from shared.models import DecisionEvent
from shared.v2_models import AssertionType, AuthorityClass, Claim, Evidence


def evidence_graph_enabled() -> bool:
    """Return True when CORTEX_EVIDENCE_GRAPH is enabled."""
    return os.environ.get("CORTEX_EVIDENCE_GRAPH", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _authority_for_source(source: str) -> tuple[AuthorityClass, float]:
    """Map connector source to authority class + default score."""
    mapping: dict[str, tuple[AuthorityClass, float]] = {
        "github": ("merged_PR", 0.75),
        "jira": ("approved_ticket", 0.70),
        "linear": ("approved_ticket", 0.70),
        "slack": ("casual_chat", 0.45),
        "meeting": ("verified_human_statement", 0.55),
        "cicd": ("production_state", 0.80),
        "manual": ("verified_human_statement", 0.60),
    }
    return mapping.get(source, ("external_unverified", 0.30))


def _assertion_for_decision(decision: DecisionEvent) -> AssertionType:
    """Label agent/manual inference vs observed organizational decisions."""
    model = (decision.provenance.extractor_model or "").lower()
    if decision.provenance.source == "manual" and "agent" in model:
        return "INFERRED"
    if decision.extraction_confidence < 0.7:
        return "DERIVED"
    return "ASSERTED"


def decision_to_claim(
    decision: DecisionEvent,
    *,
    subject: str | None = None,
    predicate: str = "decided",
    object_: str | None = None,
) -> Claim:
    """Map a V1 DecisionEvent to a V2 Claim without mutating the decision."""
    subj = subject or (decision.affects[0] if decision.affects else "organization")
    obj = object_ or decision.content[:200]
    status = "ACTIVE" if decision.status == "active" else "SUPERSEDED"
    if decision.status == "archived":
        status = "ARCHIVED"
    elif decision.status == "under_review":
        status = "CHALLENGED"
    return Claim(
        workspace_id=decision.workspace_id,
        subject=subj,
        predicate=predicate,
        object=obj,
        claim_type="decision",
        assertion_type=_assertion_for_decision(decision),
        confidence=max(decision.trust_score, decision.extraction_confidence),
        status=status,  # type: ignore[arg-type]
        valid_from=decision.extracted_at,
        observed_at=decision.extracted_at,
        decision_id=decision.event_id,
        content=decision.content,
        superseded_by=None if decision.status != "superseded" else decision.replaces,
    )


def decision_to_evidence(decision: DecisionEvent) -> Evidence:
    """Create primary Evidence from the decision provenance chain."""
    authority_class, authority_score = _authority_for_source(decision.provenance.source)
    raw = f"{decision.provenance.raw_event_id}:{decision.content}".encode()
    return Evidence(
        workspace_id=decision.workspace_id,
        source_type=decision.provenance.source,
        source_id=decision.provenance.raw_event_id,
        source_uri=None,
        author=decision.made_by[0] if decision.made_by else None,
        content_hash=hashlib.sha256(raw).hexdigest()[:32],
        authority_class=authority_class,
        authority_score=authority_score,
        captured_at=decision.extracted_at,
        observed_at=decision.provenance.original_timestamp,
        integrity_state="ok",
        snippet=decision.content[:280],
        access_policy={},
    )


def claim_evidence_bundle(decision: DecisionEvent) -> dict[str, Any]:
    """Return claim + supporting evidence for optional graph write paths."""
    claim = decision_to_claim(decision)
    evidence = decision_to_evidence(decision)
    return {
        "claim": claim,
        "evidence": [evidence],
        "relation": "SUPPORTS",
        "enabled": evidence_graph_enabled(),
    }
