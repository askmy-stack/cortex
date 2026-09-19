"""Procedural memory models and environment compatibility."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ProcedureStatus = Literal["ACTIVE", "STALE", "DEPRECATED", "DRAFT"]
RecallValidity = Literal[
    "VALID", "PARTIALLY_VALID", "STALE", "INCOMPATIBLE", "UNKNOWN"
]


def _uuid4() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Procedure(BaseModel):
    """Versioned how-to memory for agent tasks."""

    id: str = Field(default_factory=_uuid4)
    workspace_id: str
    name: str
    goal: str
    version: int = 1
    status: ProcedureStatus = "ACTIVE"
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)
    rollback: list[str] = Field(default_factory=list)
    environment_constraints: dict[str, str] = Field(default_factory=dict)
    success_count: int = 0
    failure_count: int = 0
    last_verified_at: datetime | None = None
    created_from_trace: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


def check_environment(
    procedure: Procedure,
    current_env: dict[str, str],
) -> RecallValidity:
    """Compare procedure constraints to current environment."""
    if procedure.status == "STALE":
        return "STALE"
    if procedure.status == "DEPRECATED":
        return "INCOMPATIBLE"
    constraints = procedure.environment_constraints or {}
    if not constraints:
        return "UNKNOWN" if not current_env else "VALID"
    mismatches = 0
    for key, expected in constraints.items():
        actual = current_env.get(key)
        if actual is None:
            mismatches += 1
            continue
        # Simple equality / prefix match for versions like ">=1.31"
        if expected.startswith(">="):
            continue  # treat as soft constraint for MVP
        if actual != expected and expected not in actual:
            mismatches += 1
    if mismatches == 0:
        return "VALID"
    if mismatches < len(constraints):
        return "PARTIALLY_VALID"
    return "INCOMPATIBLE"


def recall_procedure(
    procedures: list[Procedure],
    *,
    goal: str,
    current_env: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Pick best matching procedure for a goal."""
    current_env = current_env or {}
    candidates = [p for p in procedures if goal.lower() in p.goal.lower() or goal.lower() in p.name.lower()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: (p.success_count - p.failure_count, p.version), reverse=True)
    best = candidates[0]
    validity = check_environment(best, current_env)
    return {
        "procedure": best.model_dump(mode="json"),
        "validity": validity,
    }
