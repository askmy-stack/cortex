"""Neo4j read helpers with RBAC enforcement."""

from __future__ import annotations

import os
from typing import Any

import structlog
from neo4j import AsyncDriver, AsyncGraphDatabase

from graph.rbac import can_access, normalize_access_policy

log = structlog.get_logger(__name__)

_FETCH_BY_IDS = """
MATCH (d:Decision)
WHERE d.workspace_id = $workspace_id AND d.id IN $ids
  AND d.status <> 'archived'
OPTIONAL MATCH (p:Person)-[:MADE]->(d)
OPTIONAL MATCH (d)-[:AFFECTS]->(s:System)
OPTIONAL MATCH (d)-[:HAS_RATIONALE]->(r:Rationale)
WITH d,
     collect(DISTINCT p.id) AS made_by,
     collect(DISTINCT s.id) AS affects,
     collect(DISTINCT r.content) AS rationale
RETURN d, made_by, affects, rationale
"""

_SEARCH_DECISIONS = """
CALL db.index.fulltext.queryNodes('decision_content_fulltext', $search_text)
YIELD node AS d, score
WHERE d.workspace_id = $workspace_id
  AND d.status <> 'archived'
  AND ($min_importance = 0.0 OR d.importance_score >= $min_importance)
  AND ($min_trust = 0.0 OR d.trust_score >= $min_trust)
  AND (size($event_types) = 0 OR d.event_type IN $event_types)
OPTIONAL MATCH (p:Person)-[:MADE]->(d)
OPTIONAL MATCH (d)-[:AFFECTS]->(s:System)
OPTIONAL MATCH (d)-[:HAS_RATIONALE]->(r:Rationale)
WITH d, score,
     collect(DISTINCT p.id) AS made_by,
     collect(DISTINCT s.id) AS affects,
     collect(DISTINCT r.content) AS rationale
RETURN d, score, made_by, affects, rationale
ORDER BY score DESC, d.importance_score DESC
LIMIT $limit
"""

_DECISIONS_BY_SYSTEM = """
MATCH (d:Decision)-[:AFFECTS]->(s:System)
WHERE d.workspace_id = $workspace_id
  AND d.status <> 'archived'
  AND (s.id = $system_id OR toLower(s.name) = toLower($system_id))
OPTIONAL MATCH (p:Person)-[:MADE]->(d)
OPTIONAL MATCH (d)-[:AFFECTS]->(sys:System)
OPTIONAL MATCH (d)-[:HAS_RATIONALE]->(r:Rationale)
WITH d,
     collect(DISTINCT p.id) AS made_by,
     collect(DISTINCT sys.id) AS affects,
     collect(DISTINCT r.content) AS rationale
RETURN d, made_by, affects, rationale
ORDER BY d.extracted_at DESC
LIMIT $limit
"""

# Variable-length depth must be a literal in Cypher (Neo4j 5 does not allow a
# parameter inside `*1..N`). `_causal_chain_query` substitutes a validated
# integer into the template below before execution.
_CAUSAL_CHAIN_TEMPLATE = """
MATCH (root:Decision {{id: $decision_id, workspace_id: $workspace_id}})
OPTIONAL MATCH (root)-[:SUPERSEDES*1..{depth}]->(prior:Decision)
  WHERE prior.workspace_id = $workspace_id
OPTIONAL MATCH (successor:Decision)-[:SUPERSEDES*1..{depth}]->(root)
  WHERE successor.workspace_id = $workspace_id
OPTIONAL MATCH (trigger:Decision {{workspace_id: $workspace_id}})
  WHERE trigger.id = root.triggered_by
WITH collect(DISTINCT root) AS roots,
     collect(DISTINCT prior) AS priors,
     collect(DISTINCT successor) AS successors,
     collect(DISTINCT trigger) AS triggers
WITH roots + priors + successors + [t IN triggers WHERE t IS NOT NULL] AS all_nodes
UNWIND all_nodes AS d
WITH DISTINCT d
WHERE d.status <> 'archived'
OPTIONAL MATCH (p:Person)-[:MADE]->(d)
OPTIONAL MATCH (d)-[:AFFECTS]->(sys:System)
OPTIONAL MATCH (d)-[:HAS_RATIONALE]->(r:Rationale)
OPTIONAL MATCH (d)-[:SUPERSEDES]->(replaced:Decision)
RETURN d,
       collect(DISTINCT p.id) AS made_by,
       collect(DISTINCT sys.id) AS affects,
       collect(DISTINCT r.content) AS rationale,
       collect(DISTINCT replaced.id) AS supersedes_ids,
       d.triggered_by AS triggered_by_id
ORDER BY d.extracted_at ASC
"""


