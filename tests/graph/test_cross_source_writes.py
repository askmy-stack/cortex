"""Cross-source graph write validation — consistent schema across connectors."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from graph.writer import GraphWriter
from shared.models import DecisionEvent, Provenance

NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
WORKSPACE = "ws-cross-source"


def _decision(
    *,
    source: str,
    author: str,
    system: str,
    event_id: str,
) -> DecisionEvent:
    return DecisionEvent(
        event_id=event_id,
        source_raw_event_id=f"raw-{source}",
        workspace_id=WORKSPACE,
        event_type="decision",
        content=f"Decision from {source}",
        made_by=[author],
        affects=[system],
        rationale=[f"Rationale from {source}"],
        extraction_confidence=0.9,
        importance_score=0.75,
        trust_score=0.8,
        provenance=Provenance(
            source=source,
            channel=f"{source}-channel",
            original_timestamp=NOW,
            extractor_version="0.1.0",
            extractor_model="test",
            verified_by=[],
            raw_event_id=f"raw-{source}",
        ),
        extracted_at=NOW,
    )


def _writer_with_mock_tx() -> tuple[GraphWriter, MagicMock]:
    mock_tx = MagicMock()
    mock_session = MagicMock()
    mock_session.__enter__.return_value = mock_session
    mock_session.__exit__.return_value = False
    mock_session.execute_write.side_effect = lambda fn, **kwargs: fn(mock_tx, **kwargs)
    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session
    with patch("graph.writer.GraphDatabase") as mock_gdb:
        mock_gdb.driver.return_value = mock_driver
        writer = GraphWriter(uri="bolt://x", user="u", password="p")
        writer._driver = mock_driver
    return writer, mock_tx


def test_cross_source_writes_use_workspace_scoped_person_and_system() -> None:
    """Person/System MERGE must always include workspace_id for every connector source."""
    writer, mock_tx = _writer_with_mock_tx()

    sources = [
        ("slack", "alice@co.com", "billing"),
        ("github", "priya", "payments-service"),
        ("jira", "alex@co.com", "billing"),
        ("linear", "dan@co.com", "auth-service"),
    ]
    for source, author, system in sources:
        writer.write(
            _decision(
                source=source,
                author=author,
                system=system,
                event_id=f"dec-{source}",
            )
        )

    person_kwargs = [
        call.kwargs
        for call in mock_tx.run.call_args_list
        if call.args and "MERGE (p:Person" in call.args[0]
    ]
    system_kwargs = [
        call.kwargs
        for call in mock_tx.run.call_args_list
        if call.args and "MERGE (s:System" in call.args[0]
    ]

    assert len(person_kwargs) == 4
    assert len(system_kwargs) == 4
    for kwargs in person_kwargs + system_kwargs:
        assert kwargs["workspace_id"] == WORKSPACE

    decision_kwargs = [
        call.kwargs
        for call in mock_tx.run.call_args_list
        if call.args and "MERGE (d:Decision" in call.args[0]
    ]
    assert len(decision_kwargs) == 4
    for kwargs in decision_kwargs:
        assert kwargs["workspace_id"] == WORKSPACE
        assert kwargs["importance_score"] == 0.75
        assert kwargs["trust_score"] == 0.8
