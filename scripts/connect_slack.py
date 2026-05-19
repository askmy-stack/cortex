#!/usr/bin/env python3
"""Slack connector setup helper for Cortex."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")


def _missing(keys: list[str]) -> list[str]:
    return [key for key in keys if not os.environ.get(key)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Slack connector configuration")
    parser.add_argument(
        "--workspace",
        default=os.environ.get("CORTEX_WORKSPACE_ID", "local-dev"),
        help="Cortex workspace identifier",
    )
    args = parser.parse_args()

    _load_env()
    os.environ["CORTEX_WORKSPACE_ID"] = args.workspace

    required = ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET"]
    missing = _missing(required)
    if missing:
        print("Missing required environment variables:")
        for key in missing:
            print(f"  - {key}")
        print("\nCopy .env.example to .env and add Slack app credentials.")
        return 1

    print("Slack connector configuration looks valid.")
    print(f"Workspace: {args.workspace}")
    print("Webhook URL: http://localhost:8000/webhooks/slack")
    print("Subscribe to message.channels and message.groups in the Slack app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
