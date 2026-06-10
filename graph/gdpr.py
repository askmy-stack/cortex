"""GDPR Right to Erasure — cascade delete with audit log.

Architecture: Phase 4 — graph-level RBAC (D-008) + thermodynamic lifecycle (D-007).
Deletes all Decision/Rationale/Contradiction nodes linked to a data subject,
then removes the Person node. Every erasure is recorded as a GdprAuditLog node.

Requires V009__rbac_enforcement.cypher (GdprAuditLog schema).
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any

import structlog
from neo4j import Driver, GraphDatabase

from graph.rbac import can_erase

log = structlog.get_logger(__name__)

_COLLECT_SUBJECT = """
MATCH (p:Person {id: $person_id, workspace_id: $workspace_id})
OPTIONAL MATCH (p)-[:MADE]->(d:Decision)
RETURN collect(DISTINCT d.id) AS decision_ids
"""

_DELETE_RATIONALES = """
UNWIND $decision_ids AS decision_id
MATCH (d:Decision {id: decision_id, workspace_id: $workspace_id})-[:HAS_RATIONALE]->(r:Rationale)
DETACH DELETE r
"""

_DELETE_CONTRADICTIONS = """
UNWIND $decision_ids AS decision_id
MATCH (c:Contradiction {workspace_id: $workspace_id})-[:INVOLVES_NEW|INVOLVES_PRIOR]->(d:Decision {id: decision_id})
DETACH DELETE c
"""

_DELETE_DECISIONS = """
UNWIND $decision_ids AS decision_id
MATCH (d:Decision {id: decision_id, workspace_id: $workspace_id})
DETACH DELETE d
"""

_DELETE_PERSON = """
MATCH (p:Person {id: $person_id, workspace_id: $workspace_id})
DETACH DELETE p
RETURN count(p) AS deleted
"""

_CREATE_AUDIT = """
CREATE (a:GdprAuditLog {
    id: $audit_id,
    workspace_id: $workspace_id,
    subject_id: $person_id,
    requested_by: $requested_by,
    reason: $reason,
    decisions_deleted: $decisions_deleted,
    deleted_at: datetime()
})
RETURN a.id AS id
"""


@dataclass(frozen=True)
class GdprErasureResult:
    """Outcome of a GDPR cascade delete."""

    audit_id: str
    workspace_id: str
    person_id: str
    decisions_deleted: int
    requested_by: str


class GdprErasureService:
    """Cascade-delete a data subject and linked memory nodes."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self._uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self._user = user or os.environ.get("NEO4J_USER", "neo4j")
        self._password = password or os.environ.get("NEO4J_PASSWORD", "cortex_local")
        self._driver: Driver = GraphDatabase.driver(
            self._uri,
            auth=(self._user, self._password),
        )
        log.info("graph.gdpr.initialized", uri=self._uri)

    def erase_subject(
        self,
        *,
        workspace_id: str,
        person_id: str,
        requested_by: str,
        caller_roles: list[str],
        reason: str = "gdpr_right_to_erasure",
    ) -> GdprErasureResult:
        """Delete all memory for a data subject and write an audit log entry.

        Args:
            workspace_id: Org scope for the erasure.
            person_id: Canonical person id (email or username).
            requested_by: DID or user id initiating the request.
            caller_roles: Roles of the caller — must include admin/gdpr_officer/legal.
            reason: Human-readable reason stored on the audit node.

        Returns:
            GdprErasureResult with counts and audit id.

        Raises:
            PermissionError: When caller lacks erasure privileges.
            ValueError: When the person node does not exist in the workspace.
        """
        if not can_erase(caller_roles):
            raise PermissionError(
                "GDPR erasure requires admin, gdpr_officer, or legal role."
            )

        audit_id = str(uuid.uuid4())

        with self._driver.session() as session:
            result = session.execute_write(
                self._erase_transaction,
                workspace_id=workspace_id,
                person_id=person_id,
                requested_by=requested_by,
                reason=reason,
                audit_id=audit_id,
            )

        log.info(
            "graph.gdpr.erased",
            workspace_id=workspace_id,
            person_id=person_id,
            decisions_deleted=result.decisions_deleted,
            audit_id=result.audit_id,
            requested_by=requested_by,
        )
        return result

    def close(self) -> None:
        """Close the Neo4j driver."""
        self._driver.close()

    @staticmethod
    def _erase_transaction(
        tx: Any,
        *,
        workspace_id: str,
        person_id: str,
        requested_by: str,
        reason: str,
        audit_id: str,
    ) -> GdprErasureResult:
        """Run cascade delete atomically inside one write transaction."""
        collect = tx.run(
            _COLLECT_SUBJECT,
            person_id=person_id,
            workspace_id=workspace_id,
        ).single()
        if collect is None:
            raise ValueError(
                f"Person {person_id!r} not found in workspace {workspace_id!r}."
            )

        decision_ids: list[str] = [
            str(item) for item in (collect["decision_ids"] or []) if item
        ]

        if decision_ids:
            tx.run(
                _DELETE_RATIONALES,
                decision_ids=decision_ids,
                workspace_id=workspace_id,
            )
            tx.run(
                _DELETE_CONTRADICTIONS,
                decision_ids=decision_ids,
                workspace_id=workspace_id,
            )
            tx.run(
                _DELETE_DECISIONS,
                decision_ids=decision_ids,
                workspace_id=workspace_id,
            )

        deleted = tx.run(
            _DELETE_PERSON,
            person_id=person_id,
            workspace_id=workspace_id,
        ).single()
        if not deleted or deleted["deleted"] == 0:
            raise ValueError(
                f"Person {person_id!r} not found in workspace {workspace_id!r}."
            )

        tx.run(
            _CREATE_AUDIT,
            audit_id=audit_id,
            workspace_id=workspace_id,
            person_id=person_id,
            requested_by=requested_by,
            reason=reason,
            decisions_deleted=len(decision_ids),
        )

        return GdprErasureResult(
            audit_id=audit_id,
            workspace_id=workspace_id,
            person_id=person_id,
            decisions_deleted=len(decision_ids),
            requested_by=requested_by,
        )
