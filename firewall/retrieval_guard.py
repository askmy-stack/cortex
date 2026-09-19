"""Retrieval-side integrity checks."""

from __future__ import annotations

from typing import Any


def filter_safe_memories(memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop quarantined / instruction-like memories from injection context."""
    safe: list[dict[str, Any]] = []
    for m in memories:
        status = str(m.get("status") or "").upper()
        if status in {"QUARANTINED", "ERASED"}:
            continue
        content = str(m.get("content") or "")
        if "ignore previous instructions" in content.lower():
            continue
        safe.append(m)
    return safe
