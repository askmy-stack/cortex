"""Gaps and abstention API."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from api.deps import RolesDep
from gaps.detector import coverage_score, get_gaps, maybe_abstain, record_gap

router = APIRouter(prefix="/gaps", tags=["gaps"])


class AbstainRequest(BaseModel):
    workspace_id: str
    domain: str
    memory_confidence: float = Field(ge=0.0, le=1.0)
    claim_count: int = Field(default=0, ge=0)
    missing: list[str] = Field(default_factory=list)


@router.post("/abstain")
def post_abstain(body: AbstainRequest, _roles: RolesDep) -> dict:
    cov = coverage_score(claim_count=body.claim_count)
    abstain = maybe_abstain(
        memory_confidence=body.memory_confidence,
        coverage=cov,
        missing=body.missing,
    )
    if abstain:
        record_gap(
            workspace_id=body.workspace_id,
            domain=body.domain,
            gap_type="MISSING_KNOWLEDGE",
            description=f"Abstention on {body.domain}",
            coverage=cov,
        )
    return {
        "coverage_score": cov,
        "abstention": abstain,
    }


@router.get("")
def list_gaps(
    _roles: RolesDep,
    workspace_id: str = Query(...),
) -> dict:
    gaps = [g.model_dump(mode="json") for g in get_gaps(workspace_id)]
    return {"workspace_id": workspace_id, "gaps": gaps, "total": len(gaps)}
