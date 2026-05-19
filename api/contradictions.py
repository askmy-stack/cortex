"""Human review queue API for detected contradictions."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.deps import caller_roles, memory

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/contradictions", tags=["intelligence"])


class ContradictionItem(BaseModel):
    """Single contradiction pending human review."""

    id: str = Field(description="Contradiction node id")
    score: float
    explanation: str
    new_decision_id: str | None = None
    prior_decision_id: str | None = None
    status: str = "pending"


@router.get("/pending", response_model=list[ContradictionItem])
async def list_pending_contradictions(
    workspace_id: str = Query(..., description="Cortex workspace identifier"),
    x_cortex_roles: str | None = Header(default=None, alias="X-Cortex-Roles"),
) -> list[ContradictionItem]:
    """Return pending contradictions for human review.

    Uses the shared async Neo4j driver (see ``MemoryService``) — no per-request
    connection is opened. RBAC filtering is enforced inside the graph layer.
    """
    roles = caller_roles(x_cortex_roles)
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
