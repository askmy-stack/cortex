#!/usr/bin/env python3
"""Inject a synthetic Jira comment event into the Cortex pipeline.

Publishes to ``cortex.raw.jira.events`` for the extraction worker to consume.

Usage:
  python scripts/inject_jira_event.py --dry-run
  python scripts/inject_jira_event.py
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

from connectors.jira.producer import JiraKafkaProducer, normalise_jira_event

DEFAULT_COMMENT = (
    "We decided to adopt event sourcing for billing because audit requirements "
    "blocked the monolith release."
)


def build_comment_payload(*, comment: str, issue_key: str, project_key: str) -> dict:
    """Build a Jira ``jira:issue_commented`` webhook payload."""
    return {
        "webhookEvent": "jira:issue_commented",
        "issue": {
            "key": issue_key,
            "fields": {
                "summary": "Billing architecture decision",
                "project": {"key": project_key},
            },
        },
        "comment": {
            "id": "10001",
            "body": comment,
            "created": "2026-06-10T18:00:00.000+0000",
            "author": {"displayName": "Alex Chen", "accountId": "demo-user"},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish a synthetic Jira comment to cortex.raw.jira.events",
    )
    parser.add_argument("--workspace", default=None, help="Cortex workspace id")
    parser.add_argument("--comment", default=DEFAULT_COMMENT, help="Comment body")
    parser.add_argument("--issue", default="ENG-123", help="Jira issue key")
    parser.add_argument("--project", default="ENG", help="Jira project key")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print normalised RawEvent JSON without publishing",
    )
    args = parser.parse_args()

    load_dotenv(_REPO / ".env")
    workspace = args.workspace or os.environ.get("CORTEX_WORKSPACE_ID", "local-dev")

    payload = build_comment_payload(
        comment=args.comment,
        issue_key=args.issue,
        project_key=args.project,
    )
    raw_event = normalise_jira_event(payload, "jira:issue_commented", workspace)
    if raw_event is None:
        print("FAIL: payload did not normalise to a RawEvent", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(json.loads(raw_event.model_dump_json()), indent=2))
        print(f"\nWould publish to cortex.raw.jira.events (workspace={workspace!r})")
        return 0

    producer = JiraKafkaProducer()
    try:
        producer.publish(raw_event)
        producer.flush(timeout=10.0)
    finally:
        producer.close()

    print(f"Published event_id={raw_event.event_id} to cortex.raw.jira.events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
