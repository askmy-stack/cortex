"""Neo4j graph writer — persists DecisionEvents as structured knowledge graph nodes.

Architecture: Layer 3 — Memory Fabric (structural/procedural store).
Decision: D-002 — Neo4j as source of truth for relationships.
Decision: D-008 — RBAC enforced at graph query level (access_policy on every node).

Write pipeline (enforced by this module):
  DecisionEvent → importance scored → trust scored → GraphWriter.write()

RBAC:
  Every node carries access_policy: {roles, deny, classification, gdpr_subject}
  Query helpers filter by roles at read time — never at write time.
  See graph/query.py for read-path RBAC enforcement.

Idempotency:
  MERGE on event_id — safe to replay Kafka messages.
  Duplicate writes update scores and status only — never duplicate nodes.
"""

from __future__ import annotations

import os
from typing import Any

import structlog
from neo4j import Driver, GraphDatabase

from graph.rbac import serialize_access_policy
from scoring.trust_scorer import is_writable
from shared.models import IMPORTANCE_DISCARD, DecisionEvent

log = structlog.get_logger(__name__)

_DEFAULT_ACCESS_POLICY: dict[str, Any] = {
    "roles": ["authenticated"],
    "deny": [],
    "classification": "internal",
    "gdpr_subject": False,
}


# ─────────────────────────────────────────────────────────────────────────────
# Cypher queries
# ─────────────────────────────────────────────────────────────────────────────

_UPSERT_DECISION = """
MERGE (d:Decision {id: $event_id})
ON CREATE SET
    d.workspace_id          = $workspace_id,
    d.event_type            = $event_type,
    d.content               = $content,
    d.status                = $status,
    d.extraction_confidence = $extraction_confidence,
    d.importance_score      = $importance_score,
    d.trust_score           = $trust_score,
    d.source                = $source,
    d.channel               = $channel,
    d.raw_event_id          = $raw_event_id,
    d.extractor_version     = $extractor_version,
    d.extractor_model       = $extractor_model,
    d.replaces              = $replaces,
    d.triggered_by          = $triggered_by,
    d.extracted_at          = $extracted_at,
    d.valid_at              = $valid_at,
    d.invalid_at            = null,
    d.access_policy         = $access_policy
ON MATCH SET
    d.importance_score      = $importance_score,
    d.trust_score           = $trust_score,
    d.status                = $status
RETURN d.id AS id, (count(*) > 0) AS written
"""

_UPSERT_PERSON = """
MERGE (p:Person {id: $person_id, workspace_id: $workspace_id})
ON CREATE SET
    p.display_name  = $person_id,
    p.access_policy = $access_policy
RETURN p.id AS id
"""

_LINK_MADE_BY = """
MATCH (d:Decision {id: $decision_id})
MATCH (p:Person {id: $person_id, workspace_id: $workspace_id})
MERGE (p)-[r:MADE]->(d)
ON CREATE SET r.valid_at = $valid_at, r.invalid_at = null
RETURN r
"""

_UPSERT_SYSTEM = """
MERGE (s:System {id: $system_id, workspace_id: $workspace_id})
ON CREATE SET
    s.name          = $system_id,
    s.access_policy = $access_policy
RETURN s.id AS id
"""

_LINK_AFFECTS = """
MATCH (d:Decision {id: $decision_id})
MATCH (s:System {id: $system_id, workspace_id: $workspace_id})
MERGE (d)-[r:AFFECTS]->(s)
ON CREATE SET r.valid_at = $valid_at, r.invalid_at = null
RETURN r
"""

_SUPERSEDE_PREVIOUS = """
MATCH (prev:Decision {id: $prev_id})
MATCH (next:Decision {id: $next_id})
SET prev.status     = 'superseded',
    prev.invalid_at = $invalid_at
MERGE (next)-[r:SUPERSEDES]->(prev)
ON CREATE SET r.valid_at = $valid_at
RETURN r
"""

_LINK_RATIONALE = """
MATCH (d:Decision {id: $decision_id})
MERGE (r:Rationale {id: $rationale_id, workspace_id: $workspace_id})
ON CREATE SET
    r.content       = $content,
    r.access_policy = $access_policy
MERGE (d)-[rel:HAS_RATIONALE]->(r)
ON CREATE SET rel.valid_at = $valid_at
RETURN r
"""


# ─────────────────────────────────────────────────────────────────────────────
# Graph writer
# ─────────────────────────────────────────────────────────────────────────────


