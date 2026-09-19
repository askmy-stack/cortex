"""Knowledge gap detection and coverage estimates."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from shared.v2_models import KnowledgeGap

_GAPS: dict[str, KnowledgeGap] = {}


def coverage_score(*, claim_count: int, expected_min: int = 3) -> float:
    """Simple domain coverage estimate in [0, 1]."""
    if expected_min <= 0:
        return 1.0
    return max(0.0, min(1.0, claim_count / float(expected_min)))


def maybe_abstain(
    *,
    memory_confidence: float,
    coverage: float,
    missing: list[str] | None = None,
) -> dict[str, Any] | None:
    """Return abstention payload when evidence is insufficient."""
    if memory_confidence >= 0.45 and coverage >= 0.5:
        return None
    return {
        "status": "INSUFFICIENT_EVIDENCE",
        "memory_confidence": memory_confidence,
        "coverage": coverage,
        "missing": missing or [],
        "next_action": "ASK",
    }


def record_gap(
    *,
    workspace_id: str,
    domain: str,
    gap_type: str,
    description: str,
    coverage: float,
) -> KnowledgeGap:
    """Create or bump a knowledge gap for repeated abstentions."""
    key = f"{workspace_id}:{domain}:{gap_type}"
    existing = _GAPS.get(key)
    now = datetime.now(UTC)
    if existing:
        existing.frequency += 1
        existing.last_seen = now
        existing.coverage_score = coverage
        existing.description = description
        return existing
    gap = KnowledgeGap(
        workspace_id=workspace_id,
        domain=domain,
        gap_type=gap_type,
        description=description,
        coverage_score=coverage,
        first_seen=now,
        last_seen=now,
    )
    _GAPS[key] = gap
    return gap


def get_gaps(workspace_id: str) -> list[KnowledgeGap]:
    return [g for g in _GAPS.values() if g.workspace_id == workspace_id]
