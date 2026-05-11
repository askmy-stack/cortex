"""Tests for api/main.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from api.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    with patch("api.main._check_neo4j", return_value="ok"), patch(
        "api.main._check_redis",
        return_value="ok",
    ):
        response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["dependencies"]["neo4j"] == "ok"


def test_query_endpoint_uses_memory_service() -> None:
    client = TestClient(app)
    with patch(
        "api.main._memory",
        return_value=AsyncMock(
            query_decisions=AsyncMock(
                return_value=[
                    {
                        "event_id": "d-1",
                        "event_type": "decision",
                        "content": "Use CockroachDB",
                        "made_by": ["alice@company.com"],
                        "affects": ["payments-service"],
                        "rationale": ["Scale"],
                        "importance_score": 0.9,
                        "trust_score": 0.8,
                        "extraction_confidence": 0.95,
                        "source": "slack",
                        "channel": "C-engineering",
                        "extracted_at": "2026-05-11T12:00:00+00:00",
                        "status": "active",
                    }
                ]
            )
        ),
    ):
        response = client.post(
            "/query",
            json={"query": "why CockroachDB", "workspace_id": "ws-1"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["results"][0]["made_by"] == ["alice@company.com"]
