"""Shared Pydantic models — canonical schemas used across all Cortex services.

Every connector outputs RawEvent. The extraction engine outputs DecisionEvent.
These schemas are the contracts that keep the pipeline consistent.

Decision: D-003 — Decision events as atomic memory unit (not raw text).
Architecture: Layer 1 → Layer 2 contract.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def _uuid4() -> str:
    """Return a new UUID4 string."""
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# Layer 1 → Layer 2: RawEvent
# Emitted by every connector into Kafka topic cortex.raw.{source}.{event_type}
# ─────────────────────────────────────────────────────────────────────────────


class RawEvent(BaseModel):
    """Canonical schema for all connector output.

    Connectors are stateless — they transform tool-specific events into RawEvent
    and publish to Kafka. No business logic beyond schema normalisation.
    """

    event_id: str = Field(default_factory=_uuid4, description="UUID4 — unique event ID")
    source: Literal["slack", "github", "jira", "linear", "meeting", "cicd"] = Field(
        description="Tool the event originated from"
    )
    source_id: str = Field(description="Original ID from the source tool")
    workspace_id: str = Field(description="Org identifier (e.g. Slack workspace ID)")
    event_type: str = Field(
        description="slack:message | github:commit | github:pr | jira:issue | etc."
    )
    content: str = Field(description="Raw text content of the event")
    author: str = Field(description="Canonical author ID — email or tool username")
    channel: str = Field(
        description="Slack channel, GitHub repo, Jira project, etc."
    )
    timestamp: datetime = Field(description="When the event occurred — UTC")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific fields (thread_ts, PR number, reaction counts, etc.)",
    )
    schema_version: str = Field(default="1.0", description="Schema version for forward compat")
    ingested_at: datetime = Field(
        default_factory=_utcnow, description="When Cortex received this event — UTC"
    )

    model_config = ConfigDict()


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2 → Layer 3: Provenance
# Required on every DecisionEvent write — audit trail for trust scoring.
# ─────────────────────────────────────────────────────────────────────────────


class Provenance(BaseModel):
    """Audit trail required on every memory write.

    Decision: D-006 — Bayesian trust scoring requires provenance chain on every node.
    """

    source: str = Field(description="'slack' | 'github' | 'jira' | ...")
    channel: str = Field(description="Source channel or repo")
    original_timestamp: datetime = Field(description="When the source event occurred — UTC")
    extractor_version: str = Field(description="Extractor version string, e.g. '0.1.0'")
    extractor_model: str = Field(
        description="LLM model used: 'gpt-4o' | 'gemma2:latest'"
    )
    verified_by: list[str] = Field(
        default_factory=list,
        description="Verifier IDs from CMVK (Cross-Model Verification Kernel)",
    )
    raw_event_id: str = Field(description="RawEvent.event_id this was extracted from")


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2 → Layer 3: DecisionEvent
# Emitted by extraction engine into Kafka topic cortex.extracted.decisions
# ─────────────────────────────────────────────────────────────────────────────

EventType = Literal["decision", "exception", "rationale", "update", "escalation"]
DecisionStatus = Literal["active", "superseded", "under_review", "archived"]


class DecisionEvent(BaseModel):
    """Atomic unit of organizational memory.

    Extracted from RawEvents by the decision extractor. Every field is required
    before a DecisionEvent can be written to the Neo4j graph.

    Pipeline position: extraction engine output → importance scorer → trust scorer → graph writer.
    Decision: D-003 — Decision events as atomic memory unit (not raw text).
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    event_id: str = Field(default_factory=_uuid4, description="UUID4")
    source_raw_event_id: str = Field(
        description="RawEvent.event_id this was extracted from"
    )
    workspace_id: str = Field(description="Org identifier")

    # ── Classification ────────────────────────────────────────────────────────
    event_type: EventType = Field(
        description="What kind of organisational event this is"
    )

    # ── Content ───────────────────────────────────────────────────────────────
    content: str = Field(
        description="Clean summary of the decision — one or two sentences"
    )
    made_by: list[str] = Field(
        default_factory=list,
        description="Canonical person IDs (email or username)",
    )
    affects: list[str] = Field(
        default_factory=list,
        description="Canonical system / service / team IDs",
    )
    rationale: list[str] = Field(
        default_factory=list,
        description="Reasons stated for this decision",
    )
    replaces: str | None = Field(
        default=None,
        description="DecisionEvent.event_id this supersedes (null if new)",
    )
    triggered_by: str | None = Field(
        default=None,
        description="Incident / ticket / issue ID that caused this decision",
    )
    status: DecisionStatus = Field(default="active")

    # ── Quality signals ───────────────────────────────────────────────────────
    extraction_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="LLM confidence in extraction correctness. < 0.4 → discard.",
    )
    importance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Computed by ImportanceScorer. 0 until scored.",
    )
    trust_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Computed by TrustScorer. 0 until scored.",
    )

    # ── Provenance (required on every write) ──────────────────────────────────
    provenance: Provenance = Field(
        description="Full audit trail — source, extractor, verifiers"
    )

    extracted_at: datetime = Field(default_factory=_utcnow)

    model_config = ConfigDict()

    @field_validator("extraction_confidence")
    @classmethod
    def validate_confidence_threshold(cls, v: float) -> float:
        """Warn when extraction confidence is below the discard threshold.

        Below 0.4 events should be discarded by the extractor, not passed here.
        The validator does not raise — it allows the caller to apply thresholds.
        """
        return v


# ─────────────────────────────────────────────────────────────────────────────
# Confidence thresholds (referenced by extractor and graph writer)
# ─────────────────────────────────────────────────────────────────────────────

CONFIDENCE_DISCARD: float = 0.4       # Below this: discard, do not write
CONFIDENCE_REVIEW: float = 0.7        # 0.4–0.7: write to human review queue
CONFIDENCE_TRUST: float = 0.7         # Above this: pass to importance scorer

IMPORTANCE_DISCARD: float = 0.30      # Below this: discard entirely
IMPORTANCE_COMPRESS: float = 0.60     # 0.30–0.60: store compressed 3-sentence summary
IMPORTANCE_FULL: float = 0.80         # 0.60–0.80: store full DecisionEvent
                                       # Above 0.80: full + relationship extraction + agent notify

TRUST_QUARANTINED: float = 0.40       # Below this: quarantine — never injected
TRUST_LOW_CONFIDENCE: float = 0.70    # 0.40–0.70: store with label, human review suggested
                                       # Above 0.70: TRUSTED — stored and available for injection
