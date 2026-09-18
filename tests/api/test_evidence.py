"""API tests for GET /evidence/explain/{claim_id}."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_explain_404_when_missing() -> None:
    with patch("api.evidence.EvidenceExplainer") as cls:
        inst = MagicMock()
        inst.explain.return_value = None
        cls.return_value = inst
        resp = client.get("/evidence/explain/missing?workspace_id=ws")
    assert resp.status_code == 404


def test_explain_200() -> None:
    payload = {
        "claim": "payments uses CockroachDB",
        "claim_id": "c1",
        "confidence": 0.94,
        "status": "ACTIVE",
        "assertion_type": "ASSERTED",
        "temporal": {},
        "supporting_evidence": [{"id": "e1", "type": "ADR"}],
        "conflicting_evidence": [],
    }
    with patch("api.evidence.EvidenceExplainer") as cls:
        inst = MagicMock()
        inst.explain.return_value = payload
        cls.return_value = inst
        resp = client.get("/evidence/explain/c1?workspace_id=ws")
    assert resp.status_code == 200
    body = resp.json()
    assert body["claim_id"] == "c1"
    assert body["confidence"] == 0.94
