#!/usr/bin/env python3
"""Benchmark Cortex /query latency against a running API.

Usage:
  python scripts/benchmark_query.py --dry-run
  python scripts/benchmark_query.py --url http://localhost:8000 --iterations 30

Exits non-zero if p95 exceeds --max-p95-ms (default 2000) when the API is reachable.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def _percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile (same method as NumPy ``percentile``)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * (pct / 100)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] + weight * (ordered[upper] - ordered[lower])


def run_benchmark(
    *,
    url: str,
    workspace_id: str,
    query: str,
    iterations: int,
    limit: int,
) -> dict[str, float | int]:
    """POST /query ``iterations`` times and return latency stats in milliseconds."""
    endpoint = f"{url.rstrip('/')}/query"
    payload = json.dumps(
        {
            "query": query,
            "workspace_id": workspace_id,
            "limit": limit,
        }
    ).encode("utf-8")

    latencies: list[float] = []
    errors = 0

    for _ in range(iterations):
        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
                if resp.status >= 400:
                    errors += 1
        except urllib.error.HTTPError:
            errors += 1
        except urllib.error.URLError:
            raise
        else:
            latencies.append((time.perf_counter() - t0) * 1000)

    return {
        "iterations": iterations,
        "success": len(latencies),
        "errors": errors,
        "min_ms": min(latencies) if latencies else 0.0,
        "mean_ms": statistics.mean(latencies) if latencies else 0.0,
        "p50_ms": _percentile(latencies, 50),
        "p95_ms": _percentile(latencies, 95),
        "max_ms": max(latencies) if latencies else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Cortex /query latency")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--workspace", default="local-dev", help="Workspace id")
    parser.add_argument(
        "--query",
        default="Why CockroachDB for payments?",
        help="Natural language query to benchmark",
    )
    parser.add_argument("--iterations", type=int, default=20, help="Number of requests")
    parser.add_argument("--limit", type=int, default=10, help="Result limit per request")
    parser.add_argument(
        "--max-p95-ms",
        type=float,
        default=2000.0,
        help="Fail if p95 latency exceeds this threshold",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned benchmark and exit without calling the API",
    )
    args = parser.parse_args()

    if args.dry_run:
        print("Dry run — would benchmark:")
        print(f"  POST {args.url.rstrip('/')}/query")
        print(f"  workspace={args.workspace!r} iterations={args.iterations}")
        print(f"  query={args.query!r}")
        return 0

    try:
        stats = run_benchmark(
            url=args.url,
            workspace_id=args.workspace,
            query=args.query,
            iterations=args.iterations,
            limit=args.limit,
        )
    except urllib.error.URLError as exc:
        print(f"API unreachable at {args.url}: {exc.reason}", file=sys.stderr)
        print("Start the API (docker compose up) or pass --dry-run.", file=sys.stderr)
        return 2

    print(json.dumps(stats, indent=2))
    p95 = float(stats["p95_ms"])
    if p95 > args.max_p95_ms:
        print(
            f"FAIL: p95 {p95:.1f}ms exceeds budget {args.max_p95_ms}ms",
            file=sys.stderr,
        )
        return 1
    if int(stats["errors"]) > 0:
        print(f"WARN: {stats['errors']} requests failed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
