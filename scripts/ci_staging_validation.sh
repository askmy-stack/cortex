#!/usr/bin/env bash
# CI/local live-stack validation: infra → migrate → seed → smoke → k6.
# Used by .github/workflows/staging-validation.yml and manual pre-release checks.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-cortex_local}"
WORKSPACE="${CORTEX_WORKSPACE_ID:-ci-staging}"
API_URL="${CORTEX_URL:-http://localhost:8000}"
K6_VUS="${K6_VUS:-8}"
K6_DURATION="${K6_DURATION:-20s}"
K6_P95_MS="${K6_P95_MS:-5000}"
MAX_P95_MS="${MAX_P95_MS:-5000}"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

echo "==> Starting infrastructure"
docker compose up -d --wait --wait-timeout 600 zookeeper kafka neo4j redis postgres

echo "==> Building API"
docker compose --profile api build api

echo "==> Migrations"
docker compose --profile api run --rm --no-deps \
  -e NEO4J_URI=bolt://neo4j:7687 \
  -e NEO4J_USER="$NEO4J_USER" \
  -e NEO4J_PASSWORD="$NEO4J_PASSWORD" \
  api python -m graph.migrate

echo "==> Seed workspace $WORKSPACE"
docker compose --profile api run --rm --no-deps \
  -e NEO4J_URI=bolt://neo4j:7687 \
  -e NEO4J_USER="$NEO4J_USER" \
  -e NEO4J_PASSWORD="$NEO4J_PASSWORD" \
  -e CORTEX_WORKSPACE_ID="$WORKSPACE" \
  api python scripts/seed_demo.py --workspace "$WORKSPACE"

echo "==> Start API"
docker compose --profile api up -d --force-recreate api

echo "==> Wait for /health"
for _ in $(seq 1 60); do
  if curl -sf "$API_URL/health" | grep -q '"neo4j":"ok"'; then
    break
  fi
  sleep 3
done
curl -sf "$API_URL/health" | grep -q '"neo4j":"ok"' || {
  docker compose logs api --tail 80
  exit 1
}

echo "==> Staging smoke + benchmark"
python scripts/staging_smoke.py \
  --url "$API_URL" \
  --workspace "$WORKSPACE" \
  --benchmark \
  --max-p95-ms "$MAX_P95_MS"

if command -v k6 >/dev/null 2>&1; then
  echo "==> k6 load test"
  CORTEX_URL="$API_URL" CORTEX_WORKSPACE="$WORKSPACE" \
    K6_VUS="$K6_VUS" K6_DURATION="$K6_DURATION" K6_P95_MS="$K6_P95_MS" \
    k6 run scripts/load/k6_query.js
else
  echo "WARN: k6 not installed — skipping load test"
fi

echo "PASS: staging validation complete"
