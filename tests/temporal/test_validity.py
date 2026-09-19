"""Tests for temporal validity and ranking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from temporal.validity import is_valid_at, rank_key


def test_active_claim_valid_now() -> None:
    now = datetime.now(UTC)
    assert is_valid_at(
        status="ACTIVE",
        valid_from=now - timedelta(days=10),
        valid_to=None,
        at=now,
    )


def test_ended_claim_not_valid() -> None:
    now = datetime.now(UTC)
    assert not is_valid_at(
        status="ACTIVE",
        valid_from=now - timedelta(days=30),
        valid_to=now - timedelta(days=1),
        at=now,
    )


def test_quarantined_never_valid() -> None:
    now = datetime.now(UTC)
    assert not is_valid_at(
        status="QUARANTINED",
        valid_from=None,
        valid_to=None,
        at=now,
    )


def test_ranking_prefers_active_over_superseded() -> None:
    now = datetime.now(UTC)
    active = {"id": "a", "status": "ACTIVE", "confidence": 0.5}
    superseded = {"id": "s", "status": "SUPERSEDED", "confidence": 0.99}
    assert rank_key(active, at=now) > rank_key(superseded, at=now)
