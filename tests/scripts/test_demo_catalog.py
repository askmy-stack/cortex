"""Tests for expanded demo catalog and org-scale stress presets."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.demo_catalog import (
    BASE_DECISION_SPECS,
    SCALE_MULTIPLIERS,
    build_demo_decisions,
    demo_uuid,
)


def test_base_catalog_at_least_five_x_original() -> None:
    """Original seed had 2 decisions; catalog must be ≥10 (5×)."""
    assert len(BASE_DECISION_SPECS) >= 10


def test_sources_cover_organizational_channels() -> None:
    sources = {str(s["source"]) for s in BASE_DECISION_SPECS}
    assert "slack" in sources
    assert "github" in sources
    assert "meeting" in sources
    assert "manual" in sources
    assert "cicd" in sources


def test_scale_mid_is_five_x_base() -> None:
    base = len(build_demo_decisions("ws", scale="small"))
    mid = len(build_demo_decisions("ws", scale="mid"))
    assert mid == base * SCALE_MULTIPLIERS["mid"]
    assert mid >= 50


def test_scale_enterprise_is_ten_x_base() -> None:
    base = len(build_demo_decisions("ws", scale="small"))
    ent = len(build_demo_decisions("ws", scale="enterprise"))
    assert ent == base * SCALE_MULTIPLIERS["enterprise"]


def test_decision_ids_stable_per_workspace() -> None:
    a = build_demo_decisions("ws-a", scale="small")
    b = build_demo_decisions("ws-a", scale="small")
    assert [d.event_id for d in a] == [d.event_id for d in b]


def test_workspace_isolation_in_payload() -> None:
    a = build_demo_decisions("ws-a", scale="small")[0]
    b = build_demo_decisions("ws-b", scale="small")[0]
    assert a.event_id == b.event_id
    assert a.workspace_id != b.workspace_id


def test_contradiction_spec_has_replaces() -> None:
    contradictory = [s for s in BASE_DECISION_SPECS if s.get("replaces")]
    assert len(contradictory) >= 1


def test_demo_uuid_stable() -> None:
    assert demo_uuid("x") == demo_uuid("x")
    assert demo_uuid("a") != demo_uuid("b")
