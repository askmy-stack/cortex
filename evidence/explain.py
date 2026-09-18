"""Explain Claim confidence via supporting / conflicting evidence."""

from __future__ import annotations

import os
from typing import Any

import structlog
from neo4j import Driver, GraphDatabase

log = structlog.get_logger(__name__)

_EXPLAIN_CYPHER = """
MATCH (c:Claim {id: $claim_id})
WHERE c.workspace_id = $workspace_id
OPTIONAL MATCH (s:Evidence)-[:SUPPORTS]->(c)
OPTIONAL MATCH (x:Evidence)-[:CONTRADICTS]->(c)
RETURN c {
  .id, .workspace_id, .subject, .predicate, .object, .content,
  .confidence, .status, .assertion_type, .decision_id,
  .valid_from, .valid_to, .observed_at
} AS claim,
collect(DISTINCT s {
  .id, .source_type, .source_id, .authority_class, .authority_score,
  .snippet, .integrity_state
}) AS supporting,
collect(DISTINCT x {
  .id, .source_type, .source_id, .authority_class, .authority_score,
  .snippet, .integrity_state
}) AS conflicting
"""


class EvidenceExplainer:
    """Assemble explainability payload for a Claim."""

    def __init__(self, driver: Driver | None = None) -> None:
        self._owns_driver = driver is None
        if driver is None:
            uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
            user = os.environ.get("NEO4J_USER", "neo4j")
            password = os.environ.get("NEO4J_PASSWORD", "cortex_local")
            self._driver = GraphDatabase.driver(uri, auth=(user, password))
        else:
            self._driver = driver

    def explain(self, *, claim_id: str, workspace_id: str) -> dict[str, Any] | None:
        """Return claim + evidence breakdown or None if missing."""
        with self._driver.session() as session:
            record = session.run(
                _EXPLAIN_CYPHER,
                claim_id=claim_id,
                workspace_id=workspace_id,
            ).single()
        if record is None or record["claim"] is None:
            return None
        supporting = [e for e in (record["supporting"] or []) if e and e.get("id")]
        conflicting = [e for e in (record["conflicting"] or []) if e and e.get("id")]
        claim = dict(record["claim"])
        return {
            "claim": claim.get("content") or self._claim_text(claim),
            "claim_id": claim.get("id"),
            "confidence": claim.get("confidence"),
            "status": claim.get("status"),
            "assertion_type": claim.get("assertion_type"),
            "temporal": {
                "valid_from": claim.get("valid_from"),
                "valid_to": claim.get("valid_to"),
                "observed_at": claim.get("observed_at"),
            },
            "supporting_evidence": supporting,
            "conflicting_evidence": conflicting,
        }

    @staticmethod
    def _claim_text(claim: dict[str, Any]) -> str:
        return f"{claim.get('subject')} {claim.get('predicate')} {claim.get('object')}"

    def close(self) -> None:
        if self._owns_driver:
            self._driver.close()
