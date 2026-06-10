#!/usr/bin/env python3
"""Verify the Slack → Kafka → extract → Neo4j pipeline end-to-end.

Prerequisites:
  - `make stack` or `docker compose --profile api up -d`
  - Ollama running on the host with the configured model pulled
  - After code changes: `make pipeline-restart` (seconds) — not `docker compose build`

Usage:
  python scripts/verify_slack_pipeline.py --dry-run
  python scripts/verify_slack_pipeline.py
  python scripts/verify_slack_pipeline.py --timeout 180
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv
from neo4j import GraphDatabase

_INJECT = _REPO / "scripts" / "inject_slack_message.py"


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_ollama(*, base_url: str, model: str) -> tuple[bool, str]:
    """Return (ok, message) after confirming Ollama serves the requested model."""
    try:
        payload = _fetch_json(f"{base_url.rstrip('/')}/api/tags")
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        return False, f"Ollama unreachable at {base_url}: {exc}"

    names = {item.get("name", "") for item in payload.get("models", [])}
    if model in names:
        return True, f"Ollama model {model!r} available"

    # Allow unpinned tags, e.g. llama3.1:8b vs llama3.1:8b-instruct
    prefix = model.split(":")[0] + ":"
    matches = sorted(n for n in names if n.startswith(prefix))
    if matches:
        return True, f"Ollama has {matches[0]!r} (requested {model!r})"

    return False, f"Model {model!r} not in Ollama tags: {sorted(names)}"


def count_decisions(
    *,
    uri: str,
    user: str,
    password: str,
    workspace: str,
) -> int:
    """Count Decision nodes for a workspace in Neo4j."""
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        with driver.session() as session:
            record = session.run(
                """
                MATCH (d:Decision {workspace_id: $workspace})
                RETURN count(d) AS c
                """,
                workspace=workspace,
            ).single()
            return int(record["c"]) if record else 0


def inject_message(*, text: str, workspace: str) -> subprocess.CompletedProcess[str]:
    """Publish a synthetic Slack message via inject_slack_message.py."""
    cmd = [
        sys.executable,
        str(_INJECT),
        "--text",
        text,
        "--workspace",
        workspace,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Slack pipeline: inject → extract → Neo4j",
    )
    parser.add_argument("--workspace", default=None, help="Cortex workspace id")
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Seconds to wait for a new Decision node after inject",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=3.0,
        help="Seconds between Neo4j polls",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check Ollama + Neo4j only; do not inject",
    )
    args = parser.parse_args()

    load_dotenv(_REPO / ".env")
    workspace = args.workspace or os.environ.get("CORTEX_WORKSPACE_ID", "local-dev")
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
    neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "cortex_local")

    ok, msg = check_ollama(base_url=ollama_url, model=ollama_model)
    print(f"{'PASS' if ok else 'FAIL'}: {msg}")
    if not ok:
        return 1

    try:
        before = count_decisions(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password,
            workspace=workspace,
        )
    except Exception as exc:  # noqa: BLE001 — script boundary
        print(f"FAIL: Neo4j query failed: {exc}")
        return 1

    print(f"Neo4j Decision count (workspace={workspace!r}): {before}")

    if args.dry_run:
        print("Dry run — skipping inject and poll")
        return 0

    marker = f"verify-pipeline-{int(time.time())}"
    text = (
        f"We decided to adopt event sourcing for billing ({marker}) "
        "because audit requirements blocked the monolith release."
    )
    print(f"Injecting Slack message (marker={marker!r})...")
    result = inject_message(text=text, workspace=workspace)
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        print("FAIL: inject_slack_message.py exited non-zero")
        return 1
    print(result.stdout.strip())

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        try:
            after = count_decisions(
                uri=neo4j_uri,
                user=neo4j_user,
                password=neo4j_password,
                workspace=workspace,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: Neo4j poll failed: {exc}")
            time.sleep(args.poll_interval)
            continue

        if after > before:
            print(f"PASS: Decision count increased {before} → {after}")
            return 0

        time.sleep(args.poll_interval)

    print(
        f"FAIL: No new Decision node within {args.timeout}s "
        f"(count stayed at {before}). Check pipeline-worker logs."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
