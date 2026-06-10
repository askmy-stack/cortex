"""Decision graph read routes — system lookup, causal chain, conflicts."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from api.deps import RolesDep, memory
from api.schemas import DecisionResult

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/decisions", tags=["decisions"])


class CausalChainResponse(BaseModel):
    decision_id: str
    workspace_id: str
    nodes: list[DecisionResult]
    total: int


class ConflictPreviewResponse(BaseModel):
    decision_id: str
    workspace_id: str
    candidates: list[DecisionResult]
    total: int


@router.get(
    "/by-system/{system_id}",
    response_model=list[DecisionResult],
    summary="Decisions affecting a system",
)
async def decisions_by_system(
    system_id: str,
    roles: RolesDep,
    workspace_id: str = Query(description="Workspace scope"),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[DecisionResult]:
    """Return the most recent decisions that affect a system (id or name)."""
    try:
        records = await memory().decisions_by_system(
            system_id=system_id,
            workspace_id=workspace_id,
            limit=limit,
            caller_roles=roles,
        )
    except Exception as exc:
        log.error("decisions.by_system.failed", system_id=system_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph query failed",
        ) from exc
    return [DecisionResult(**record) for record in records]


@router.get(
    "/{decision_id}/chain",
    response_model=CausalChainResponse,
    summary="Trace supersession and trigger lineage",
)
async def decision_causal_chain(
    decision_id: str,
    roles: RolesDep,
    workspace_id: str = Query(),
    max_depth: int = Query(default=4, ge=1, le=8),
) -> CausalChainResponse:
    """Return decisions linked via SUPERSEDES and triggered_by."""
    try:
        records = await memory().causal_chain(
            decision_id=decision_id,
            workspace_id=workspace_id,
            max_depth=max_depth,
            caller_roles=roles,
        )
    except Exception as exc:
        log.error("decisions.chain.failed", decision_id=decision_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph query failed",
        ) from exc
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found or not accessible",
        )
    nodes = [
        DecisionResult(**{k: v for k, v in record.items() if k in DecisionResult.model_fields})
        for record in records
    ]
    return CausalChainResponse(
        decision_id=decision_id,
        workspace_id=workspace_id,
        nodes=nodes,
        total=len(nodes),
    )


@router.get(
    "/{decision_id}/conflicts",
    response_model=ConflictPreviewResponse,
    summary="Preview potential contradictions",
)
async def decision_conflicts(
    decision_id: str,
    roles: RolesDep,
    workspace_id: str = Query(),
    limit: int = Query(default=5, ge=1, le=20),
) -> ConflictPreviewResponse:
    """Return other active decisions on shared systems (pre-write check)."""
    try:
        records = await memory().conflict_candidates(
            decision_id=decision_id,
            workspace_id=workspace_id,
            limit=limit,
            caller_roles=roles,
        )
    except Exception as exc:
        log.error("decisions.conflicts.failed", decision_id=decision_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph query failed",
        ) from exc
    candidates = [
        DecisionResult(**{k: v for k, v in record.items() if k in DecisionResult.model_fields})
        for record in records
    ]
    return ConflictPreviewResponse(
        decision_id=decision_id,
        workspace_id=workspace_id,
        candidates=candidates,
        total=len(candidates),
    )
