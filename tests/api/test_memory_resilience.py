"""MemoryService resilience — Redis optional, cache hits, graph failures."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.memory import MemoryService

_SAMPLE_ROW = {
    "event_id": "d-1",
    "event_type": "decision",
    "content": "Use CockroachDB",
    "made_by": ["alice"],
    "affects": ["payments"],
    "rationale": ["scale"],
    "importance_score": 0.9,
    "trust_score": 0.8,
    "extraction_confidence": 0.95,
    "source": "slack",
    "channel": "C-engineering",
    "extracted_at": "2026-05-11T12:00:00+00:00",
    "status": "active",
}


@pytest.mark.asyncio
async def test_query_works_without_redis() -> None:
    svc = MemoryService()
    svc._redis = None
    svc._graph.search_decisions = AsyncMock(return_value=[_SAMPLE_ROW])

    rows = await svc.query_decisions(
        query="payments",
        workspace_id="ws-1",
        limit=5,
        min_importance=0.0,
        min_trust=0.0,
        event_types=[],
        caller_roles=["authenticated"],
    )

    assert len(rows) == 1
    svc._graph.search_decisions.assert_awaited_once()


@pytest.mark.asyncio
async def test_query_uses_redis_cache_hit() -> None:
    svc = MemoryService()
    redis = MagicMock()
    redis.get.return_value = json.dumps([_SAMPLE_ROW])
    svc._redis = redis
    svc._graph.search_decisions = AsyncMock()

    rows = await svc.query_decisions(
        query="payments",
        workspace_id="ws-1",
        limit=5,
        min_importance=0.0,
        min_trust=0.0,
        event_types=[],
        caller_roles=["authenticated"],
    )

    assert rows[0]["event_id"] == "d-1"
    svc._graph.search_decisions.assert_not_called()


@pytest.mark.asyncio
async def test_query_propagates_graph_failure() -> None:
    svc = MemoryService()
    svc._redis = None
    svc._graph.search_decisions = AsyncMock(side_effect=RuntimeError("neo4j down"))

    with pytest.raises(RuntimeError, match="neo4j down"):
        await svc.query_decisions(
            query="payments",
            workspace_id="ws-1",
            limit=5,
            min_importance=0.0,
            min_trust=0.0,
            event_types=[],
            caller_roles=["authenticated"],
        )


def test_redis_health_unreachable_when_client_none() -> None:
    svc = MemoryService()
    svc._redis = None
    assert svc.redis_health() == "unreachable"


def test_redis_health_ok_when_ping_succeeds() -> None:
    svc = MemoryService()
    redis = MagicMock()
    redis.ping.return_value = True
    svc._redis = redis
    assert svc.redis_health() == "ok"


@pytest.mark.asyncio
async def test_neo4j_health_degraded() -> None:
    svc = MemoryService()
    svc._graph.health = AsyncMock(return_value=False)
    assert await svc.neo4j_health() == "unreachable"
