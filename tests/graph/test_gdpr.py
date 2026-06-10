"""Tests for graph/gdpr.py — GDPR cascade delete."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from graph.gdpr import GdprErasureService


@patch("graph.gdpr.GraphDatabase")
def test_erase_subject_requires_privileged_role(mock_gdb: MagicMock) -> None:
    mock_gdb.driver.return_value = MagicMock()
    service = GdprErasureService(uri="bolt://x", user="u", password="p")

    with pytest.raises(PermissionError, match="GDPR erasure requires"):
        service.erase_subject(
            workspace_id="ws-1",
            person_id="alice@company.com",
            requested_by="agent-1",
            caller_roles=["viewer"],
        )


@patch("graph.gdpr.GraphDatabase")
def test_erase_subject_cascade_and_audit(mock_gdb: MagicMock) -> None:
    driver = MagicMock()
    mock_gdb.driver.return_value = driver
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session

    def _execute_write(fn: object, **kwargs: object) -> object:
        tx = MagicMock()

        def _single() -> dict[str, object]:
            return {"decision_ids": ["dec-1", "dec-2"]}

        def _single_person() -> dict[str, object]:
            return {"deleted": 1}

        tx.run.side_effect = [
            MagicMock(single=_single),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(single=_single_person),
            MagicMock(),
        ]
        return fn(
            tx,
            workspace_id="ws-1",
            person_id="alice@company.com",
            requested_by="admin-1",
            reason="gdpr_right_to_erasure",
            audit_id="audit-123",
        )

    session.execute_write.side_effect = _execute_write

    service = GdprErasureService(uri="bolt://x", user="u", password="p")
    result = service.erase_subject(
        workspace_id="ws-1",
        person_id="alice@company.com",
        requested_by="admin-1",
        caller_roles=["admin"],
    )

    assert result.decisions_deleted == 2
    assert result.person_id == "alice@company.com"
    assert result.requested_by == "admin-1"
    assert result.audit_id


@patch("graph.gdpr.GraphDatabase")
def test_erase_subject_raises_when_person_missing(mock_gdb: MagicMock) -> None:
    driver = MagicMock()
    mock_gdb.driver.return_value = driver
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session

    def _execute_write(fn: object, **kwargs: object) -> object:
        tx = MagicMock()
        tx.run.return_value = MagicMock(single=lambda: None)
        return fn(
            tx,
            workspace_id="ws-1",
            person_id="missing@company.com",
            requested_by="admin-1",
            reason="gdpr_right_to_erasure",
            audit_id="audit-123",
        )

    session.execute_write.side_effect = _execute_write

    service = GdprErasureService(uri="bolt://x", user="u", password="p")
    with pytest.raises(ValueError, match="not found"):
        service.erase_subject(
            workspace_id="ws-1",
            person_id="missing@company.com",
            requested_by="admin-1",
            caller_roles=["legal"],
        )
