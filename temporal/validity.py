"""Temporal validity helpers — current vs historical claim state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def parse_utc(value: Any) -> datetime | None:
    """Parse ISO / Neo4j temporal to timezone-aware UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if hasattr(value, "to_native"):
        native = value.to_native()
        if isinstance(native, datetime):
            return parse_utc(native)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def is_valid_at(
    *,
    status: str,
    valid_from: Any,
    valid_to: Any,
    at: datetime,
) -> bool:
    """Return True if claim is temporally valid at timestamp `at`."""
    if status in {"QUARANTINED", "ERASED"}:
        return False
    start = parse_utc(valid_from)
    end = parse_utc(valid_to)
    if start and at < start:
        return False
    if end and at >= end:
        return False
    return True


def rank_key(claim: dict[str, Any], *, at: datetime) -> tuple[int, float, str]:
    """Sort key for current-state ranking (higher better via reverse sort)."""
    status = str(claim.get("status") or "")
    valid = is_valid_at(
        status=status,
        valid_from=claim.get("valid_from"),
        valid_to=claim.get("valid_to"),
        at=at,
    )
    status_rank = {
        "VERIFIED": 5,
        "ACTIVE": 4,
        "CHALLENGED": 3,
        "CANDIDATE": 2,
        "SUPERSEDED": 1,
        "ARCHIVED": 0,
    }.get(status, 0)
    if not valid:
        status_rank = -1
    conf = float(claim.get("confidence") or 0.0)
    return (status_rank, conf, str(claim.get("id") or ""))
