#!/usr/bin/env python3
"""Seed Neo4j with demo organizational memory for portfolio demos.

Run after `python -m graph.migrate` (or use scripts/demo.sh).

Uses GraphWriter so Decision nodes match the production schema (RBAC, edges, full-text).
Idempotent: fixed event IDs — safe to re-run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(_path: Path | None = None) -> bool:
        return False

# Repo root on sys.path for `python scripts/seed_demo.py`
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from shared.models import DecisionEvent, Provenance


def _demo_uuid(name: str) -> str:
    """Deterministic UUID for idempotent MERGE."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"cortex.demo:{name}"))


def _build_primary_decision(workspace_id: str) -> DecisionEvent:
    now = datetime.now(UTC)
    raw_id = _demo_uuid("raw-cockroach")
    return DecisionEvent(
        event_id=_demo_uuid("decision-cockroach"),
        source_raw_event_id=raw_id,
        workspace_id=workspace_id,
        event_type="decision",
        content=(
            "We decided to migrate the payments service from PostgreSQL to CockroachDB "
            "for multi-region active-active replication and predictable scale past 10M txn/day."
        ),
        made_by=["priya@acme.example", "dan@acme.example"],
        affects=["payments-service", "billing-service"],
        rationale=[
            "Incident #247 showed Postgres failover gaps in eu-west.",
            "Finance signed off on incremental infra cost for HA.",
        ],
        triggered_by="incident-247",
        extraction_confidence=0.92,
        importance_score=0.88,
        trust_score=0.82,
        provenance=Provenance(
            source="slack",
            channel="C-architecture",
            original_timestamp=now,
            extractor_version="demo-seed",
            extractor_model="seed-script",
            verified_by=[],
            raw_event_id=raw_id,
        ),
        extracted_at=now,
    )


def _build_secondary_decision(workspace_id: str) -> DecisionEvent:
    """Optional second decision (related context, same workspace)."""
    now = datetime.now(UTC)
    raw_id = _demo_uuid("raw-cache")
    return DecisionEvent(
        event_id=_demo_uuid("decision-cache"),
        source_raw_event_id=raw_id,
        workspace_id=workspace_id,
        event_type="decision",
        content=(
            "We standardized on Redis Cluster for hot payment session state with TTL-based "
            "eviction; Postgres remains system of record for balances."
        ),
        made_by=["ops@acme.example"],
        affects=["payments-service"],
        rationale=["Sub-10ms p99 for session reads during checkout."],
        extraction_confidence=0.88,
        importance_score=0.72,
        trust_score=0.78,
        provenance=Provenance(
            source="github",
            channel="acme/payments-platform",
            original_timestamp=now,
            extractor_version="demo-seed",
            extractor_model="seed-script",
            verified_by=[],
            raw_event_id=raw_id,
        ),
        extracted_at=now,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Neo4j with Cortex demo decisions")
    parser.add_argument(
        "--workspace",
        default=os.environ.get("CORTEX_WORKSPACE_ID", "local-dev"),
        help="Workspace id stored on Decision nodes (default: env CORTEX_WORKSPACE_ID or local-dev)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned writes and exit without connecting to Neo4j",
    )
    args = parser.parse_args()

    load_dotenv(_REPO / ".env")

    primary = _build_primary_decision(args.workspace)
    secondary = _build_secondary_decision(args.workspace)

    if args.dry_run:
        print("Dry run — would write:")
        print(f"  - {primary.event_id}: {primary.content[:80]}...")
        print(f"  - {secondary.event_id}: {secondary.content[:80]}...")
        return 0

    from graph.writer import GraphWriter

    writer = GraphWriter()
    try:
        w1 = writer.write(primary)
        w2 = writer.write(secondary)
    finally:
        writer.close()

    print(f"Demo seed complete for workspace={args.workspace!r}")
    print(f"  Decision event_ids: {w1!r}, {w2!r}")
    sample = json.dumps(
        {
            "query": "Why CockroachDB payments?",
            "workspace_id": args.workspace,
            "limit": 5,
        }
    )
    print("  Try query: POST /query with body", sample)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
