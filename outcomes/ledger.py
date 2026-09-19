"""Outcome ledger and usefulness updates (V2 Enhancement 5)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

OutcomeResult = Literal["success", "failure", "partial", "unknown"]


def _uuid4() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ActionLedgerEntry(BaseModel):
    """Append-oriented audit of agent action + memory used."""

    id: str = Field(default_factory=_uuid4)
    workspace_id: str
    agent_id: str
    task: str
    memory_ids: list[str] = Field(default_factory=list)
    reliability_decision: str | None = None
    action: dict[str, Any] = Field(default_factory=dict)
    outcome: OutcomeResult = "unknown"
    metrics: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class OutcomeRecord(BaseModel):
    """Outcome linked to a decision or procedure."""

    id: str = Field(default_factory=_uuid4)
    workspace_id: str
    action_id: str | None = None
    procedure_id: str | None = None
    decision_id: str | None = None
    result: OutcomeResult
    success: bool
    metrics: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=_utcnow)
    evidence_ids: list[str] = Field(default_factory=list)


def update_usefulness(
    *,
    prior_usefulness: float,
    success: bool,
    learning_rate: float = 0.1,
) -> float:
    """Update usefulness score without erasing history (bounded EMA)."""
    target = 1.0 if success else 0.0
    value = prior_usefulness + learning_rate * (target - prior_usefulness)
    return max(0.0, min(1.0, round(value, 4)))


_LEDGER: list[ActionLedgerEntry] = []


def record_outcome(entry: ActionLedgerEntry) -> ActionLedgerEntry:
    """Append to in-memory ledger (Neo4j writer can replace later)."""
    _LEDGER.append(entry)
    return entry


def ledger_for_workspace(workspace_id: str) -> list[ActionLedgerEntry]:
    return [e for e in _LEDGER if e.workspace_id == workspace_id]
