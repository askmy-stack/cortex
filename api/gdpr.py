"""GDPR Right to Erasure API — admin-only cascade delete."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import RolesDep, memory
from graph.rbac import can_erase

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/gdpr", tags=["compliance"])


class GdprEraseRequest(BaseModel):
    """Request body for GDPR subject erasure."""

    workspace_id: str = Field(description="Cortex workspace identifier")
    person_id: str = Field(
        description="Canonical person id (email or username) to erase",
        min_length=1,
    )
    requested_by: str = Field(
        description="DID or user id initiating the erasure request",
        min_length=1,
    )
    reason: str = Field(
        default="gdpr_right_to_erasure",
        description="Human-readable reason stored on the audit log node",
    )


class GdprEraseResponse(BaseModel):
    """Outcome of a successful GDPR cascade delete."""

    audit_id: str
    workspace_id: str
    person_id: str
    decisions_deleted: int
    requested_by: str


@router.post(
    "/erase",
    response_model=GdprEraseResponse,
    summary="Erase a data subject and linked memory (GDPR)",
)
async def erase_gdpr_subject(
    request: GdprEraseRequest,
    roles: RolesDep,
) -> GdprEraseResponse:
    """Cascade-delete all memory for a data subject with audit logging.

    Requires ``admin``, ``gdpr_officer``, or ``legal`` role (see ``graph.rbac``).
    Deletes linked Decision, Rationale, and Contradiction nodes, then the Person
    node. Writes a ``GdprAuditLog`` entry for compliance traceability.
    """
    if not can_erase(roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="GDPR erasure requires admin, gdpr_officer, or legal role",
        )

    try:
        result = await memory().erase_gdpr_subject(
            workspace_id=request.workspace_id,
            person_id=request.person_id,
            requested_by=request.requested_by,
            caller_roles=roles,
            reason=request.reason,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        log.error("gdpr.erase.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GDPR erasure failed — Neo4j may be unavailable",
        ) from exc

    log.info(
        "gdpr.erase.complete",
        workspace_id=request.workspace_id,
        person_id=request.person_id,
        audit_id=result["audit_id"],
        decisions_deleted=result["decisions_deleted"],
    )
    return GdprEraseResponse(**result)
