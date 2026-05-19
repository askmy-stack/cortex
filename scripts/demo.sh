#!/usr/bin/env bash
# One-command local demo: infra → migrations → Neo4j seed → API + worker + dashboard + smoke curl.
# Prerequisites: Docker + Docker Compose plugin, ports 5432 6379 7687 7474 9092 8000 3000 free.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Compose services reference env_file: .env — create from template if missing.
if [[ ! -f .env ]]; then
  echo "==> Creating .env from .env.example (no secrets required for local demo)"
  cp .env.example .env
fi

NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-cortex_local}"
WORKSPACE="${CORTEX_WORKSPACE_ID:-local-dev}"
export NEO4J_USER NEO4J_PASSWORD

echo "==> Building API image (migrate + seed + runtime)"
docker compose --profile api build api

echo "==> Starting Kafka, Neo4j, Redis, Postgres (wait until healthy)"
# --wait avoids hanging forever on docker exec cypher-shell when a service is crash-looping.
docker compose up -d --wait --wait-timeout 600 zookeeper kafka neo4j redis postgres

echo "==> Applying Neo4j migrations"
docker compose --profile api run --rm --no-deps \
  -e NEO4J_URI=bolt://neo4j:7687 \
  -e NEO4J_USER="$NEO4J_USER" \
  -e NEO4J_PASSWORD="$NEO4J_PASSWORD" \
  api python -m graph.migrate

echo "==> Seeding demo decisions (workspace: $WORKSPACE)"
docker compose --profile api run --rm --no-deps \
  -e NEO4J_URI=bolt://neo4j:7687 \
  -e NEO4J_USER="$NEO4J_USER" \
  -e NEO4J_PASSWORD="$NEO4J_PASSWORD" \
  -e CORTEX_WORKSPACE_ID="$WORKSPACE" \
  api python scripts/seed_demo.py --workspace "$WORKSPACE"

echo "==> Building frontend image (dashboard UI)"
docker compose --profile frontend build frontend

echo "==> Starting API, pipeline worker, frontend"
docker compose --profile api --profile frontend up -d --force-recreate api pipeline-worker frontend

echo "==> Waiting for API /health"
for _ in $(seq 1 45); do
  if curl -sf "http://localhost:8000/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "==> Smoke: POST /query (CockroachDB + payments)"
curl -sf "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"Why CockroachDB for payments?\",\"workspace_id\":\"$WORKSPACE\",\"limit\":5}" \
  | head -c 800
echo
echo
echo "Demo stack is up."
echo "  Dashboard:  http://localhost:3000"
echo "  API docs:   http://localhost:8000/docs"
echo "  Kafka UI:   http://localhost:8080"
