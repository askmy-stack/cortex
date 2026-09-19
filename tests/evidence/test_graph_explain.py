"""Tests for evidence authority policy and explainer assembly."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from evidence.authority import compare_authority, load_authority_scores, score_for_class
from evidence.explain import EvidenceExplainer
from evidence.graph import EvidenceGraphWriter
from shared.v2_models import Claim, Evidence


def test_default_authority_ordering() -> None:
    assert score_for_class("formal_policy") > score_for_class("casual_chat")
    assert compare_authority("merged_PR", "casual_chat") == 1
    assert compare_authority("agent_inference", "approved_ADR") == -1


def test_authority_json_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CORTEX_AUTHORITY_SCORES_JSON",
        '{"casual_chat": 0.9, "merged_PR": 0.1}',
    )
    scores = load_authority_scores()
    assert scores["casual_chat"] == 0.9
    assert scores["merged_PR"] == 0.1


def test_writer_skips_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_EVIDENCE_GRAPH", "false")
    with patch("evidence.graph.GraphDatabase") as gdb:
        writer = EvidenceGraphWriter(uri="bolt://x", user="u", password="p")
        claim = Claim(
            workspace_id="ws",
            subject="s",
            predicate="p",
            object="o",
            content="c",
        )
        assert writer.write_claim_with_evidence(claim, []) is None
        gdb.driver.return_value.session.assert_not_called()
        writer.close()


def test_writer_runs_when_forced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_EVIDENCE_GRAPH", "false")
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session
    with patch("evidence.graph.GraphDatabase") as gdb:
        gdb.driver.return_value = mock_driver
        writer = EvidenceGraphWriter(uri="bolt://x", user="u", password="p")
        writer._driver = mock_driver
        claim = Claim(
            workspace_id="ws",
            subject="payments",
            predicate="uses",
            object="CockroachDB",
            content="payments uses CockroachDB",
            decision_id="dec-1",
        )
        ev = Evidence(
            workspace_id="ws",
            source_type="github",
            source_id="pr-1",
            authority_class="merged_PR",
        )
        result = writer.write_claim_with_evidence(claim, [ev], force=True)
        assert result == claim.id
        mock_session.execute_write.assert_called_once()
        writer.close()


def test_explainer_filters_empty_evidence() -> None:
    mock_record = {
        "claim": {
            "id": "c1",
            "content": "payments uses CockroachDB",
            "confidence": 0.9,
            "status": "ACTIVE",
            "assertion_type": "ASSERTED",
            "valid_from": None,
            "valid_to": None,
            "observed_at": None,
        },
        "supporting": [{"id": "e1", "source_type": "github"}, None, {}],
        "conflicting": [None],
    }
    mock_result = MagicMock()
    mock_result.single.return_value = mock_record
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.run.return_value = mock_result
    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session

    explainer = EvidenceExplainer(driver=mock_driver)
    out = explainer.explain(claim_id="c1", workspace_id="ws")
    assert out is not None
    assert out["claim"] == "payments uses CockroachDB"
    assert len(out["supporting_evidence"]) == 1
    assert out["conflicting_evidence"] == []
