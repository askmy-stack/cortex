"""GET /memory/state — current or historical claim state for an entity."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from api.deps import RolesDep
from temporal.state import TemporalStateService

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryStateResponse(BaseModel):
    entity: str
    workspace_id: str
    at: str
    mode: str
    claims: list[dict[str, Any]] = Field(default_factory=list)
    total: int


@router.get(
    "/state",
    response_model=MemoryStateResponse,
    summary="Current or historical memory state for an entity",
)
def memory_state(
    _roles: RolesDep,
    entity: str = Query(..., min_length=1),
    workspace_id: str = Query(...),
    at: datetime | None = Query(
        default=None,
        description="UTC timestamp for historical state; default now",
    ),
    current_only: bool = Query(
        default=True,
        description="If true, prefer active valid claims only",
    ),
) -> MemoryStateResponse:
    """Return temporally filtered claims about an entity."""
    when = at or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    svc = TemporalStateService()
    try:
        payload = svc.state_at(
            entity=entity,
            workspace_id=workspace_id,
            at=when,
            current_only=current_only,
        )
    finally:
        svc.close()
    return MemoryStateResponse(**payload)
