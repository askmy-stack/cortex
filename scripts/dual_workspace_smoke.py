#!/usr/bin/env python3
"""Compare query results across multiple Cortex workspaces.

Useful for validating synthetic seed data (local-dev) vs real OSS imports (oss-*).

Usage:
  python scripts/dual_workspace_smoke.py --url http://localhost:8000
  python scripts/dual_workspace_smoke.py --workspaces local-dev,oss-tiangolo-fastapi
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_QUERIES = [
    "Why CockroachDB for payments?",
    "cache session strategy",
    "architecture migration decision",
]

DEFAULT_WORKSPACES = ["local-dev", "oss-tiangolo-fastapi"]


def post_query(base_url: str, *, query: str, workspace_id: str, limit: int) -> dict:
    """POST /query and return parsed JSON."""
    body = json.dumps(
        {"query": query, "workspace_id": workspace_id, "limit": limit},
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/query",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Dual-workspace query smoke test")
    parser.add_argument("--url", default="http://localhost:8000", help="Cortex API base URL")
    parser.add_argument(
        "--workspaces",
        default=",".join(DEFAULT_WORKSPACES),
        help="Comma-separated workspace ids",
    )
    parser.add_argument(
        "--queries",
        default="",
        help="Comma-separated queries (default: built-in set)",
    )
    parser.add_argument("--limit", type=int, default=3, help="Results per query")
    args = parser.parse_args()

    workspaces = [w.strip() for w in args.workspaces.split(",") if w.strip()]
    queries = (
        [q.strip() for q in args.queries.split(",") if q.strip()]
        if args.queries
        else DEFAULT_QUERIES
    )

    print(f"API: {args.url}")
    print(f"Workspaces: {', '.join(workspaces)}")
    print()

    failed = 0
    for query in queries:
        print(f"Query: {query!r}")
        row: list[str] = []
        for ws in workspaces:
            try:
                payload = post_query(args.url, query=query, workspace_id=ws, limit=args.limit)
                results = payload.get("results") or []
                if results:
                    top = results[0].get("content", "")[:60]
                    row.append(f"{ws}: {len(results)} hit(s) — {top!r}…")
                else:
                    row.append(f"{ws}: 0 results")
            except urllib.error.HTTPError as exc:
                failed += 1
                row.append(f"{ws}: HTTP {exc.code}")
            except urllib.error.URLError as exc:
                failed += 1
                row.append(f"{ws}: unreachable ({exc.reason})")
        for line in row:
            print(f"  {line}")
        print()

    if failed:
        print(f"FAIL: {failed} request(s) failed", file=sys.stderr)
        return 1
    print("OK: all workspace queries completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
