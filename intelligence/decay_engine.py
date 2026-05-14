"""Thermodynamic-style relevance decay for Decision nodes (nightly batch).

Architecture: Layer 4 — Intelligence (decay engine).
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import UTC, datetime
from typing import Any

import structlog
from neo4j import GraphDatabase

log = structlog.get_logger(__name__)


def _parse_extracted_at(value: Any) -> datetime | None:
    """Parse Neo4j temporal or ISO string to timezone-aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if hasattr(value, "to_native"):
        native = value.to_native()
        if isinstance(native, datetime):
            if native.tzinfo is None:
                return native.replace(tzinfo=UTC)
            return native.astimezone(UTC)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def run_decay(now: datetime | None = None) -> int:
    """Apply exponential decay to importance_score based on age since extraction."""
    now = now or datetime.now(UTC)
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "cortex_local")
    driver = GraphDatabase.driver(uri, auth=(user, password))

    rows: list[dict[str, Any]] = []
    read_cypher = """
    MATCH (d:Decision)
    WHERE d.status IN ['active', 'under_review']
      AND d.importance_score IS NOT NULL
      AND d.extracted_at IS NOT NULL
    RETURN d.id AS id, d.extracted_at AS ext, d.importance_score AS imp
    """

    with driver.session() as session:
        for record in session.run(read_cypher):
            ext = _parse_extracted_at(record["ext"])
            if ext is None:
                continue
            age_days = max(0.0, (now - ext).total_seconds() / 86400.0)
            new_score = float(record["imp"]) * math.exp(-0.002 * age_days)
            new_score = max(0.05, round(new_score, 4))
            rows.append({"id": record["id"], "imp": new_score})

    with driver.session() as session:
        if rows:
            session.run(
                """
                UNWIND $rows AS row
                MATCH (d:Decision {id: row.id})
                SET d.importance_score = row.imp
                """,
                rows=rows,
            )

    driver.close()
    log.info("decay_engine.complete", updated=len(rows))
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cortex decision decay batch job")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log intent without executing Cypher",
    )
    args = parser.parse_args()
    if args.dry_run:
        log.info("decay_engine.dry_run", message="Would scan Decision nodes and decay scores")
        return
    try:
        run_decay()
    except Exception as exc:
        log.error("decay_engine.failed", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
