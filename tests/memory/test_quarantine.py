"""Tests for memory/quarantine.py."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from memory.quarantine import persist_quarantine
from shared.models import DecisionEvent, Provenance

NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def _decision() -> DecisionEvent:
    return DecisionEvent(
        source_raw_event_id="raw-1",
        workspace_id="ws-1",
        event_type="decision",
        content="We decided to migrate payments to CockroachDB.",
        made_by=["alice@company.com"],
        affects=["payments-service"],
        rationale=["Scale ceiling"],
        extraction_confidence=0.9,
        importance_score=0.75,
        trust_score=0.1,
        provenance=Provenance(
            source="slack",
            channel="C-engineering",
            original_timestamp=NOW,
            extractor_version="0.1.0",
            extractor_model="gpt-4o",
            verified_by=[],
            raw_event_id="raw-1",
        ),
        extracted_at=NOW,
    )


@patch("memory.quarantine._timescale_dsn", return_value=None)
def test_persist_quarantine_noop_without_dsn(_dsn: object) -> None:
    persist_quarantine(_decision(), "trust_quarantine")


@patch("memory.quarantine.asyncio.run")
@patch("memory.quarantine._timescale_dsn", return_value="postgresql://x")
def test_persist_quarantine_calls_async_when_dsn_set(
    _dsn: object,
    run_mock: object,
) -> None:
    persist_quarantine(_decision(), "cmvk_disagreement")
    run_mock.assert_called_once()
