"""Confidence aggregation for reliability gate."""

from __future__ import annotations

from typing import Any


def memory_confidence_from_claims(claims: list[dict[str, Any]]) -> float:
    """Aggregate memory confidence from claim payloads."""
    if not claims:
        return 0.0
    scores = [float(c.get("confidence") or 0.0) for c in claims]
    return sum(scores) / len(scores)


def action_confidence(
    *,
    memory_conf: float,
    risk_penalty: float,
    conflict_penalty: float,
    auth_ok: bool,
) -> float:
    """Derive action confidence from memory conf and penalties."""
    if not auth_ok:
        return min(memory_conf, 0.15)
    value = memory_conf - risk_penalty - conflict_penalty
    return max(0.0, min(1.0, value))
