#!/usr/bin/env bash
# Smoke-test Plan A deploy: Render API + optional Cloudflare Pages dashboard.
set -euo pipefail

API=""
PAGES=""

usage() {
  echo "Usage: $0 --api URL [--pages URL]"
  echo "  --api    Render API base URL (required)"
  echo "  --pages  Cloudflare Pages URL (optional HEAD check)"
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --api) API="${2%/}"; shift 2 ;;
    --pages) PAGES="${2%/}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

[ -n "$API" ] || usage

echo "==> Health: $API/health"
health=$(curl -sf "$API/health")
echo "$health" | head -c 200
echo ""

echo "==> Query: local-dev"
result=$(curl -sf -X POST "$API/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"Why CockroachDB?","workspace_id":"local-dev","limit":5}')
count=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total',0))")
echo "total=$count"
if [ "$count" -lt 1 ]; then
  echo "FAIL: expected at least 1 decision — seed Neo4j or set CORTEX_SEED_DEMO=true on Render"
  exit 1
fi

if [ -n "$PAGES" ]; then
  echo "==> Pages HEAD: $PAGES"
  curl -sfI "$PAGES" | head -5
fi

echo "OK — Plan A API checks passed"