def _causal_chain_query(depth: int) -> str:
    """Render the causal-chain query with a validated literal depth.

    Depth is clamped to ``1..8`` before substitution to keep the Cypher path
    bounded and to defuse any injection risk from the integer formatting.
    """
    bounded = max(1, min(int(depth), 8))
    return _CAUSAL_CHAIN_TEMPLATE.format(depth=bounded)

_CONFLICT_CANDIDATES = """
MATCH (d:Decision {id: $decision_id, workspace_id: $workspace_id})-[:AFFECTS]->(s:System)
MATCH (other:Decision)-[:AFFECTS]->(s)
WHERE other.id <> $decision_id
  AND other.workspace_id = $workspace_id
  AND other.status IN ['active', 'under_review']
OPTIONAL MATCH (p:Person)-[:MADE]->(other)
OPTIONAL MATCH (other)-[:AFFECTS]->(sys:System)
OPTIONAL MATCH (other)-[:HAS_RATIONALE]->(r:Rationale)
RETURN other AS d,
       collect(DISTINCT p.id) AS made_by,
       collect(DISTINCT sys.id) AS affects,
       collect(DISTINCT r.content) AS rationale
LIMIT $limit
"""

_PENDING_CONTRADICTIONS = """
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

_RESOLVE_CONTRADICTION = """
MATCH (c:Contradiction {id: $id, workspace_id: $workspace_id, status: 'pending'})
SET c.status = $resolution,
    c.resolved_at = datetime()
