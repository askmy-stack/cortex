#!/usr/bin/env python3
"""Inject a synthetic Slack decision message into the Cortex pipeline.

Publishes to ``cortex.raw.slack.messages`` for the extraction worker to consume.
Use for local dev without configuring a public Slack webhook tunnel.

Usage:
  python scripts/inject_slack_message.py --dry-run
  python scripts/inject_slack_message.py
  python scripts/inject_slack_message.py --text "We decided to use Kafka for the event bus."
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv

from connectors.slack.producer import SlackKafkaProducer, normalise_slack_event

DEFAULT_TEXT = (
    "We decided to migrate payments to CockroachDB for multi-region scale "
    "because Postgres failover gaps blocked EU launch."
)


def build_slack_payload(
    *,
    text: str,
    channel: str,
    user: str,
    team_id: str,
) -> dict:
    """Build a Slack Events API ``event_callback`` payload."""
    ts = f"{time.time():.6f}"
    return {
        "type": "event_callback",
        "team_id": team_id,
        "event": {
            "type": "message",
            "user": user,
            "text": text,
            "channel": channel,
            "ts": ts,
            "channel_type": "channel",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish a synthetic Slack message to cortex.raw.slack.messages",
    )
    parser.add_argument("--workspace", default=None, help="Cortex workspace id")
    parser.add_argument("--text", default=DEFAULT_TEXT, help="Message body")
    parser.add_argument("--channel", default="C-engineering", help="Slack channel id")
    parser.add_argument("--user", default="U-demo-user", help="Slack user id")
    parser.add_argument("--team", default="T-demo", help="Slack team id")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print normalised RawEvent JSON without publishing",
    )
    args = parser.parse_args()

    load_dotenv(_REPO / ".env")
    workspace = args.workspace or os.environ.get("CORTEX_WORKSPACE_ID", "local-dev")

    payload = build_slack_payload(
        text=args.text,
        channel=args.channel,
        user=args.user,
        team_id=args.team,
    )
    raw_event = normalise_slack_event(payload, workspace)
    if raw_event is None:
        print("FAIL: payload did not normalise to a RawEvent", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(json.loads(raw_event.model_dump_json()), indent=2))
        print(f"\nWould publish to cortex.raw.slack.messages (workspace={workspace!r})")
        return 0

    producer = SlackKafkaProducer()
    try:
        producer.publish(raw_event)
        producer.flush(timeout=10.0)
    finally:
        producer.close()

    print(f"Published event_id={raw_event.event_id} to cortex.raw.slack.messages")
    print("Watch pipeline-worker logs for extractor.decision_extracted / graph.write.success")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
