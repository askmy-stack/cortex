"""Unit tests for scripts/seed_demo.py (no Neo4j)."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts import seed_demo as sd


def test_demo_uuid_stable() -> None:
    assert sd._demo_uuid("x") == sd._demo_uuid("x")
    assert sd._demo_uuid("a") != sd._demo_uuid("b")


def test_primary_decision_fields() -> None:
    d = sd._build_primary_decision("ws-test")
    assert d.workspace_id == "ws-test"
    assert "CockroachDB" in d.content
    assert d.importance_score >= 0.8
    assert d.trust_score >= 0.7
    assert d.made_by
    assert d.affects


def test_secondary_decision_writable_scores() -> None:
    d = sd._build_secondary_decision("ws-test")
    from scoring.trust_scorer import is_writable

    assert is_writable(d.trust_score)