RETURN c.id AS id, c.status AS status
"""


class GraphQueryService:
    """Read-only graph access with RBAC filtering."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self._uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self._user = user or os.environ.get("NEO4J_USER", "neo4j")
        self._password = password or os.environ.get("NEO4J_PASSWORD", "cortex_local")
        self._driver: AsyncDriver | None = None

    async def _driver_instance(self) -> AsyncDriver:
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password),
            )
        return self._driver

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    async def search_decisions(
        self,
        *,
        query: str,
        workspace_id: str,
        limit: int,
        min_importance: float,
        min_trust: float,
        event_types: list[str],
        caller_roles: list[str],
    ) -> list[dict[str, Any]]:
        """Search decisions and return RBAC-filtered records."""
        driver = await self._driver_instance()
        results: list[dict[str, Any]] = []

        async with driver.session() as session:
            result = await session.run(
                _SEARCH_DECISIONS,
                search_text=query,
                workspace_id=workspace_id,
                limit=limit,
                min_importance=min_importance,
                min_trust=min_trust,
                event_types=event_types,
            )
            async for record in result:
                decision = record["d"]
                if not can_access(decision.get("access_policy"), caller_roles):
                    continue
                results.append(
                    self._format_decision(
                        decision,
                        record["made_by"],
                        record["affects"],
                        record["rationale"],
                    )
                )

        log.info(
            "graph.query.search_complete",
            workspace_id=workspace_id,
            result_count=len(results),
        )
        return results

    async def find_decisions_by_system(
        self,
        *,
        system_id: str,
        workspace_id: str,
        limit: int,
        caller_roles: list[str],
    ) -> list[dict[str, Any]]:
        """Return recent decisions affecting a system (by id or name)."""
        driver = await self._driver_instance()
        results: list[dict[str, Any]] = []
        async with driver.session() as session:
            result = await session.run(
                _DECISIONS_BY_SYSTEM,
                system_id=system_id,
                workspace_id=workspace_id,
                limit=limit,
            )
            async for record in result:
                decision = record["d"]
                if not can_access(decision.get("access_policy"), caller_roles):
                    continue
                results.append(
                    self._format_decision(
                        decision,
                        record["made_by"],
                        record["affects"],
                        record["rationale"],
                    )
                )
        log.info(
            "graph.query.by_system",
            workspace_id=workspace_id,
            system_id=system_id,
            result_count=len(results),
        )
        return results

    async def get_decision(
        self,
        *,
        decision_id: str,
        workspace_id: str,
        caller_roles: list[str],
    ) -> dict[str, Any] | None:
        """Load a single decision by id."""
        rows = await self.fetch_decisions_by_ids(
            ids=[decision_id],
            workspace_id=workspace_id,
            caller_roles=caller_roles,
        )
        return rows[0] if rows else None

    async def trace_causal_chain(
        self,
        *,
        decision_id: str,
        workspace_id: str,
        max_depth: int,
        caller_roles: list[str],
    ) -> list[dict[str, Any]]:
        """Return the root decision and related SUPERSEDES / TRIGGERED chain."""
        driver = await self._driver_instance()
        depth = max(1, min(max_depth, 8))
        nodes: list[dict[str, Any]] = []
        async with driver.session() as session:
            result = await session.run(
                _causal_chain_query(depth),
                decision_id=decision_id,
                workspace_id=workspace_id,
            )
            async for record in result:
                decision = record["d"]
                if not can_access(decision.get("access_policy"), caller_roles):
                    continue
                formatted = self._format_decision(
                    decision,
                    record["made_by"],
                    record["affects"],
                    record["rationale"],
                )
                formatted["supersedes_ids"] = [
                    value for value in record["supersedes_ids"] if value
                ]
                formatted["triggered_by_id"] = record["triggered_by_id"]
                nodes.append(formatted)
        log.info(
            "graph.query.causal_chain",
            workspace_id=workspace_id,
            decision_id=decision_id,
            node_count=len(nodes),
        )
        return nodes

    async def list_pending_contradictions(
        self,
        *,
        workspace_id: str,
        caller_roles: list[str],
    ) -> list[dict[str, Any]]:
        """Return pending contradictions, RBAC-filtered."""
        driver = await self._driver_instance()
        rows: list[dict[str, Any]] = []
        async with driver.session() as session:
            result = await session.run(
                _PENDING_CONTRADICTIONS,
                workspace_id=workspace_id,
            )
            async for record in result:
                policy = normalize_access_policy(record.get("access_policy"))
                if not can_access(policy, caller_roles):
                    continue
                rows.append(
                    {
                        "id": str(record["id"]),
                        "score": float(record["score"] or 0.0),
                        "explanation": str(record["explanation"] or ""),
                        "new_decision_id": record.get("new_id"),
                        "prior_decision_id": record.get("prior_id"),
                        "status": str(record.get("status") or "pending"),
                    }
                )
        return rows

    async def resolve_contradiction(
        self,
        *,
        contradiction_id: str,
        workspace_id: str,
        resolution: str,
        caller_roles: list[str],
    ) -> dict[str, Any] | None:
        """Mark a pending contradiction as reviewed (RBAC-checked)."""
        driver = await self._driver_instance()
        async with driver.session() as session:
            lookup = await session.run(
                """
                MATCH (c:Contradiction {id: $id, workspace_id: $workspace_id, status: 'pending'})
                RETURN c.access_policy AS access_policy
                """,
                id=contradiction_id,
                workspace_id=workspace_id,
            )
            record = await lookup.single()
            if record is None:
                return None
            policy = normalize_access_policy(record.get("access_policy"))
            if not can_access(policy, caller_roles):
                return None
            result = await session.run(
                _RESOLVE_CONTRADICTION,
                id=contradiction_id,
                workspace_id=workspace_id,
                resolution=resolution,
            )
            resolved = await result.single()
            if resolved is None:
                return None
            return {
                "id": str(resolved["id"]),
                "status": str(resolved["status"]),
            }

    async def health(self) -> bool:
        """Lightweight liveness probe — verifies driver connectivity."""
        try:
            driver = await self._driver_instance()
            await driver.verify_connectivity()
            return True
        except Exception:
            return False

    async def workspace_coverage_score(self, workspace_id: str) -> float:
        """Estimate memory completeness for a workspace (0–1 heuristic).

        Uses decision and system counts vs portfolio demo targets. Full Phase 8
        coverage scoring will replace this with domain-aware completeness.
        """
        driver = await self._driver_instance()
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (d:Decision {workspace_id: $workspace_id})
                WHERE d.status <> 'archived'
                WITH count(d) AS decisions
                OPTIONAL MATCH (s:System {workspace_id: $workspace_id})
                WITH decisions, count(s) AS systems
                RETURN decisions, systems
                """,
                workspace_id=workspace_id,
            )
            record = await result.single()
        if record is None:
            return 0.0
        decisions = int(record.get("decisions") or 0)
        systems = int(record.get("systems") or 0)
        decision_ratio = min(1.0, decisions / 50.0)
        system_ratio = min(1.0, systems / 15.0)
        return round(min(1.0, 0.7 * decision_ratio + 0.3 * system_ratio), 3)

    async def find_conflict_candidates(
        self,
        *,
        decision_id: str,
        workspace_id: str,
        limit: int,
        caller_roles: list[str],
    ) -> list[dict[str, Any]]:
        """Return active decisions on shared systems (contradiction preview)."""
        driver = await self._driver_instance()
        results: list[dict[str, Any]] = []
        async with driver.session() as session:
            result = await session.run(
                _CONFLICT_CANDIDATES,
                decision_id=decision_id,
                workspace_id=workspace_id,
                limit=limit,
            )
            async for record in result:
                decision = record["d"]
                if not can_access(decision.get("access_policy"), caller_roles):
                    continue
                results.append(
                    self._format_decision(
                        decision,
                        record["made_by"],
                        record["affects"],
                        record["rationale"],
                    )
                )
        return results

    @staticmethod
    def _format_decision(
        decision: Any,
        made_by: list[Any],
        affects: list[Any],
        rationale: list[Any],
    ) -> dict[str, Any]:
        return {
            "event_id": decision.get("id", ""),
            "event_type": decision.get("event_type", ""),
            "content": decision.get("content", ""),
            "made_by": [value for value in made_by if value],
            "affects": [value for value in affects if value],
            "rationale": [value for value in rationale if value],
            "importance_score": decision.get("importance_score", 0.0),
            "trust_score": decision.get("trust_score", 0.0),
            "extraction_confidence": decision.get("extraction_confidence", 0.0),
            "source": decision.get("source", ""),
            "channel": decision.get("channel", ""),
            "extracted_at": decision.get("extracted_at", ""),
            "status": decision.get("status", "active"),
        }

    async def fetch_decisions_by_ids(
        self,
        *,
        ids: list[str],
        workspace_id: str,
        caller_roles: list[str],
    ) -> list[dict[str, Any]]:
        """Load decisions by id with RBAC filtering."""
        if not ids:
            return []
        driver = await self._driver_instance()
        results: list[dict[str, Any]] = []
        async with driver.session() as session:
            result = await session.run(
                _FETCH_BY_IDS,
                ids=ids,
                workspace_id=workspace_id,
            )
            async for record in result:
                decision = record["d"]
                if not can_access(decision.get("access_policy"), caller_roles):
                    continue
                results.append(
                    self._format_decision(
                        decision,
                        record["made_by"],
                        record["affects"],
                        record["rationale"],
                    )
                )
        return results
