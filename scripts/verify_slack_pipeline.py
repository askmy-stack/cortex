#!/usr/bin/env python3
"""Verify connector → Kafka → extract → Neo4j pipeline end-to-end.

Supports slack, github, jira, and linear sources. Default source is slack for backward
compatibility with ``make verify-pipeline``.

Prerequisites:
  - `make stack` and `make init-kafka`
  - Ollama running on the host with the configured model pulled
  - After code changes: `make pipeline-restart` (seconds) — not `docker compose build`

Usage:
  python scripts/verify_slack_pipeline.py --source slack
  python scripts/verify_slack_pipeline.py --source github
  python scripts/verify_slack_pipeline.py --source jira --dry-run
  python scripts/verify_slack_pipeline.py --source linear
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
from collections.abc import Callable
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv
from neo4j import GraphDatabase

DecisionTextBuilder = Callable[[str, str], str]


def _slack_text(marker: str, _workspace: str) -> str:
    return (
        f"We decided to adopt event sourcing for billing ({marker}) "
        "because audit requirements blocked the monolith release."
    )


def _github_body(marker: str, _workspace: str) -> str:
    return (
        f"We decided to adopt event sourcing for billing ({marker}) "
        "because audit requirements blocked the monolith release."
    )


def _jira_comment(marker: str, _workspace: str) -> str:
    return (
        f"We decided to adopt event sourcing for billing ({marker}) "
        "because audit requirements blocked the monolith release."
    )


def _linear_comment(marker: str, _workspace: str) -> str:
    return (
        f"We decided to adopt event sourcing for billing ({marker}) "
        "because audit requirements blocked the monolith release."
    )


SOURCE_CONFIG: dict[str, dict[str, object]] = {
    "slack": {
        "script": "inject_slack_message.py",
        "label": "Slack message",
        "text_builder": _slack_text,
        "extra_args": lambda text, workspace: ["--text", text, "--workspace", workspace],
    },
    "github": {
        "script": "inject_github_event.py",
        "label": "GitHub PR",
        "text_builder": _github_body,
        "extra_args": lambda text, workspace: ["--body", text, "--workspace", workspace],
    },
    "jira": {
        "script": "inject_jira_event.py",
        "label": "Jira comment",
        "text_builder": _jira_comment,
        "extra_args": lambda text, workspace: ["--comment", text, "--workspace", workspace],
    },
    "linear": {
        "script": "inject_linear_event.py",
        "label": "Linear comment",
        "text_builder": _linear_comment,
        "extra_args": lambda text, workspace: ["--body", text, "--workspace", workspace],
    },
}


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


def inject_event(*, source: str, text: str, workspace: str) -> subprocess.CompletedProcess[str]:
    """Publish a synthetic connector event via the matching inject script."""
    config = SOURCE_CONFIG[source]
    script = _REPO / "scripts" / str(config["script"])
    extra_args_fn = config["extra_args"]
    assert callable(extra_args_fn)
    cmd = [sys.executable, str(script), *extra_args_fn(text, workspace)]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify connector pipeline: inject → extract → Neo4j",
    )
    parser.add_argument(
        "--source",
        choices=sorted(SOURCE_CONFIG),
        default="slack",
        help="Connector source to verify (default: slack)",
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

    config = SOURCE_CONFIG[args.source]
    label = str(config["label"])

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
        print(f"Dry run — skipping {args.source} inject and poll")
        return 0

    marker = f"verify-{args.source}-{int(time.time())}"
    text_builder = config["text_builder"]
    assert callable(text_builder)
    text = text_builder(marker, workspace)
    print(f"Injecting {label} (source={args.source!r}, marker={marker!r})...")
    result = inject_event(source=args.source, text=text, workspace=workspace)
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        print(f"FAIL: {config['script']} exited non-zero")
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
            print(f"PASS: {args.source} pipeline — Decision count {before} → {after}")
            return 0

        time.sleep(args.poll_interval)

    print(
        f"FAIL: No new Decision node within {args.timeout}s "
        f"(count stayed at {before}). Check pipeline-worker logs."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
