"""Tests for api/main.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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
        "api.main.memory",
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


@patch("api.contradictions.GraphDatabase.driver")
def test_contradictions_pending(mock_driver: MagicMock) -> None:
    session = MagicMock()

    class Rec:
        def get(self, key: str, default: object = None) -> object:
            data = {
                "id": "c1",
                "score": 0.6,
                "explanation": "overlap",
                "access_policy": '{"roles": ["authenticated"], "deny": [], "classification": "internal", "gdpr_subject": false}',
                "new_id": "d-new",
                "prior_id": "d-old",
                "status": "pending",
            }
            return data.get(key, default)

        def __getitem__(self, key: str) -> object:
            return self.get(key)

    session.run.return_value = [Rec()]
    cm = MagicMock()
    cm.__enter__.return_value = session
    cm.__exit__.return_value = False
    mock_driver.return_value.session.return_value = cm

    client = TestClient(app)
    response = client.get("/contradictions/pending", params={"workspace_id": "ws-1"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "c1"
