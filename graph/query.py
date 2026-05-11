"""Neo4j read helpers with RBAC enforcement."""

from __future__ import annotations

import os
from typing import Any

import structlog
from neo4j import AsyncDriver, AsyncGraphDatabase

from graph.rbac import can_access

log = structlog.get_logger(__name__)

_SEARCH_DECISIONS = """
CALL db.index.fulltext.queryNodes('decision_content_fulltext', $query)
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
                query=query,
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
                    {
                        "event_id": decision.get("id", ""),
                        "event_type": decision.get("event_type", ""),
                        "content": decision.get("content", ""),
                        "made_by": [value for value in record["made_by"] if value],
                        "affects": [value for value in record["affects"] if value],
                        "rationale": [value for value in record["rationale"] if value],
                        "importance_score": decision.get("importance_score", 0.0),
                        "trust_score": decision.get("trust_score", 0.0),
                        "extraction_confidence": decision.get("extraction_confidence", 0.0),
                        "source": decision.get("source", ""),
                        "channel": decision.get("channel", ""),
                        "extracted_at": decision.get("extracted_at", ""),
                        "status": decision.get("status", "active"),
                    }
                )

        log.info(
            "graph.query.complete",
            workspace_id=workspace_id,
            result_count=len(results),
        )
        return results
