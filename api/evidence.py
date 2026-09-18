"""Evidence Graph HTTP routes — explain Claim confidence."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import RolesDep
from evidence.explain import EvidenceExplainer

router = APIRouter(prefix="/evidence", tags=["evidence"])


class ExplainResponse(BaseModel):
    claim: str
    claim_id: str
    confidence: float | None = None
    status: str | None = None
    assertion_type: str | None = None
    temporal: dict[str, Any] = Field(default_factory=dict)
    supporting_evidence: list[dict[str, Any]] = Field(default_factory=list)
    conflicting_evidence: list[dict[str, Any]] = Field(default_factory=list)


@router.get(
    "/explain/{claim_id}",
    response_model=ExplainResponse,
    summary="Explain a claim via supporting and conflicting evidence",
)
def explain_claim(
    claim_id: str,
    workspace_id: str,
    _roles: RolesDep,
) -> ExplainResponse:
    """Return evidence-backed explanation for a Claim node."""
    explainer = EvidenceExplainer()
    try:
        payload = explainer.explain(claim_id=claim_id, workspace_id=workspace_id)
    finally:
        explainer.close()
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim {claim_id} not found in workspace {workspace_id}",
        )
    return ExplainResponse(**payload)
