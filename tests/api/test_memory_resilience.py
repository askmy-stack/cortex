"""MemoryService resilience — Redis optional, cache hits, graph failures."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

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

    def _redis_get(key: str) -> str | None:
        if key.endswith(":cache_epoch"):
            return "0"
        return json.dumps([_SAMPLE_ROW])

    redis.get.side_effect = _redis_get
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


def test_build_redis_client_uses_redis_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """REDIS_URL (Upstash) takes precedence over REDIS_HOST for cloud deploys."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("REDIS_HOST", raising=False)

    with patch("redis.from_url") as from_url:
        client = MagicMock()
        client.ping.return_value = True
        from_url.return_value = client
        built = MemoryService._build_redis_client()

    from_url.assert_called_once()
    assert built is client


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


def test_invalidate_workspace_cache_bumps_epoch() -> None:
    svc = MemoryService()
    redis = MagicMock()
    redis.get.return_value = "2"
    svc._redis = redis

    svc.invalidate_workspace_cache("ws-1")

    redis.incr.assert_called_once_with("cortex:ws:ws-1:cache_epoch")


def test_cache_key_changes_after_invalidation() -> None:
    svc = MemoryService()
    redis = MagicMock()
    redis.get.side_effect = ["0", "1"]
    svc._redis = redis
    payload = {
        "query": "payments",
        "workspace_id": "ws-1",
        "limit": 5,
        "min_importance": 0.0,
        "min_trust": 0.0,
        "event_types": [],
        "caller_roles": ["authenticated"],
    }

    key_before = svc._cache_key("query", payload)
    svc.invalidate_workspace_cache("ws-1")
    key_after = svc._cache_key("query", payload)

    assert key_before != key_after


@pytest.mark.asyncio
async def test_erase_gdpr_subject_invalidates_workspace_cache() -> None:
    svc = MemoryService()
    redis = MagicMock()
    svc._redis = redis
    svc._gdpr.erase_subject = MagicMock(
        return_value=MagicMock(
            audit_id="audit-1",
            workspace_id="ws-1",
            person_id="alice@co.com",
            decisions_deleted=3,
            requested_by="admin@co.com",
        ),
    )

    await svc.erase_gdpr_subject(
        workspace_id="ws-1",
        person_id="alice@co.com",
        requested_by="admin@co.com",
        caller_roles=["admin"],
    )

    redis.incr.assert_called_once_with("cortex:ws:ws-1:cache_epoch")
