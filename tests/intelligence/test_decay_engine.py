"""Tests for intelligence/decay_engine."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from intelligence.decay_engine import _parse_extracted_at, run_decay


def test_parse_extracted_at_iso_string() -> None:
    dt = _parse_extracted_at("2026-05-11T12:00:00+00:00")
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_extracted_at_datetime() -> None:
    raw = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
    assert _parse_extracted_at(raw) == raw


@patch("intelligence.decay_engine.GraphDatabase.driver")
def test_run_decay_batches_updates(mock_driver: MagicMock) -> None:
    session = MagicMock()

    class Rec:
        def __getitem__(self, key: str) -> object:
            return {"id": "d1", "ext": "2026-05-01T00:00:00+00:00", "imp": 0.8}[key]

    session.run.side_effect = [iter([Rec()]), MagicMock()]

    cm = MagicMock()
    cm.__enter__.return_value = session
    cm.__exit__.return_value = False
    mock_driver.return_value.session.return_value = cm

    updated = run_decay(now=datetime(2026, 5, 11, tzinfo=UTC))
    assert updated == 1
    assert session.run.call_count == 2
    mock_driver.return_value.close.assert_called_once()
