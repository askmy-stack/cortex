"""POST /outcomes/record — append action ledger entry."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.deps import RolesDep
from outcomes.ledger import ActionLedgerEntry, record_outcome, update_usefulness

router = APIRouter(prefix="/outcomes", tags=["outcomes"])


class RecordOutcomeRequest(BaseModel):
    workspace_id: str
    agent_id: str
    task: str
    memory_ids: list[str] = Field(default_factory=list)
    reliability_decision: str | None = None
    action: dict[str, Any] = Field(default_factory=dict)
    outcome: str = "unknown"
    metrics: dict[str, Any] = Field(default_factory=dict)
    prior_usefulness: float = Field(default=0.5, ge=0.0, le=1.0)
    trace_id: str | None = None


class RecordOutcomeResponse(BaseModel):
    id: str
    usefulness_score: float


@router.post("/record", response_model=RecordOutcomeResponse)
def post_record_outcome(body: RecordOutcomeRequest, _roles: RolesDep) -> RecordOutcomeResponse:
    entry = ActionLedgerEntry(
        workspace_id=body.workspace_id,
        agent_id=body.agent_id,
        task=body.task,
        memory_ids=body.memory_ids,
        reliability_decision=body.reliability_decision,
        action=body.action,
        outcome=body.outcome,  # type: ignore[arg-type]
        metrics=body.metrics,
        trace_id=body.trace_id,
    )
    record_outcome(entry)
    success = body.outcome == "success"
    usefulness = update_usefulness(
        prior_usefulness=body.prior_usefulness,
        success=success,
    )
    return RecordOutcomeResponse(id=entry.id, usefulness_score=usefulness)
