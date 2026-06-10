#!/usr/bin/env python3
"""Seed Neo4j with demo organizational memory for portfolio demos.

Run after `python -m graph.migrate` (or use scripts/demo.sh).

Uses GraphWriter so Decision nodes match the production schema (RBAC, edges, full-text).
Idempotent: fixed event IDs — safe to re-run.

Scale presets (``--scale``):
  small / startup — 11 base decisions
  mid             — 55 decisions (5×)
  enterprise      — 110 decisions (10×)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:

    def load_dotenv(_path: Path | None = None) -> bool:
        return False

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.demo_catalog import (
    OrgScale,
    SCALE_MULTIPLIERS,
    build_demo_decisions,
    build_primary_decision,
    build_secondary_decision,
    demo_uuid,
)

# Re-export for tests that import from seed_demo.
_demo_uuid = demo_uuid
_build_primary_decision = build_primary_decision
_build_secondary_decision = build_secondary_decision


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Neo4j with Cortex demo decisions")
    parser.add_argument(
        "--workspace",
        default=os.environ.get("CORTEX_WORKSPACE_ID", "local-dev"),
        help="Workspace id stored on Decision nodes (default: env CORTEX_WORKSPACE_ID or local-dev)",
    )
    parser.add_argument(
        "--scale",
        choices=list(SCALE_MULTIPLIERS.keys()),
        default="small",
        help="Org size preset — multiplies base catalog for stress testing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned writes and exit without connecting to Neo4j",
    )
    args = parser.parse_args()

    load_dotenv(_REPO / ".env")
    scale: OrgScale = args.scale  # type: ignore[assignment]
    decisions = build_demo_decisions(args.workspace, scale=scale)

    if args.dry_run:
        print(f"Dry run — would write {len(decisions)} decisions (scale={scale}):")
        for d in decisions[:5]:
            print(f"  - {d.event_id}: {d.content[:72]}...")
        if len(decisions) > 5:
            print(f"  ... and {len(decisions) - 5} more")
        return 0

    from graph.writer import GraphWriter
    from memory.quarantine import persist_quarantine
    from scoring.write_pipeline import DecisionScoringPipeline, write_reject_reason

    scoring = DecisionScoringPipeline()
    writer = GraphWriter()
    written: list[str] = []
    skipped = 0
    try:
        for decision in decisions:
            scoring.score(decision)
            reject = write_reject_reason(decision)
            if reject is not None:
                persist_quarantine(decision, reject)
                skipped += 1
                continue
            written.append(writer.write(decision))
    finally:
        writer.close()

    print(f"Demo seed complete for workspace={args.workspace!r} scale={scale!r}")
    print(f"  Wrote {len(written)} decisions")
    if skipped:
        print(f"  Skipped {skipped} decisions (importance/trust thresholds)")
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
