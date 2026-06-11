#!/usr/bin/env python3
"""Import merged GitHub PRs from a public repo into the Cortex Kafka pipeline.

Fetches closed merged pull requests via the GitHub REST API, filters for
decision-like titles/bodies, normalises to RawEvent, and publishes to
``cortex.raw.github.events`` for the extraction worker.

Usage:
  python scripts/import_github_org.py --org tiangolo --repo fastapi --dry-run
  python scripts/import_github_org.py --org tiangolo --repo fastapi --workspace oss-fastapi --limit 30
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv

from connectors.github.producer import GitHubKafkaProducer, normalise_github_event
from scripts.inject_github_event import build_merged_pr_payload

DECISION_PATTERN = re.compile(
    r"\b(decision|rfc|adr|migrate|migration|deprecat|architect|proposal|"
    r"we decided|chosen|replace|switch to)\b",
    re.IGNORECASE,
)

GITHUB_API = "https://api.github.com"


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "cortex-import-github-org",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_merged_prs(
    owner: str,
    repo: str,
    *,
    limit: int,
    page_size: int = 100,
) -> list[dict[str, Any]]:
    """Return up to ``limit`` merged pull requests (newest first)."""
    collected: list[dict[str, Any]] = []
    page = 1
    while len(collected) < limit:
        url = (
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls"
            f"?state=closed&sort=updated&direction=desc&per_page={page_size}&page={page}"
        )
        req = urllib.request.Request(url, headers=_github_headers())
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                batch: list[dict[str, Any]] = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"GitHub API error {exc.code}: {exc.reason}") from exc

        if not batch:
            break

        for pr in batch:
            if pr.get("merged_at"):
                collected.append(pr)
                if len(collected) >= limit:
                    break
        page += 1
        if len(batch) < page_size:
            break
        time.sleep(0.5)

    return collected[:limit]


def is_decision_like(pr: dict[str, Any]) -> bool:
    """Heuristic filter for PRs likely to contain organizational decisions."""
    text = f"{pr.get('title', '')}\n{pr.get('body') or ''}"
    return bool(DECISION_PATTERN.search(text))


def pr_to_payload(pr: dict[str, Any], repo_full_name: str) -> dict[str, Any]:
    """Map GitHub pull object to webhook-shaped payload."""
    user = pr.get("user") or {}
    head = pr.get("head") or {}
    return build_merged_pr_payload(
        title=str(pr.get("title", "")),
        body=str(pr.get("body") or ""),
        repo=repo_full_name,
        number=int(pr.get("number", 0)),
        user_login=str(user.get("login", "unknown")),
        updated_at=str(pr.get("updated_at") or pr.get("merged_at") or ""),
        created_at=str(pr.get("created_at") or ""),
        head_ref=str(head.get("ref", "feature/import")),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import merged GitHub PRs into cortex.raw.github.events",
    )
    parser.add_argument("--org", required=True, help="GitHub org or user")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument(
        "--workspace",
        default=None,
        help="Cortex workspace id (default: oss-<org>-<repo>)",
    )
    parser.add_argument("--limit", type=int, default=50, help="Max merged PRs to fetch")
    parser.add_argument(
        "--all-merged",
        action="store_true",
        help="Import all merged PRs (default: filter decision-like PRs only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned RawEvents without publishing to Kafka",
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

    events: list[tuple[str, dict[str, Any]]] = []
    for pr in prs:
        payload = pr_to_payload(pr, repo_full)
        raw = normalise_github_event(payload, "pull_request", workspace)
        if raw is None:
            continue
        events.append((raw.event_id, json.loads(raw.model_dump_json())))

    if args.dry_run:
        for _eid, body in events[:5]:
            print(json.dumps(body, indent=2)[:500], "…")
        if len(events) > 5:
            print(f"… and {len(events) - 5} more")
        print(f"\nDry run — would publish {len(events)} event(s) to cortex.raw.github.events")
        return 0

    if not events:
        print("No events to publish.", file=sys.stderr)
        return 1

    producer = GitHubKafkaProducer()
    try:
        for _eid, body in events:
            from shared.models import RawEvent

            raw_event = RawEvent.model_validate(body)
            producer.publish(raw_event)
        producer.flush(timeout=30.0)
    finally:
        producer.close()

    print(f"Published {len(events)} event(s) to cortex.raw.github.events")
    print("Run pipeline-worker and query with workspace_id=", repr(workspace))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
