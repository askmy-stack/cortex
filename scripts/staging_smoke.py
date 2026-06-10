#!/usr/bin/env python3
"""Validate a running Cortex stack (staging or local docker compose).

Checks:
  1. GET /health — API up, Neo4j + Redis dependency status
  2. POST /query — sample retrieval returns HTTP 200
  3. Optional: run query latency benchmark via benchmark_query.py

Usage:
  python scripts/staging_smoke.py --dry-run
  python scripts/staging_smoke.py --url http://localhost:8000
  python scripts/staging_smoke.py --url http://localhost:8000 --benchmark
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_BENCHMARK = _REPO / "scripts" / "benchmark_query.py"


def fetch_json(url: str, *, method: str = "GET", body: dict | None = None) -> dict:
    """HTTP request returning parsed JSON."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_health(base_url: str) -> tuple[bool, dict]:
    """Return (ok, payload) for GET /health."""
    payload = fetch_json(f"{base_url.rstrip('/')}/health")
    deps = payload.get("dependencies", {})
    neo4j = deps.get("neo4j", "unknown")
    redis = deps.get("redis", "unknown")
    ok = payload.get("status") == "ok" and neo4j == "ok" and redis == "ok"
    return ok, payload


def check_query(base_url: str, *, workspace: str, query: str) -> tuple[bool, dict]:
    """Return (ok, payload) for POST /query."""
    payload = fetch_json(
        f"{base_url.rstrip('/')}/query",
        method="POST",
        body={"query": query, "workspace_id": workspace, "limit": 5},
    )
    ok = isinstance(payload.get("results"), list)
    return ok, payload


def run_benchmark(*, base_url: str, workspace: str, max_p95_ms: float) -> int:
    """Delegate to scripts/benchmark_query.py; return process exit code."""
    cmd = [
        sys.executable,
        str(_BENCHMARK),
        "--url",
        base_url,
        "--workspace",
        workspace,
        "--iterations",
        "10",
        "--max-p95-ms",
        str(max_p95_ms),
    ]
    return subprocess.run(cmd, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Cortex staging smoke validation")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--workspace", default="local-dev", help="Workspace id for /query")
    parser.add_argument(
        "--query",
        default="Why CockroachDB for payments?",
        help="Sample natural language query",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run benchmark_query.py after smoke checks",
    )
    parser.add_argument(
        "--max-p95-ms",
        type=float,
        default=2000.0,
        help="p95 budget when --benchmark is set",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned checks without calling the API",
    )
    args = parser.parse_args()

    if args.dry_run:
        print("Dry run — would validate:")
        print(f"  GET  {args.url.rstrip('/')}/health")
        print(f"  POST {args.url.rstrip('/')}/query  workspace={args.workspace!r}")
        if args.benchmark:
            print(f"  benchmark iterations=10 max_p95_ms={args.max_p95_ms}")
        return 0

    try:
        health_ok, health = check_health(args.url)
    except urllib.error.URLError as exc:
        print(f"FAIL: API unreachable at {args.url}: {exc.reason}", file=sys.stderr)
        return 2

    print(json.dumps({"health": health}, indent=2))
    if not health_ok:
        print("FAIL: /health dependencies not all ok", file=sys.stderr)
        return 1

    try:
        query_ok, query_payload = check_query(
            args.url,
            workspace=args.workspace,
            query=args.query,
        )
    except urllib.error.HTTPError as exc:
        print(f"FAIL: /query returned HTTP {exc.code}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"FAIL: /query unreachable: {exc.reason}", file=sys.stderr)
        return 2

    print(json.dumps({"query": {"total": query_payload.get("total"), "latency_ms": query_payload.get("latency_ms")}}, indent=2))
    if not query_ok:
        print("FAIL: /query response missing results array", file=sys.stderr)
        return 1

    if args.benchmark:
        code = run_benchmark(
            base_url=args.url,
            workspace=args.workspace,
            max_p95_ms=args.max_p95_ms,
        )
        if code != 0:
            return code

    print("PASS: staging smoke checks complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
