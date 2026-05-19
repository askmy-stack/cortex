"""Tests for decision graph read routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from api.main import app


def test_decisions_by_system() -> None:
    client = TestClient(app)
    with patch(
        "api.decisions.memory",
        return_value=AsyncMock(
            decisions_by_system=AsyncMock(
                return_value=[
                    {
                        "event_id": "d-1",
                        "event_type": "decision",
                        "content": "Use Redis",
                        "made_by": ["bob"],
                        "affects": ["cache"],
                        "rationale": [],
                        "importance_score": 0.8,
                        "trust_score": 0.7,
                        "extraction_confidence": 0.9,
                        "source": "github",
                        "channel": "org/repo",
                        "extracted_at": "2026-05-11T12:00:00+00:00",
                        "status": "active",
                    }
                ]
            )
        ),
    ):
        response = client.get(
            "/decisions/by-system/cache",
            params={"workspace_id": "ws-1"},
        )
    assert response.status_code == 200
    assert response.json()[0]["event_id"] == "d-1"


def test_causal_chain_not_found() -> None:
    client = TestClient(app)
    with patch(
        "api.decisions.memory",
        return_value=AsyncMock(causal_chain=AsyncMock(return_value=[])),
    ):
        response = client.get(
            "/decisions/missing/chain",
            params={"workspace_id": "ws-1"},
        )
    assert response.status_code == 404
