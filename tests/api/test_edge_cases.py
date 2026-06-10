"""API edge cases — validation, empty results, dependency failures."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from api.main import app


def test_query_rejects_empty_string() -> None:
    client = TestClient(app)
    response = client.post(
        "/query",
        json={"query": "", "workspace_id": "ws-1"},
    )
    assert response.status_code == 422


def test_query_rejects_too_short() -> None:
    client = TestClient(app)
    response = client.post(
        "/query",
        json={"query": "ab", "workspace_id": "ws-1"},
    )
    assert response.status_code == 422


def test_query_empty_workspace_returns_zero_results() -> None:
    client = TestClient(app)
    with patch(
        "api.main.memory",
        return_value=AsyncMock(query_decisions=AsyncMock(return_value=[])),
    ):
        response = client.post(
            "/query",
            json={"query": "any decision", "workspace_id": "empty-workspace"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
    assert payload["results"] == []
    assert payload["workspace_id"] == "empty-workspace"


def test_query_neo4j_failure_returns_503() -> None:
    client = TestClient(app)
    failing = AsyncMock()
    failing.query_decisions.side_effect = RuntimeError("neo4j connection refused")
    with patch("api.main.memory", return_value=failing):
        response = client.post(
            "/query",
            json={"query": "payments database", "workspace_id": "ws-1"},
        )
    assert response.status_code == 503
    assert "Graph query failed" in response.json()["detail"]


def test_health_returns_200_when_neo4j_degraded() -> None:
    """Liveness probe stays 200; callers inspect dependencies."""
    client = TestClient(app)
    with patch(
        "api.main._check_neo4j",
        new=AsyncMock(return_value="unreachable"),
    ), patch("api.main._check_redis", return_value="ok"):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["dependencies"]["neo4j"] == "unreachable"


def test_health_returns_200_when_redis_degraded() -> None:
    client = TestClient(app)
    with patch(
        "api.main._check_neo4j",
        new=AsyncMock(return_value="ok"),
    ), patch("api.main._check_redis", return_value="unreachable"):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["dependencies"]["redis"] == "unreachable"


def test_inject_rejects_short_context() -> None:
    client = TestClient(app)
    response = client.post(
        "/inject",
        json={
            "context": "short",
            "workspace_id": "ws-1",
            "agent_id": "agent-1",
        },
    )
    assert response.status_code == 422


def test_query_limit_bounds() -> None:
    client = TestClient(app)
    response = client.post(
        "/query",
        json={"query": "valid query", "workspace_id": "ws-1", "limit": 0},
    )
    assert response.status_code == 422

    response = client.post(
        "/query",
        json={"query": "valid query", "workspace_id": "ws-1", "limit": 51},
    )
    assert response.status_code == 422
