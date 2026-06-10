#!/usr/bin/env python3
"""Inject a synthetic Linear issue comment into the Cortex pipeline.

Publishes to ``cortex.raw.linear.events`` for the extraction worker to consume.

Usage:
  python scripts/inject_linear_event.py --dry-run
  python scripts/inject_linear_event.py
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

from connectors.linear.producer import LinearKafkaProducer, normalise_linear_event

DEFAULT_BODY = (
    "We decided to adopt event sourcing for billing because audit requirements "
    "blocked the monolith release."
)


def build_comment_payload(*, body: str, issue_id: str, identifier: str, team: str) -> dict:
    """Build a Linear Comment create webhook payload."""
    return {
        "type": "Comment",
        "action": "create",
        "data": {
            "id": "comment-demo-1",
            "body": body,
            "createdAt": "2026-06-10T18:00:00Z",
            "user": {"email": "alex@company.com"},
            "issue": {
                "id": issue_id,
                "identifier": identifier,
                "team": {"key": team},
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish a synthetic Linear comment to cortex.raw.linear.events",
    )
    parser.add_argument("--workspace", default=None, help="Cortex workspace id")
    parser.add_argument("--body", default=DEFAULT_BODY, help="Comment body")
    parser.add_argument("--issue-id", default="issue-linear-1", help="Linear issue id")
    parser.add_argument("--identifier", default="ENG-42", help="Linear issue identifier")
    parser.add_argument("--team", default="ENG", help="Linear team key")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print normalised RawEvent JSON without publishing",
    )
    args = parser.parse_args()

    load_dotenv(_REPO / ".env")
    workspace = args.workspace or os.environ.get("CORTEX_WORKSPACE_ID", "local-dev")

    payload = build_comment_payload(
        body=args.body,
        issue_id=args.issue_id,
        identifier=args.identifier,
        team=args.team,
    )
    raw_event = normalise_linear_event(payload, workspace)
    if raw_event is None:
        print("FAIL: payload did not normalise to a RawEvent", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(json.loads(raw_event.model_dump_json()), indent=2))
        print(f"\nWould publish to cortex.raw.linear.events (workspace={workspace!r})")
        return 0

    producer = LinearKafkaProducer()
    try:
        producer.publish(raw_event)
        producer.flush(timeout=10.0)
    finally:
        producer.close()

    print(f"Published event_id={raw_event.event_id} to cortex.raw.linear.events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
