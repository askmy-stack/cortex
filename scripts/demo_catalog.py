"""Demo organizational memory catalog for stress testing and portfolio demos.

Covers architecture, Slack, GitHub, RFCs, meetings, incidents, product, engineering,
team comms, and cross-functional decisions. Idempotent via deterministic UUIDs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from shared.models import DecisionEvent, Provenance

OrgScale = Literal["small", "startup", "mid", "enterprise"]

SCALE_MULTIPLIERS: dict[OrgScale, int] = {
    "small": 1,
    "startup": 1,
    "mid": 5,
    "enterprise": 10,
}


def demo_uuid(name: str) -> str:
    """Deterministic UUID for idempotent MERGE."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"cortex.demo:{name}"))


def _provenance(
    *,
    source: str,
    channel: str,
    raw_name: str,
    now: datetime,
) -> Provenance:
    raw_id = demo_uuid(raw_name)
    return Provenance(
        source=source,
        channel=channel,
        original_timestamp=now,
        extractor_version="demo-seed",
        extractor_model="seed-script",
        verified_by=[],
        raw_event_id=raw_id,
    )


def _spec(
    name: str,
    *,
    source: str,
    channel: str,
    content: str,
    made_by: list[str],
    affects: list[str],
    rationale: list[str],
    event_type: str = "decision",
    importance: float = 0.75,
    trust: float = 0.78,
    confidence: float = 0.9,
    triggered_by: str | None = None,
    replaces: str | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "source": source,
        "channel": channel,
        "content": content,
        "made_by": made_by,
        "affects": affects,
        "rationale": rationale,
        "event_type": event_type,
        "importance": importance,
        "trust": trust,
        "confidence": confidence,
        "triggered_by": triggered_by,
        "replaces": replaces,
    }


# Ten canonical demo decisions — 5× the original two-decision seed.
BASE_DECISION_SPECS: list[dict[str, object]] = [
    _spec(
        "decision-cockroach",
        source="slack",
        channel="C-architecture",
        content=(
            "We decided to migrate the payments service from PostgreSQL to CockroachDB "
            "for multi-region active-active replication and predictable scale past 10M txn/day."
        ),
        made_by=["priya@acme.example", "dan@acme.example"],
        affects=["payments-service", "billing-service"],
        rationale=[
            "Incident #247 showed Postgres failover gaps in eu-west.",
            "Finance signed off on incremental infra cost for HA.",
        ],
        importance=0.88,
        trust=0.82,
        triggered_by="incident-247",
    ),
    _spec(
        "decision-cache",
        source="github",
        channel="acme/payments-platform",
        content=(
            "We standardized on Redis Cluster for hot payment session state with TTL-based "
            "eviction; Postgres remains system of record for balances."
        ),
        made_by=["ops@acme.example"],
        affects=["payments-service"],
        rationale=["Sub-10ms p99 for session reads during checkout."],
        importance=0.72,
        trust=0.78,
    ),
    _spec(
        "decision-api-versioning",
        source="github",
        channel="acme/platform-api",
        content=(
            "GitHub discussion #842 concluded: public REST APIs use calendar versioning "
            "(v2026-03) with six-month deprecation windows; breaking changes require RFC."
        ),
        made_by=["api-lead@acme.example"],
        affects=["public-api", "developer-portal"],
        rationale=["Third-party integrators need predictable upgrade paths."],
        importance=0.8,
        trust=0.85,
    ),
    _spec(
        "decision-auth-rfc",
        source="manual",
        channel="RFC-014-oauth-migration",
        content=(
            "RFC-014 approved: migrate internal services from shared API keys to OAuth2 "
            "client credentials with short-lived JWTs and workspace-scoped RBAC."
        ),
        made_by=["security@acme.example", "platform@acme.example"],
        affects=["auth-service", "api-gateway"],
        rationale=["Audit requirement for SOC2 Type II.", "Eliminates long-lived secrets in repos."],
        importance=0.91,
        trust=0.88,
    ),
    _spec(
        "decision-q3-roadmap",
        source="meeting",
        channel="leadership-sync-2026-05",
        content=(
            "Q3 roadmap prioritizes organizational memory (Cortex), billing revamp, and "
            "EU data residency — deferring mobile app v2 to Q4."
        ),
        made_by=["ceo@acme.example", "cpo@acme.example"],
        affects=["product-roadmap", "billing-service", "cortex"],
        rationale=["Enterprise pipeline blocked on memory + residency.", "Mobile v2 lacks design sign-off."],
        importance=0.86,
        trust=0.8,
    ),
    _spec(
        "decision-incident-247",
        source="cicd",
        channel="incident-247-postmortem",
        content=(
            "Post-incident: payments failover must complete under 60s; add chaos drills monthly "
            "and block deploys without multi-AZ validation."
        ),
        made_by=["sre@acme.example"],
        affects=["payments-service", "sre-oncall"],
        rationale=["eu-west failover exceeded RTO during #247."],
        event_type="escalation",
        importance=0.9,
        trust=0.84,
        triggered_by="incident-247",
    ),
    _spec(
        "decision-pricing-tier",
        source="slack",
        channel="C-product",
        content=(
            "Product decided to launch Enterprise tier with SSO, audit logs, and dedicated "
            "support — Pro remains self-serve with usage caps."
        ),
        made_by=["cpo@acme.example", "revops@acme.example"],
        affects=["pricing", "sales-playbook"],
        rationale=["Top 5 deals requested SSO and audit trail."],
        importance=0.83,
        trust=0.79,
    ),
    _spec(
        "decision-monorepo",
        source="slack",
        channel="C-engineering",
        content=(
            "Engineering agreed to consolidate 14 micro-repos into a Turborepo monorepo for "
            "shared types and unified CI — exceptions require architecture review."
        ),
        made_by=["eng-dir@acme.example"],
        affects=["platform-tooling", "ci-pipeline"],
        rationale=["Duplicate CI config caused drift.", "Onboarding slowed by repo sprawl."],
        importance=0.77,
        trust=0.76,
    ),
    _spec(
        "decision-oncall-rotation",
        source="slack",
        channel="C-team-ops",
        content=(
            "Ops team adopted follow-the-sun on-call with handoff runbooks in Cortex; "
            "PagerDuty schedules sync from Linear incident labels."
        ),
        made_by=["ops@acme.example", "manager@acme.example"],
        affects=["sre-oncall", "incident-response"],
        rationale=["APAC gaps in previous single-region rotation."],
        importance=0.7,
        trust=0.75,
    ),
    _spec(
        "decision-data-residency",
        source="meeting",
        channel="legal-eng-sync",
        content=(
            "Legal and Engineering aligned: EU customer PII stays in eu-central-1; "
            "US analytics may use aggregated exports only after DPA review."
        ),
        made_by=["legal@acme.example", "cto@acme.example"],
        affects=["data-platform", "billing-service", "cortex"],
        rationale=["German enterprise deal requires EU residency attestation."],
        importance=0.89,
        trust=0.87,
    ),
    _spec(
        "decision-cache-contradiction",
        source="slack",
        channel="C-architecture",
        content=(
            "Architecture review reopened cache strategy: evaluate DynamoDB DAX instead of "
            "Redis Cluster for session state due to ops headcount constraints."
        ),
        made_by=["dan@acme.example"],
        affects=["payments-service"],
        rationale=["Redis cluster ops burden on a team of two."],
        importance=0.68,
        trust=0.7,
        event_type="update",
        replaces=demo_uuid("decision-cache"),
    ),
]


