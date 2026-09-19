"""POST /reliability/evaluate — Memory Reliability Gate API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.deps import RolesDep
from reliability.gate import ReliabilityGate
from shared.v2_models import ActionRisk, ReliabilityVerdict

router = APIRouter(prefix="/reliability", tags=["reliability"])


class EvaluateRequest(BaseModel):
    workspace_id: str
    query: str = Field(min_length=3, max_length=2000)
    candidate_action: dict[str, Any] = Field(default_factory=dict)
    memory_ids: list[str] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    memories: list[dict[str, Any]] = Field(default_factory=list)
    risk: ActionRisk | None = None


class EvaluateResponse(BaseModel):
    decision: ReliabilityVerdict
    memory_confidence: float
    action_confidence: float
    risk: ActionRisk
    reason_codes: list[str]
    required_checks: list[str]
    id: str


@router.post(
    "/evaluate",
    response_model=EvaluateResponse,
    summary="Evaluate whether memory is reliable enough for an agent action",
)
def evaluate_reliability(body: EvaluateRequest, roles: RolesDep) -> EvaluateResponse:
    """Run the Memory Reliability Gate."""
    gate = ReliabilityGate()
    result = gate.evaluate(
        workspace_id=body.workspace_id,
        query=body.query,
        candidate_action=body.candidate_action,
        claims=body.claims,
        memories=body.memories,
        caller_roles=roles,
        risk=body.risk,
    )
    return EvaluateResponse(
        decision=result.decision,
        memory_confidence=result.memory_confidence,
        action_confidence=result.action_confidence,
        risk=result.risk,
        reason_codes=result.reason_codes,
        required_checks=result.required_checks,
        id=result.id,
    )
