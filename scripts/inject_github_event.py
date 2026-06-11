#!/usr/bin/env python3
"""Inject a synthetic GitHub PR event into the Cortex pipeline.

Publishes to ``cortex.raw.github.events`` for the extraction worker to consume.

Usage:
  python scripts/inject_github_event.py --dry-run
  python scripts/inject_github_event.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv

from connectors.github.producer import GitHubKafkaProducer, normalise_github_event

DEFAULT_BODY = (
    "We decided to migrate payments to CockroachDB for multi-region scale "
    "because Postgres failover gaps blocked EU launch."
)
DEFAULT_TITLE = "Decision: migrate payments to CockroachDB"


def build_merged_pr_payload(
    *,
    title: str,
    body: str,
    repo: str,
    number: int = 42,
    user_login: str = "priya",
    updated_at: str = "2026-06-10T18:00:00Z",
    created_at: str = "2026-06-10T17:00:00Z",
    head_ref: str = "feature/decision",
) -> dict:
    """Build a GitHub ``pull_request`` closed+merged webhook payload."""
    return {
        "action": "closed",
        "pull_request": {
            "number": number,
            "title": title,
            "body": body or "",
            "merged": True,
            "merged_at": updated_at,
            "user": {"login": user_login},
            "base": {"ref": "main"},
            "head": {"ref": head_ref},
            "updated_at": updated_at,
            "created_at": created_at,
            "labels": [],
            "requested_reviewers": [],
        },
        "repository": {"full_name": repo, "default_branch": "main"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish a synthetic GitHub PR event to cortex.raw.github.events",
    )
    parser.add_argument("--workspace", default=None, help="Cortex workspace id")
    parser.add_argument("--title", default=DEFAULT_TITLE, help="PR title")
    parser.add_argument("--body", default=DEFAULT_BODY, help="PR body")
    parser.add_argument("--repo", default="acme/payments", help="GitHub repo full name")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print normalised RawEvent JSON without publishing",
    )
    args = parser.parse_args()

    load_dotenv(_REPO / ".env")
    workspace = args.workspace or os.environ.get("CORTEX_WORKSPACE_ID", "local-dev")

    payload = build_merged_pr_payload(title=args.title, body=args.body, repo=args.repo)
    raw_event = normalise_github_event(payload, "pull_request", workspace)
    if raw_event is None:
        print("FAIL: payload did not normalise to a RawEvent", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(json.loads(raw_event.model_dump_json()), indent=2))
        print(f"\nWould publish to cortex.raw.github.events (workspace={workspace!r})")
        return 0

    producer = GitHubKafkaProducer()
    try:
        producer.publish(raw_event)
        producer.flush(timeout=10.0)
    finally:
        producer.close()

    print(f"Published event_id={raw_event.event_id} to cortex.raw.github.events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