def build_decision_from_spec(
    spec: dict[str, object],
    workspace_id: str,
    *,
    suffix: str = "",
    batch: int = 0,
) -> DecisionEvent:
    """Materialize a catalog spec into a DecisionEvent."""
    now = datetime.now(UTC)
    name = str(spec["name"]) + suffix
    raw_name = f"raw-{spec['name']}{suffix}"
    content = str(spec["content"])
    if batch > 0:
        content = f"{content} (org growth batch {batch})"

    return DecisionEvent(
        event_id=demo_uuid(name),
        source_raw_event_id=demo_uuid(raw_name),
        workspace_id=workspace_id,
        event_type=str(spec.get("event_type", "decision")),  # type: ignore[arg-type]
        content=content,
        made_by=list(spec["made_by"]),  # type: ignore[arg-type]
        affects=list(spec["affects"]),  # type: ignore[arg-type]
        rationale=list(spec["rationale"]),  # type: ignore[arg-type]
        triggered_by=spec.get("triggered_by"),  # type: ignore[arg-type]
        replaces=spec.get("replaces"),  # type: ignore[arg-type]
        extraction_confidence=float(spec["confidence"]),  # type: ignore[arg-type]
        importance_score=float(spec["importance"]),  # type: ignore[arg-type]
        trust_score=float(spec["trust"]),  # type: ignore[arg-type]
        provenance=_provenance(
            source=str(spec["source"]),
            channel=str(spec["channel"]),
            raw_name=raw_name,
            now=now,
        ),
        extracted_at=now,
    )


def build_demo_decisions(
    workspace_id: str,
    scale: OrgScale = "small",
) -> list[DecisionEvent]:
    """Build demo decisions; scale multiplies catalog for stress testing."""
    multiplier = SCALE_MULTIPLIERS[scale]
    decisions: list[DecisionEvent] = []

    for batch in range(multiplier):
        suffix = "" if batch == 0 else f"-b{batch}"
        for spec in BASE_DECISION_SPECS:
            decisions.append(
                build_decision_from_spec(
                    spec,
                    workspace_id,
                    suffix=suffix,
                    batch=batch,
                )
            )

    return decisions


# Backward-compatible builders for existing tests.
def build_primary_decision(workspace_id: str) -> DecisionEvent:
    return build_decision_from_spec(BASE_DECISION_SPECS[0], workspace_id)


def build_secondary_decision(workspace_id: str) -> DecisionEvent:
    return build_decision_from_spec(BASE_DECISION_SPECS[1], workspace_id)
