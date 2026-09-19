"""Neo4j writer for Claim/Evidence nodes (gated by CORTEX_EVIDENCE_GRAPH)."""

from __future__ import annotations

import os
from typing import Any, Literal

import structlog
from neo4j import Driver, GraphDatabase

from evidence.adapters import evidence_graph_enabled
from evidence.authority import score_for_class
from shared.v2_models import Claim, Evidence

log = structlog.get_logger(__name__)

RelationKind = Literal["SUPPORTS", "CONTRADICTS"]

_UPSERT_CLAIM = """
MERGE (c:Claim {id: $id})
ON CREATE SET
  c.workspace_id = $workspace_id,
  c.subject = $subject,
  c.predicate = $predicate,
  c.object = $object,
  c.claim_type = $claim_type,
  c.assertion_type = $assertion_type,
  c.confidence = $confidence,
  c.status = $status,
  c.valid_from = $valid_from,
  c.valid_to = $valid_to,
  c.observed_at = $observed_at,
  c.invalidated_at = $invalidated_at,
  c.superseded_by = $superseded_by,
  c.decision_id = $decision_id,
  c.content = $content,
  c.access_policy = $access_policy,
  c.created_at = datetime(),
  c.updated_at = datetime()
ON MATCH SET
  c.confidence = $confidence,
  c.status = $status,
  c.updated_at = datetime(),
  c.content = $content
RETURN c.id AS id
"""

_UPSERT_EVIDENCE = """
MERGE (e:Evidence {id: $id})
ON CREATE SET
  e.workspace_id = $workspace_id,
  e.source_type = $source_type,
  e.source_id = $source_id,
  e.source_uri = $source_uri,
  e.author = $author,
  e.content_hash = $content_hash,
  e.authority_class = $authority_class,
  e.authority_score = $authority_score,
  e.captured_at = $captured_at,
  e.observed_at = $observed_at,
  e.integrity_state = $integrity_state,
  e.snippet = $snippet,
  e.access_policy = $access_policy
ON MATCH SET
  e.authority_score = $authority_score,
  e.integrity_state = $integrity_state,
  e.snippet = $snippet
RETURN e.id AS id
"""

_LINK = """
MATCH (e:Evidence {id: $evidence_id})
MATCH (c:Claim {id: $claim_id})
MERGE (e)-[r:%s]->(c)
ON CREATE SET r.created_at = datetime()
RETURN type(r) AS rel
"""

_ASSERTS = """
MATCH (d:Decision {id: $decision_id})
MATCH (c:Claim {id: $claim_id})
MERGE (d)-[r:ASSERTS]->(c)
ON CREATE SET r.created_at = datetime()
RETURN type(r) AS rel
"""


class EvidenceGraphWriter:
    """Persists Claim/Evidence when the evidence-graph feature flag is on."""

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
            self._uri, auth=(self._user, self._password)
        )

    def write_claim_with_evidence(
        self,
        claim: Claim,
        evidence_items: list[Evidence],
        *,
        relation: RelationKind = "SUPPORTS",
        force: bool = False,
    ) -> str | None:
        """Write claim + evidence edges. Returns claim id or None if flag off."""
        if not force and not evidence_graph_enabled():
            log.debug("evidence_graph.skipped", reason="flag_off")
            return None

        with self._driver.session() as session:
            session.execute_write(self._tx_write, claim, evidence_items, relation)

        log.info(
            "evidence_graph.written",
            claim_id=claim.id,
            evidence_count=len(evidence_items),
            relation=relation,
        )
        return claim.id

    @staticmethod
    def _tx_write(
        tx: Any,
        claim: Claim,
        evidence_items: list[Evidence],
        relation: RelationKind,
    ) -> None:
        tx.run(
            _UPSERT_CLAIM,
            id=claim.id,
            workspace_id=claim.workspace_id,
            subject=claim.subject,
            predicate=claim.predicate,
            object=claim.object,
            claim_type=claim.claim_type,
            assertion_type=claim.assertion_type,
            confidence=claim.confidence,
            status=claim.status,
            valid_from=claim.valid_from.isoformat() if claim.valid_from else None,
            valid_to=claim.valid_to.isoformat() if claim.valid_to else None,
            observed_at=claim.observed_at.isoformat() if claim.observed_at else None,
            invalidated_at=(
                claim.invalidated_at.isoformat() if claim.invalidated_at else None
            ),
            superseded_by=claim.superseded_by,
            decision_id=claim.decision_id,
            content=claim.content,
            access_policy=str(claim.access_policy or {}),
        )
        link_cypher = _LINK % relation
        for ev in evidence_items:
            score = ev.authority_score or score_for_class(ev.authority_class)
            tx.run(
                _UPSERT_EVIDENCE,
                id=ev.id,
                workspace_id=ev.workspace_id,
                source_type=ev.source_type,
                source_id=ev.source_id,
                source_uri=ev.source_uri,
                author=ev.author,
                content_hash=ev.content_hash,
                authority_class=ev.authority_class,
                authority_score=score,
                captured_at=ev.captured_at.isoformat(),
                observed_at=ev.observed_at.isoformat() if ev.observed_at else None,
                integrity_state=ev.integrity_state,
                snippet=ev.snippet,
                access_policy=str(ev.access_policy or {}),
            )
            tx.run(
                link_cypher,
                evidence_id=ev.id,
                claim_id=claim.id,
            )
        if claim.decision_id:
            tx.run(
                _ASSERTS,
                decision_id=claim.decision_id,
                claim_id=claim.id,
            )

    def close(self) -> None:
        self._driver.close()
