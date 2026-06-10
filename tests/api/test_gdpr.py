"""Tests for api/gdpr.py — GDPR erasure route."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from api.main import app


def test_gdpr_erase_success() -> None:
    client = TestClient(app)
    with patch(
        "api.gdpr.memory",
        return_value=AsyncMock(
            erase_gdpr_subject=AsyncMock(
                return_value={
                    "audit_id": "audit-1",
                    "workspace_id": "ws-1",
                    "person_id": "alice@company.com",
                    "decisions_deleted": 3,
                    "requested_by": "admin@company.com",
                }
            )
        ),
    ):
        response = client.post(
            "/gdpr/erase",
            json={
                "workspace_id": "ws-1",
                "person_id": "alice@company.com",
                "requested_by": "admin@company.com",
            },
            headers={"X-Cortex-Roles": "admin,gdpr_officer"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_id"] == "audit-1"
    assert payload["decisions_deleted"] == 3


def test_gdpr_erase_forbidden_without_privileged_role() -> None:
    client = TestClient(app)
    response = client.post(
        "/gdpr/erase",
        json={
            "workspace_id": "ws-1",
            "person_id": "alice@company.com",
            "requested_by": "user@company.com",
        },
        headers={"X-Cortex-Roles": "authenticated"},
    )
    assert response.status_code == 403


def test_gdpr_erase_not_found() -> None:
    client = TestClient(app)
    failing = AsyncMock()
    failing.erase_gdpr_subject.side_effect = ValueError(
        "Person 'missing@company.com' not found in workspace 'ws-1'."
    )
    with patch("api.gdpr.memory", return_value=failing):
        response = client.post(
            "/gdpr/erase",
            json={
                "workspace_id": "ws-1",
                "person_id": "missing@company.com",
                "requested_by": "admin@company.com",
            },
            headers={"X-Cortex-Roles": "legal"},
        )
    assert response.status_code == 404


def test_gdpr_erase_graph_failure() -> None:
    client = TestClient(app)
    failing = AsyncMock()
    failing.erase_gdpr_subject.side_effect = RuntimeError("neo4j down")
    with patch("api.gdpr.memory", return_value=failing):
        response = client.post(
            "/gdpr/erase",
            json={
                "workspace_id": "ws-1",
                "person_id": "alice@company.com",
                "requested_by": "admin@company.com",
            },
            headers={"X-Cortex-Roles": "admin"},
        )
    assert response.status_code == 503
