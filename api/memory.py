"""Query and injection layer over Neo4j, Redis, and optional Qdrant."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from typing import Any

import structlog

from graph.gdpr import GdprErasureService
from graph.query import GraphQueryService
from memory.semantic import search_decision_ids, semantic_enabled
from scoring.trust_scorer import is_injectable

log = structlog.get_logger(__name__)


class MemoryService:
    """Coordinates graph reads with Redis caching and optional semantic search."""

    def __init__(self) -> None:
        self._graph = GraphQueryService()
        self._gdpr = GdprErasureService()
        self._redis = self._build_redis_client()

    @staticmethod
    def _build_redis_client() -> Any | None:
        try:
            import redis
        except ImportError:
            return None

        try:
            client = redis.Redis(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", "6379")),
                password=os.environ.get("REDIS_PASSWORD"),
                socket_connect_timeout=1,
                decode_responses=True,
            )
            client.ping()
            return client
        except Exception:
            return None

    @staticmethod
    def _cache_key(prefix: str, payload: dict[str, Any]) -> str:
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8"),
        ).hexdigest()
        return f"cortex:{prefix}:{digest}"

    async def query_decisions(
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
        """Search organizational memory with Redis caching."""
        cache_payload = {
            "query": query,
            "workspace_id": workspace_id,
            "limit": limit,
            "min_importance": min_importance,
            "min_trust": min_trust,
            "event_types": event_types,
            "caller_roles": caller_roles,
        }
        cache_key = self._cache_key("query", cache_payload)

        if self._redis is not None:
            cached = self._redis.get(cache_key)
            if cached:
                log.debug("memory.query.cache_hit", workspace_id=workspace_id)
                return json.loads(cached)

        results = await self._graph.search_decisions(
            query=query,
            workspace_id=workspace_id,
            limit=limit,
            min_importance=min_importance,
            min_trust=min_trust,
            event_types=event_types,
            caller_roles=caller_roles,
        )

        if semantic_enabled():
            semantic_ids = search_decision_ids(
                query,
                workspace_id=workspace_id,
                limit=limit,
            )
            if semantic_ids:
                extra = await self._graph.fetch_decisions_by_ids(
                    ids=semantic_ids,
                    workspace_id=workspace_id,
                    caller_roles=caller_roles,
                )
                seen = {row["event_id"] for row in results}
                for row in extra:
                    if row["event_id"] not in seen:
                        results.append(row)
                        seen.add(row["event_id"])
                results = results[:limit]

        if self._redis is not None:
            self._redis.setex(cache_key, 60, json.dumps(results))

        return results

    async def inject_decisions(
        self,
        *,
        context: str,
        workspace_id: str,
        caller_roles: list[str],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return injectable decisions ranked by importance and trust."""
        results = await self.query_decisions(
            query=context,
            workspace_id=workspace_id,
            limit=limit,
            min_importance=0.0,
            min_trust=0.0,
            event_types=[],
            caller_roles=caller_roles,
        )
        injectable = [item for item in results if is_injectable(item["trust_score"])]
        injectable.sort(
            key=lambda item: (
                item["importance_score"] * item["trust_score"],
                item["extracted_at"],
            ),
            reverse=True,
        )
        return injectable[:limit]

    async def decisions_by_system(
        self,
        *,
        system_id: str,
        workspace_id: str,
        limit: int,
        caller_roles: list[str],
    ) -> list[dict[str, Any]]:
        """Recent decisions affecting a system."""
        return await self._graph.find_decisions_by_system(
            system_id=system_id,
            workspace_id=workspace_id,
            limit=limit,
            caller_roles=caller_roles,
        )

    async def causal_chain(
        self,
        *,
        decision_id: str,
        workspace_id: str,
        max_depth: int,
        caller_roles: list[str],
    ) -> list[dict[str, Any]]:
        """SUPERSEDES and triggered_by lineage for a decision."""
        return await self._graph.trace_causal_chain(
            decision_id=decision_id,
            workspace_id=workspace_id,
            max_depth=max_depth,
            caller_roles=caller_roles,
        )

    async def conflict_candidates(
        self,
        *,
        decision_id: str,
        workspace_id: str,
        limit: int,
        caller_roles: list[str],
    ) -> list[dict[str, Any]]:
        """Decisions on shared systems (contradiction preview)."""
        return await self._graph.find_conflict_candidates(
            decision_id=decision_id,
            workspace_id=workspace_id,
            limit=limit,
            caller_roles=caller_roles,
        )

    async def pending_contradictions(
        self,
        *,
        workspace_id: str,
        caller_roles: list[str],
    ) -> list[dict[str, Any]]:
        """RBAC-filtered queue of contradictions awaiting human review."""
        return await self._graph.list_pending_contradictions(
            workspace_id=workspace_id,
            caller_roles=caller_roles,
        )

    async def resolve_contradiction(
        self,
        *,
        contradiction_id: str,
        workspace_id: str,
        resolution: str,
        caller_roles: list[str],
    ) -> dict[str, str] | None:
        """Resolve a pending contradiction after human review."""
        return await self._graph.resolve_contradiction(
            contradiction_id=contradiction_id,
            workspace_id=workspace_id,
            resolution=resolution,
            caller_roles=caller_roles,
        )

    async def erase_gdpr_subject(
        self,
        *,
        workspace_id: str,
        person_id: str,
        requested_by: str,
        caller_roles: list[str],
        reason: str = "gdpr_right_to_erasure",
    ) -> dict[str, Any]:
        """Cascade-delete a data subject and linked memory nodes."""
        result = await asyncio.to_thread(
            self._gdpr.erase_subject,
            workspace_id=workspace_id,
            person_id=person_id,
            requested_by=requested_by,
            caller_roles=caller_roles,
            reason=reason,
        )
        return {
            "audit_id": result.audit_id,
            "workspace_id": result.workspace_id,
            "person_id": result.person_id,
            "decisions_deleted": result.decisions_deleted,
            "requested_by": result.requested_by,
        }

    async def neo4j_health(self) -> str:
        """Return ``'ok'`` when the shared async driver is reachable."""
        return "ok" if await self._graph.health() else "unreachable"

    def redis_health(self) -> str:
        """Return ``'ok'`` when the cached Redis client responds to PING."""
        if self._redis is None:
            return "unreachable"
        try:
            self._redis.ping()
            return "ok"
        except Exception:
            return "unreachable"

    async def close(self) -> None:
        await self._graph.close()
        self._gdpr.close()
