#!/usr/bin/env python3
"""Import merged GitHub PRs directly into Neo4j (no Kafka).

Use for cloud demos where pipeline-worker is not deployed. Fetches PRs from
the GitHub REST API, normalises to RawEvent, extracts decisions, scores, and
writes via GraphWriter — same path as the extraction worker minus Kafka.

Usage:
  python scripts/import_github_graph.py --org tiangolo --repo fastapi --dry-run
  python scripts/import_github_graph.py --org tiangolo --repo fastapi \\
      --workspace oss-tiangolo-fastapi --limit 30
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv

from connectors.github.producer import normalise_github_event
from extraction.decision_extractor import DecisionExtractor
from graph.writer import GraphWriter
from memory.quarantine import persist_quarantine
from scoring.write_pipeline import DecisionScoringPipeline, write_reject_reason
from scripts.import_github_org import (
    fetch_merged_prs,
    is_decision_like,
    pr_to_payload,
)
from shared.models import RawEvent


def _process_event(
    raw: RawEvent,
    *,
    extractor: DecisionExtractor,
    scoring: DecisionScoringPipeline,
    writer: GraphWriter,
) -> str | None:
    """Extract, score, and write one raw event; return decision id or None."""
    decision = extractor.extract(raw)
    if decision is None:
        return None
    scoring.score(decision)
    reject = write_reject_reason(decision)
    if reject is not None:
        persist_quarantine(decision, reject)
        return None
    try:
        return writer.write(decision)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import merged GitHub PRs directly into Neo4j",
    )
    parser.add_argument("--org", required=True, help="GitHub org or user")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument(
        "--workspace",
        default=None,
        help="Cortex workspace id (default: oss-<org>-<repo>)",
    )
    parser.add_argument("--limit", type=int, default=30, help="Max merged PRs to fetch")
    parser.add_argument(
        "--all-merged",
        action="store_true",
        help="Import all merged PRs (default: decision-like PRs only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned RawEvents without writing to Neo4j",
    )
    args = parser.parse_args()

    load_dotenv(_REPO / ".env")
    workspace = args.workspace or f"oss-{args.org}-{args.repo}"
    repo_full = f"{args.org}/{args.repo}"
    decision_only = not args.all_merged

    print(f"Fetching merged PRs from {repo_full} (limit={args.limit})…")
    prs = fetch_merged_prs(args.org, args.repo, limit=args.limit)
    if decision_only:
        prs = [pr for pr in prs if is_decision_like(pr)]

    print(f"Selected {len(prs)} pull request(s) for workspace={workspace!r}")

    raw_events: list[RawEvent] = []
    for pr in prs:
        payload = pr_to_payload(pr, repo_full)
        raw = normalise_github_event(payload, "pull_request", workspace)
        if raw is not None:
            raw_events.append(raw)

    if args.dry_run:
        for raw in raw_events[:5]:
            print(json.dumps(json.loads(raw.model_dump_json()), indent=2)[:500], "…")
        if len(raw_events) > 5:
            print(f"… and {len(raw_events) - 5} more")
        print(f"\nDry run — would process {len(raw_events)} event(s) into Neo4j")
        return 0

    if not raw_events:
        print("No events to import.", file=sys.stderr)
        return 1

    extractor = DecisionExtractor()
    scoring = DecisionScoringPipeline()
    writer = GraphWriter()
    written: list[str] = []
    skipped = 0
    try:
        for raw in raw_events:
            event_id = _process_event(
                raw,
                extractor=extractor,
                scoring=scoring,
                writer=writer,
            )
            if event_id:
                written.append(event_id)
            else:
                skipped += 1
    finally:
        writer.close()

    print(f"Import complete for workspace={workspace!r}")
    print(f"  Wrote {len(written)} decisions")
    if skipped:
        print(f"  Skipped {skipped} events (no extract / below threshold / quarantine)")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
