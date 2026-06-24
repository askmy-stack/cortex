#!/usr/bin/env python3
"""Seed oss-tiangolo-fastapi workspace with FastAPI-themed demo decisions.

Use when GitHub import (import_github_graph.py) is unavailable — e.g. cloud
Neo4j without Kafka or without GitHub token. Idempotent via deterministic UUIDs.

Usage:
  python scripts/seed_oss_fastapi_demo.py
  python scripts/seed_oss_fastapi_demo.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv

from scripts.demo_catalog import _spec, build_decision_from_spec

WORKSPACE = "oss-tiangolo-fastapi"

_OSS_SPECS: list[dict[str, object]] = [
    _spec(
        "oss-async-deps",
        source="github",
        channel="pull_request",
        content="Adopt async dependency injection pattern for database sessions in FastAPI routers.",
        made_by=["person:tiangolo"],
        affects=["system:fastapi-core"],
        rationale=["Aligns with ASGI concurrency model; reduces thread pool pressure."],
        importance=0.72,
        trust=0.8,
    ),
    _spec(
        "oss-openapi-3-1",
        source="github",
        channel="pull_request",
        content="Standardize on OpenAPI 3.1 schema generation for all public FastAPI examples.",
        made_by=["person:tiangolo"],
        affects=["system:fastapi-docs", "system:openapi-generator"],
        rationale=["Improves SDK compatibility for downstream API clients."],
        importance=0.74,
        trust=0.82,
    ),
    _spec(
        "oss-pydantic-v2",
        source="github",
        channel="issue_comment",
        content="Migrate validation layer to Pydantic v2 with model_config instead of Config class.",
        made_by=["person:tiangolo"],
        affects=["system:fastapi-core"],
        rationale=["Performance gains and parity with ecosystem tooling."],
        importance=0.76,
        trust=0.83,
    ),
    _spec(
        "oss-starlette-pin",
        source="github",
        channel="pull_request",
        content="Pin Starlette minor version in release branches to avoid breaking middleware hooks.",
        made_by=["person:tiangolo"],
        affects=["system:fastapi-core", "system:starlette"],
        rationale=["Prevents surprise regressions in long-lived LTS installs."],
        importance=0.7,
        trust=0.79,
    ),
    _spec(
        "oss-security-defaults",
        source="github",
        channel="pull_request",
        content="Enable secure cookie defaults and document HTTPS requirements in deployment guides.",
        made_by=["person:tiangolo"],
        affects=["system:fastapi-docs", "system:fastapi-security"],
        rationale=["Reduces misconfiguration in production deployments."],
        importance=0.78,
        trust=0.85,
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed oss-tiangolo-fastapi demo workspace")
    parser.add_argument("--workspace", default=WORKSPACE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv(_REPO / ".env")
    decisions = [build_decision_from_spec(spec, args.workspace) for spec in _OSS_SPECS]

    if args.dry_run:
        print(f"Dry run — would write {len(decisions)} decisions to {args.workspace!r}")
        for d in decisions:
            print(f"  - {d.event_id}: {d.content[:64]}...")
        return 0

    from graph.writer import GraphWriter
    from memory.quarantine import persist_quarantine
    from scoring.write_pipeline import DecisionScoringPipeline, write_reject_reason

    scoring = DecisionScoringPipeline()
    writer = GraphWriter()
    written: list[str] = []
    try:
        for decision in decisions:
            scoring.score(decision)
            reject = write_reject_reason(decision)
            if reject is not None:
                persist_quarantine(decision, reject)
                continue
            written.append(writer.write(decision))
    finally:
        writer.close()

    print(f"OSS seed complete for workspace={args.workspace!r}: {len(written)} decisions")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
