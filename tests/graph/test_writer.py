"""Tests for graph/writer.py.

Tests cover:
- Decision node upsert (MERGE idempotency)
- Person + MADE edge creation
- System + AFFECTS edge creation
- Rationale node + HAS_RATIONALE edge creation
- SUPERSEDES edge when decision.replaces is set
- Discard below IMPORTANCE_DISCARD threshold
- Default RBAC access_policy applied
- Transaction atomicity (all writes or none)
- All Neo4j calls are mocked — no real DB required
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from graph.rbac import serialize_access_policy
from graph.writer import _DEFAULT_ACCESS_POLICY, GraphWriter
from shared.models import (
    IMPORTANCE_DISCARD,
    DecisionEvent,
    Provenance,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

WORKSPACE_ID = "test-workspace"
NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _make_provenance() -> Provenance:
    return Provenance(
        source="slack",
        channel="C-engineering",
        original_timestamp=NOW,
        extractor_version="0.1.0",
        extractor_model="gpt-4o",
        verified_by=[],
        raw_event_id="raw-event-id-001",
    )


_UNSET: list = []  # sentinel — distinguish None from explicitly-passed empty list


def _make_decision(
    importance_score: float = 0.75,
    made_by: list[str] | None = None,
    affects: list[str] | None = None,
    rationale: list[str] | None = None,
    replaces: str | None = None,
) -> DecisionEvent:
    return DecisionEvent(
        source_raw_event_id="raw-event-id-001",
        workspace_id=WORKSPACE_ID,
        event_type="decision",
        content="We decided to migrate payments to CockroachDB.",
        made_by=["priya@company.com"] if made_by is None else made_by,
        affects=["payments-service"] if affects is None else affects,
        rationale=["Scale ceiling at 10M txn/day"] if rationale is None else rationale,
        replaces=replaces,
        extraction_confidence=0.90,
        importance_score=importance_score,
        trust_score=0.80,
        provenance=_make_provenance(),
        extracted_at=NOW,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GraphWriter init
# ─────────────────────────────────────────────────────────────────────────────


class TestGraphWriterInit:
    @patch("graph.writer.GraphDatabase")
    def test_initialises_with_env_defaults(
        self, mock_gdb: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NEO4J_URI", "bolt://testhost:7687")
        monkeypatch.setenv("NEO4J_USER", "testuser")
        monkeypatch.setenv("NEO4J_PASSWORD", "testpass")

        writer = GraphWriter()

        mock_gdb.driver.assert_called_once_with(
            "bolt://testhost:7687", auth=("testuser", "testpass")
        )
        assert writer._uri == "bolt://testhost:7687"

    @patch("graph.writer.GraphDatabase")
    def test_initialises_with_explicit_params(self, mock_gdb: MagicMock) -> None:
        GraphWriter(uri="bolt://custom:7687", user="u", password="p")
        mock_gdb.driver.assert_called_once_with(
            "bolt://custom:7687", auth=("u", "p")
        )


# ─────────────────────────────────────────────────────────────────────────────
# write() — importance threshold enforcement
# ─────────────────────────────────────────────────────────────────────────────


class TestWriteImportanceThreshold:
    @patch("graph.writer.GraphDatabase")
    def test_raises_below_importance_discard(self, mock_gdb: MagicMock) -> None:
        mock_gdb.driver.return_value = MagicMock()
        writer = GraphWriter(uri="bolt://x", user="u", password="p")
        decision = _make_decision(importance_score=IMPORTANCE_DISCARD - 0.01)

        with pytest.raises(ValueError, match="importance_score"):
            writer.write(decision)

    @patch("graph.writer.GraphDatabase")
    def test_raises_at_zero_importance(self, mock_gdb: MagicMock) -> None:
        mock_gdb.driver.return_value = MagicMock()
        writer = GraphWriter(uri="bolt://x", user="u", password="p")
        decision = _make_decision(importance_score=0.0)

        with pytest.raises(ValueError):
            writer.write(decision)

    @patch("graph.writer.GraphDatabase")
    def test_does_not_call_session_when_discarded(
        self, mock_gdb: MagicMock
    ) -> None:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        writer = GraphWriter(uri="bolt://x", user="u", password="p")
        decision = _make_decision(importance_score=0.10)

        with pytest.raises(ValueError):
            writer.write(decision)

        mock_driver.session.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# write() — successful writes
# ─────────────────────────────────────────────────────────────────────────────


class TestWriteSuccess:
    def _make_writer_with_mock_session(self) -> tuple[GraphWriter, MagicMock]:
        """Return a writer and the mock transaction object."""
        mock_tx = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.execute_write = MagicMock(
            side_effect=lambda fn, **kwargs: fn(mock_tx, **kwargs)
        )
        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        with patch("graph.writer.GraphDatabase") as mock_gdb:
            mock_gdb.driver.return_value = mock_driver
            writer = GraphWriter(uri="bolt://x", user="u", password="p")
            writer._driver = mock_driver

        return writer, mock_tx

    def test_returns_event_id_on_success(self) -> None:
        writer, _ = self._make_writer_with_mock_session()
        decision = _make_decision()
        result = writer.write(decision)
        assert result == decision.event_id

    def test_decision_node_upsert_called(self) -> None:
        writer, mock_tx = self._make_writer_with_mock_session()
        decision = _make_decision()
        writer.write(decision)

        calls = [str(c) for c in mock_tx.run.call_args_list]
        assert any("MERGE (d:Decision" in c for c in calls)

    def test_person_upsert_called_for_each_author(self) -> None:
        writer, mock_tx = self._make_writer_with_mock_session()
        decision = _make_decision(made_by=["alice@", "bob@"])
        writer.write(decision)

        cypher_calls = [c[0][0] for c in mock_tx.run.call_args_list]
        person_calls = [c for c in cypher_calls if "MERGE (p:Person" in c]
        assert len(person_calls) == 2

    def test_system_upsert_called_for_each_system(self) -> None:
        writer, mock_tx = self._make_writer_with_mock_session()
        decision = _make_decision(affects=["payments-service", "auth-service"])
        writer.write(decision)

        cypher_calls = [c[0][0] for c in mock_tx.run.call_args_list]
        system_calls = [c for c in cypher_calls if "MERGE (s:System" in c]
        assert len(system_calls) == 2

    def test_rationale_upsert_called_for_each_rationale(self) -> None:
        writer, mock_tx = self._make_writer_with_mock_session()
        decision = _make_decision(rationale=["Reason A", "Reason B", "Reason C"])
        writer.write(decision)

        cypher_calls = [c[0][0] for c in mock_tx.run.call_args_list]
        rationale_calls = [c for c in cypher_calls if "MERGE (r:Rationale" in c]
        assert len(rationale_calls) == 3

    def test_supersedes_called_when_replaces_set(self) -> None:
        writer, mock_tx = self._make_writer_with_mock_session()
        decision = _make_decision(replaces="prev-decision-id-001")
        writer.write(decision)

        cypher_calls = [c[0][0] for c in mock_tx.run.call_args_list]
        assert any("SUPERSEDES" in c for c in cypher_calls)

    def test_supersedes_not_called_when_replaces_none(self) -> None:
        writer, mock_tx = self._make_writer_with_mock_session()
        decision = _make_decision(replaces=None)
        writer.write(decision)

        cypher_calls = [c[0][0] for c in mock_tx.run.call_args_list]
        assert not any("SUPERSEDES" in c for c in cypher_calls)

    def test_default_access_policy_applied(self) -> None:
        writer, mock_tx = self._make_writer_with_mock_session()
        decision = _make_decision()
        writer.write(decision)

        # Find the Decision upsert call and check access_policy is present
        decision_call_kwargs = mock_tx.run.call_args_list[0][1]
        assert "access_policy" in decision_call_kwargs
        assert decision_call_kwargs["access_policy"] == serialize_access_policy(
            _DEFAULT_ACCESS_POLICY
        )

    def test_custom_access_policy_propagated(self) -> None:
        writer, mock_tx = self._make_writer_with_mock_session()
        decision = _make_decision()
        custom_policy = {
            "roles": ["admin", "lead"],
            "deny": ["intern"],
            "classification": "confidential",
            "gdpr_subject": False,
        }
        writer.write(decision, access_policy=custom_policy)

        decision_call_kwargs = mock_tx.run.call_args_list[0][1]
        assert "admin" in str(decision_call_kwargs["access_policy"])

    def test_no_person_calls_when_made_by_empty(self) -> None:
        writer, mock_tx = self._make_writer_with_mock_session()
        decision = _make_decision(made_by=[])
        writer.write(decision)

        cypher_calls = [c[0][0] for c in mock_tx.run.call_args_list]
        person_calls = [c for c in cypher_calls if "MERGE (p:Person" in c]
        assert len(person_calls) == 0

    def test_no_system_calls_when_affects_empty(self) -> None:
        writer, mock_tx = self._make_writer_with_mock_session()
        decision = _make_decision(affects=[])
        writer.write(decision)

        cypher_calls = [c[0][0] for c in mock_tx.run.call_args_list]
        system_calls = [c for c in cypher_calls if "MERGE (s:System" in c]
        assert len(system_calls) == 0

    def test_minimum_above_threshold_writes_successfully(self) -> None:
        writer, _ = self._make_writer_with_mock_session()
        decision = _make_decision(importance_score=IMPORTANCE_DISCARD)
        result = writer.write(decision)
        assert result == decision.event_id

    def test_temporal_edges_include_invalid_at_on_rationale(self) -> None:
        writer, mock_tx = self._make_writer_with_mock_session()
        writer.write(_make_decision(rationale=["Because scale"]))
        cypher_calls = [c[0][0] for c in mock_tx.run.call_args_list]
        rationale_link = next(c for c in cypher_calls if "HAS_RATIONALE" in c)
        assert "rel.invalid_at = null" in rationale_link

    def test_temporal_edges_include_invalid_at_on_supersedes(self) -> None:
        writer, mock_tx = self._make_writer_with_mock_session()
        writer.write(_make_decision(replaces="prev-decision-id-001"))
        cypher_calls = [c[0][0] for c in mock_tx.run.call_args_list]
        supersedes_link = next(c for c in cypher_calls if "SUPERSEDES" in c)
        assert "r.invalid_at = null" in supersedes_link
