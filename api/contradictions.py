"""Human review queue API for detected contradictions."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.deps import RolesDep, memory

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/contradictions", tags=["intelligence"])

_ALLOWED_RESOLUTIONS = frozenset({"acknowledged", "dismissed"})


class ContradictionItem(BaseModel):
    """Single contradiction pending human review."""

    id: str = Field(description="Contradiction node id")
    score: float
    explanation: str
    new_decision_id: str | None = None
    prior_decision_id: str | None = None
    status: str = "pending"


class ContradictionResolveResponse(BaseModel):
    """Result of marking a contradiction reviewed."""

    id: str
    status: str


@router.get("/pending", response_model=list[ContradictionItem])
async def list_pending_contradictions(
    roles: RolesDep,
    workspace_id: str = Query(..., description="Cortex workspace identifier"),
) -> list[ContradictionItem]:
    """Return pending contradictions for human review.

    Uses the shared async Neo4j driver (see ``MemoryService``) — no per-request
    connection is opened. RBAC filtering is enforced inside the graph layer.
    """
    try:
        rows = await memory().pending_contradictions(
            workspace_id=workspace_id,
            caller_roles=roles,
        )
    except Exception as exc:
        log.error("contradictions.pending.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Contradiction queue unavailable",
        ) from exc

    items = [ContradictionItem(**row) for row in rows]
    log.info(
        "contradictions.pending.list",
        workspace_id=workspace_id,
        count=len(items),
    )
    return items


@router.post(
    "/{contradiction_id}/resolve",
    response_model=ContradictionResolveResponse,
    summary="Resolve a pending contradiction",
)
async def resolve_contradiction(
    contradiction_id: str,
    roles: RolesDep,
    workspace_id: str = Query(..., description="Cortex workspace identifier"),
    resolution: str = Query(
        "acknowledged",
        description="Review outcome: acknowledged (keep both) or dismissed (no action)",
    ),
) -> ContradictionResolveResponse:
    """Mark a contradiction as reviewed so it leaves the pending queue."""
    if resolution not in _ALLOWED_RESOLUTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"resolution must be one of: {', '.join(sorted(_ALLOWED_RESOLUTIONS))}",
        )
    try:
        result = await memory().resolve_contradiction(
            contradiction_id=contradiction_id,
            workspace_id=workspace_id,
            resolution=resolution,
            caller_roles=roles,
        )
    except Exception as exc:
        log.error("contradictions.resolve.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not resolve contradiction",
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contradiction not found or not accessible",
        )

    log.info(
        "contradictions.resolve",
        contradiction_id=contradiction_id,
        workspace_id=workspace_id,
        resolution=resolution,
    )
    return ContradictionResolveResponse(**result)
