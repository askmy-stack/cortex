"""Configurable source-authority policy for Evidence Graph."""

from __future__ import annotations

import json
import os
from typing import Any

from shared.v2_models import AuthorityClass

# Default ordering: higher = more authoritative (do not hardcode without tests).
DEFAULT_AUTHORITY_SCORES: dict[str, float] = {
    "formal_policy": 0.98,
    "approved_ADR": 0.95,
    "production_state": 0.90,
    "merged_PR": 0.82,
    "approved_ticket": 0.75,
    "incident_record": 0.78,
    "verified_human_statement": 0.65,
    "casual_chat": 0.45,
    "agent_inference": 0.35,
    "external_unverified": 0.25,
}


def load_authority_scores() -> dict[str, float]:
    """Load authority scores from CORTEX_AUTHORITY_SCORES_JSON or defaults."""
    raw = os.environ.get("CORTEX_AUTHORITY_SCORES_JSON", "").strip()
    if not raw:
        return dict(DEFAULT_AUTHORITY_SCORES)
    try:
        parsed: dict[str, Any] = json.loads(raw)
        out = dict(DEFAULT_AUTHORITY_SCORES)
        for key, value in parsed.items():
            out[str(key)] = float(value)
        return out
    except (json.JSONDecodeError, TypeError, ValueError):
        return dict(DEFAULT_AUTHORITY_SCORES)


def score_for_class(authority_class: AuthorityClass | str) -> float:
    """Return configured authority score for a class."""
    scores = load_authority_scores()
    return float(scores.get(str(authority_class), 0.30))


def compare_authority(a: str, b: str) -> int:
    """Return 1 if a > b, -1 if a < b, 0 if equal."""
    sa, sb = score_for_class(a), score_for_class(b)
    if sa > sb:
        return 1
    if sa < sb:
        return -1
    return 0