class GraphWriter:
    """Writes DecisionEvents to Neo4j as a structured knowledge graph.

    Thread-safe. One instance per process. Uses connection pooling internally.

    Usage:
        writer = GraphWriter()
        writer.write(decision_event)
        writer.close()
    """

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialise the writer from env vars or explicit params.

        Args:
            uri: Bolt URI, e.g. 'bolt://localhost:7687'. Defaults to NEO4J_URI.
            user: Neo4j username. Defaults to NEO4J_USER.
            password: Neo4j password. Defaults to NEO4J_PASSWORD.
        """
        self._uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self._user = user or os.environ.get("NEO4J_USER", "neo4j")
        self._password = password or os.environ.get("NEO4J_PASSWORD", "cortex_local")
        self._driver: Driver = GraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )
        log.info("graph.writer.initialized", uri=self._uri, user=self._user)

    # ── Public API ────────────────────────────────────────────────────────────

    def write(
        self,
        decision: DecisionEvent,
        access_policy: dict[str, Any] | None = None,
    ) -> str:
        """Persist a DecisionEvent to the Neo4j graph.

        This is the single entry point for all graph writes. Performs:
          1. Discard if importance_score < IMPORTANCE_DISCARD (0.30)
          2. Upsert Decision node (MERGE on event_id — idempotent)
          3. Upsert Person nodes + MADE relationships
          4. Upsert System nodes + AFFECTS relationships
          5. Upsert Rationale nodes + HAS_RATIONALE relationships
          6. If decision.replaces is set — SUPERSEDES edge + invalidate previous

        Args:
            decision: Scored DecisionEvent (importance_score and trust_score must be set).
            access_policy: RBAC policy dict. Defaults to {roles: [authenticated]}.

        Returns:
            decision.event_id on success.

        Raises:
            ValueError: If importance_score is below discard threshold.
            Neo4jError: On graph write failure.
        """
        if decision.importance_score < IMPORTANCE_DISCARD:
            log.info(
                "graph.write.discarded",
                event_id=decision.event_id,
                importance_score=decision.importance_score,
                threshold=IMPORTANCE_DISCARD,
            )
            raise ValueError(
                f"importance_score {decision.importance_score:.3f} below discard threshold "
                f"{IMPORTANCE_DISCARD}. Do not write to graph."
            )

        if not is_writable(decision.trust_score):
            log.info(
                "graph.write.quarantined",
                event_id=decision.event_id,
                trust_score=decision.trust_score,
            )
            raise ValueError(
                f"trust_score {decision.trust_score:.3f} below quarantine threshold."
            )

        policy = access_policy or _DEFAULT_ACCESS_POLICY
        serialized_policy = serialize_access_policy(policy)
        valid_at = decision.extracted_at.isoformat()

        with self._driver.session() as session:
            session.execute_write(
                self._write_transaction,
                decision=decision,
                access_policy=serialized_policy,
                valid_at=valid_at,
            )

        log.info(
            "graph.write.success",
            event_id=decision.event_id,
            event_type=decision.event_type,
            workspace_id=decision.workspace_id,
            importance_score=decision.importance_score,
            trust_score=decision.trust_score,
            persons=len(decision.made_by),
            systems=len(decision.affects),
            rationale_count=len(decision.rationale),
        )
        return decision.event_id

    def close(self) -> None:
        """Close the Neo4j driver connection pool."""
        self._driver.close()
        log.info("graph.writer.closed")

    # ── Transaction ───────────────────────────────────────────────────────────

    @staticmethod
    def _write_transaction(
        tx: Any,
        decision: DecisionEvent,
        access_policy: str,
        valid_at: str,
    ) -> None:
        """Execute all graph writes inside a single Neo4j transaction.

        Atomic: either all nodes/edges are written or none are.
        """
        # 1. Upsert Decision node
        tx.run(
            _UPSERT_DECISION,
            event_id=decision.event_id,
            workspace_id=decision.workspace_id,
            event_type=decision.event_type,
            content=decision.content,
            status=decision.status,
            extraction_confidence=decision.extraction_confidence,
            importance_score=decision.importance_score,
            trust_score=decision.trust_score,
            source=decision.provenance.source,
            channel=decision.provenance.channel,
            raw_event_id=decision.provenance.raw_event_id,
            extractor_version=decision.provenance.extractor_version,
            extractor_model=decision.provenance.extractor_model,
            replaces=decision.replaces,
            triggered_by=decision.triggered_by,
            extracted_at=decision.extracted_at.isoformat(),
            valid_at=valid_at,
            access_policy=access_policy,
        )

        # 2. Person nodes + MADE edges
        for person_id in decision.made_by:
            tx.run(
                _UPSERT_PERSON,
                person_id=person_id,
                workspace_id=decision.workspace_id,
                access_policy=access_policy,
            )
            tx.run(
                _LINK_MADE_BY,
                decision_id=decision.event_id,
                person_id=person_id,
                workspace_id=decision.workspace_id,
                valid_at=valid_at,
            )

        # 3. System nodes + AFFECTS edges
        for system_id in decision.affects:
            tx.run(
                _UPSERT_SYSTEM,
                system_id=system_id,
                workspace_id=decision.workspace_id,
                access_policy=access_policy,
            )
            tx.run(
                _LINK_AFFECTS,
                decision_id=decision.event_id,
                system_id=system_id,
                workspace_id=decision.workspace_id,
                valid_at=valid_at,
            )

        # 4. Rationale nodes + HAS_RATIONALE edges
        for i, rationale_text in enumerate(decision.rationale):
            rationale_id = f"{decision.event_id}:rationale:{i}"
            tx.run(
                _LINK_RATIONALE,
                decision_id=decision.event_id,
                rationale_id=rationale_id,
                workspace_id=decision.workspace_id,
                content=rationale_text,
                access_policy=access_policy,
                valid_at=valid_at,
            )

        # 5. SUPERSEDES edge — invalidate previous decision
        if decision.replaces:
            tx.run(
                _SUPERSEDE_PREVIOUS,
                prev_id=decision.replaces,
                next_id=decision.event_id,
                invalid_at=valid_at,
                valid_at=valid_at,
            )
