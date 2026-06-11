"""Unit tests for scripts/import_adr_markdown.py (no Neo4j)."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts import import_adr_markdown as iam

SAMPLE_ADR = """# Use Redis for session cache

## Status

Accepted

## Context

In-memory sessions do not survive horizontal scaling.

## Decision

We will store sessions in Redis with a 24h TTL.

## Consequences

Requires Redis cluster in staging and production.
"""


def test_parse_adr_markdown_extracts_sections() -> None:
    parsed = iam.parse_adr_markdown(SAMPLE_ADR, path_key="001-redis.md")
    assert parsed is not None
    assert parsed["title"] == "Use Redis for session cache"
    assert "Redis" in str(parsed["content"])
    assert parsed["event_type"] == "decision"
    assert len(parsed["rationale"]) >= 1


def test_adr_uuid_stable() -> None:
    assert iam.adr_uuid("001-redis.md") == iam.adr_uuid("001-redis.md")
    assert iam.adr_uuid("a") != iam.adr_uuid("b")


def test_build_decision_from_adr_workspace() -> None:
    parsed = iam.parse_adr_markdown(SAMPLE_ADR, path_key="001-redis.md")
    assert parsed is not None
    decision = iam.build_decision_from_adr(parsed, "oss-adr-test", channel="adr/001-redis.md")
    assert decision.workspace_id == "oss-adr-test"
    assert decision.importance_score >= 0.7
    assert decision.provenance.channel == "adr/001-redis.md"


def test_collect_adr_files_single_file(tmp_path: Path) -> None:
    adr = tmp_path / "0001-test.md"
    adr.write_text(SAMPLE_ADR, encoding="utf-8")
    files = iam.collect_adr_files(adr, "*.md")
    assert files == [adr]


def test_collect_adr_files_directory(tmp_path: Path) -> None:
    sub = tmp_path / "adr"
    sub.mkdir()
    (sub / "a.md").write_text(SAMPLE_ADR, encoding="utf-8")
    (sub / "skip.txt").write_text("nope", encoding="utf-8")
    files = iam.collect_adr_files(sub, "*.md")
    assert len(files) == 1
    assert files[0].name == "a.md"
