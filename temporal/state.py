"""Temporal state queries over Claim nodes."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from neo4j import Driver, GraphDatabase

from temporal.validity import is_valid_at, parse_utc, rank_key

_CLAIMS_FOR_ENTITY = """
MATCH (c:Claim)
WHERE c.workspace_id = $workspace_id
  AND (c.subject = $entity OR c.object = $entity OR c.decision_id = $entity)
RETURN c {
  .id, .subject, .predicate, .object, .content, .confidence, .status,
  .valid_from, .valid_to, .observed_at, .invalidated_at, .superseded_by,
  .assertion_type, .decision_id
} AS claim
"""


class TemporalStateService:
    """Query current or historical claim state for an entity."""

    def __init__(self, driver: Driver | None = None) -> None:
        self._owns = driver is None
        if driver is None:
            uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
            user = os.environ.get("NEO4J_USER", "neo4j")
            password = os.environ.get("NEO4J_PASSWORD", "cortex_local")
            self._driver = GraphDatabase.driver(uri, auth=(user, password))
        else:
            self._driver = driver

    def state_at(
        self,
        *,
        entity: str,
        workspace_id: str,
        at: datetime | None = None,
        current_only: bool = False,
    ) -> dict[str, Any]:
        """Return claims for entity filtered/ranked for timestamp `at`."""
        at = at or datetime.now(UTC)
        with self._driver.session() as session:
            rows = list(
                session.run(
                    _CLAIMS_FOR_ENTITY,
                    workspace_id=workspace_id,
                    entity=entity,
                )
            )
        claims = [dict(r["claim"]) for r in rows if r.get("claim")]
        if current_only:
            claims = [
                c
                for c in claims
                if is_valid_at(
                    status=str(c.get("status") or ""),
                    valid_from=c.get("valid_from"),
                    valid_to=c.get("valid_to"),
                    at=at,
                )
                and str(c.get("status")) not in {"SUPERSEDED", "ARCHIVED"}
            ]
        else:
            # Historical: include claims whose validity window covers `at`
            claims = [
                c
                for c in claims
                if is_valid_at(
                    status=str(c.get("status") or ""),
                    valid_from=c.get("valid_from"),
                    valid_to=c.get("valid_to"),
                    at=at,
                )
                or (
                    # include superseded that were still open at `at` via valid_from
                    parse_utc(c.get("valid_from")) is not None
                    and parse_utc(c.get("valid_from")) <= at  # type: ignore[operator]
                    and (
                        parse_utc(c.get("valid_to")) is None
                        or parse_utc(c.get("valid_to")) > at  # type: ignore[operator]
                    )
                    and str(c.get("status")) == "SUPERSEDED"
                )
            ]
        claims.sort(key=lambda c: rank_key(c, at=at), reverse=True)
        return {
            "entity": entity,
            "workspace_id": workspace_id,
            "at": at.isoformat(),
            "mode": "current" if current_only else "historical",
            "claims": claims,
            "total": len(claims),
        }

    def close(self) -> None:
        if self._owns:
            self._driver.close()
