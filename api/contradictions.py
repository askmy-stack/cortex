"""Human review queue API for detected contradictions."""

from __future__ import annotations

import os
from typing import Any

import structlog
from fastapi import APIRouter, Header, Query
from neo4j import GraphDatabase
from pydantic import BaseModel, Field

from graph.rbac import can_access, normalize_access_policy

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


def _caller_roles(x_cortex_roles: str | None) -> list[str]:
    if not x_cortex_roles:
        return ["authenticated"]
    return [role.strip() for role in x_cortex_roles.split(",") if role.strip()]


@router.get("/pending", response_model=list[ContradictionItem])
def list_pending_contradictions(
    workspace_id: str = Query(..., description="Cortex workspace identifier"),
    x_cortex_roles: str | None = Header(default=None, alias="X-Cortex-Roles"),
) -> list[ContradictionItem]:
    """Return pending contradictions for human review."""
    roles = _caller_roles(x_cortex_roles)
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "cortex_local")
    driver = GraphDatabase.driver(uri, auth=(user, password))

    cypher = """
    MATCH (c:Contradiction {workspace_id: $workspace_id, status: 'pending'})
    OPTIONAL MATCH (c)-[:INVOLVES_NEW]->(n:Decision)
    OPTIONAL MATCH (c)-[:INVOLVES_PRIOR]->(p:Decision)
    RETURN c.id AS id,
           c.score AS score,
           c.explanation AS explanation,
           c.access_policy AS access_policy,
           n.id AS new_id,
           p.id AS prior_id,
           c.status AS status
    ORDER BY c.score DESC
    """

    items: list[ContradictionItem] = []
    try:
        with driver.session() as session:
            for record in session.run(cypher, workspace_id=workspace_id):
                policy = normalize_access_policy(record.get("access_policy"))
                if not can_access(policy, roles):
                    continue
                items.append(
                    ContradictionItem(
                        id=str(record["id"]),
                        score=float(record["score"] or 0.0),
                        explanation=str(record["explanation"] or ""),
                        new_decision_id=record.get("new_id"),
                        prior_decision_id=record.get("prior_id"),
                        status=str(record.get("status") or "pending"),
                    )
                )
    finally:
        driver.close()

    log.info("contradictions.pending.list", workspace_id=workspace_id, count=len(items))
    return items
