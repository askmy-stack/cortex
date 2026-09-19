"""Cortex V2 shared models — Claim, Evidence, ReliabilityDecision, temporal types.

Backward compatible with V1 DecisionEvent. Adapters live in evidence/adapters.py.
Feature flag: CORTEX_EVIDENCE_GRAPH (default false until writers are wired).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _uuid4() -> str:
    return str(uuid.uuid4())


TemporalStatus = Literal[
    "CANDIDATE",
    "VERIFIED",
    "ACTIVE",
    "CHALLENGED",
    "SUPERSEDED",
    "ARCHIVED",
    "QUARANTINED",
    "ERASED",
]

AssertionType = Literal["ASSERTED", "OBSERVED", "INFERRED", "DERIVED"]

AuthorityClass = Literal[
    "formal_policy",
    "approved_ADR",
    "production_state",
    "merged_PR",
    "approved_ticket",
    "incident_record",
    "verified_human_statement",
    "casual_chat",
    "agent_inference",
    "external_unverified",
]

ReliabilityVerdict = Literal["ACT", "VERIFY", "ASK", "ESCALATE", "BLOCK"]

ActionRisk = Literal[
    "READ_ONLY",
    "LOW_RISK_WRITE",
    "REVERSIBLE_WRITE",
    "HIGH_IMPACT_WRITE",
    "IRREVERSIBLE",
    "PRIVILEGED",
]


class Evidence(BaseModel):
    """Source-backed support or conflict for a Claim."""

    id: str = Field(default_factory=_uuid4)
    workspace_id: str
    source_type: str = Field(description="slack | github | adr | incident | ...")
    source_id: str
    source_uri: str | None = None
    author: str | None = None
    content_hash: str | None = None
    authority_class: AuthorityClass = "casual_chat"
    authority_score: float = Field(default=0.5, ge=0.0, le=1.0)
    captured_at: datetime = Field(default_factory=_utcnow)
    observed_at: datetime | None = None
    integrity_state: Literal["ok", "quarantined", "tampered", "unknown"] = "ok"
    access_policy: dict[str, Any] = Field(default_factory=dict)
    snippet: str | None = Field(default=None, description="Short evidence excerpt")

    model_config = ConfigDict()


class Claim(BaseModel):
    """Organizational belief supported by Evidence (V2 atomic memory unit)."""

    id: str = Field(default_factory=_uuid4)
    workspace_id: str
    subject: str = Field(description="Entity the claim is about, e.g. payments-service")
    predicate: str = Field(description="Relation, e.g. uses_database")
    object: str = Field(description="Value, e.g. CockroachDB")
    claim_type: str = Field(default="fact", description="fact | policy | procedure_assumption")
    assertion_type: AssertionType = "ASSERTED"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: TemporalStatus = "CANDIDATE"
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    observed_at: datetime | None = None
    invalidated_at: datetime | None = None
    superseded_by: str | None = None
    decision_id: str | None = Field(
        default=None,
        description="Optional link to V1 DecisionEvent.event_id",
    )
    content: str = Field(default="", description="Human-readable claim summary")
    access_policy: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    model_config = ConfigDict()


class ReliabilityDecision(BaseModel):
    """Typed gate output: whether memory is safe enough for an action."""

    id: str = Field(default_factory=_uuid4)
    workspace_id: str
    query_id: str | None = None
    candidate_action: dict[str, Any] = Field(default_factory=dict)
    memory_confidence: float = Field(ge=0.0, le=1.0)
    action_confidence: float = Field(ge=0.0, le=1.0)
    risk: ActionRisk = "READ_ONLY"
    decision: ReliabilityVerdict
    reason_codes: list[str] = Field(default_factory=list)
    required_checks: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    trace_id: str | None = None

    model_config = ConfigDict()


class KnowledgeGap(BaseModel):
    """Aggregated missing/stale/contradictory knowledge for a domain."""

    id: str = Field(default_factory=_uuid4)
    workspace_id: str
    domain: str
    gap_type: str
    description: str
    frequency: int = 1
    coverage_score: float = Field(default=0.0, ge=0.0, le=1.0)
    first_seen: datetime = Field(default_factory=_utcnow)
    last_seen: datetime = Field(default_factory=_utcnow)
    status: Literal["open", "mitigated", "closed"] = "open"

    model_config = ConfigDict()
