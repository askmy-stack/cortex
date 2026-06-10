#!/usr/bin/env bash
# Run the extraction pipeline worker on the host (fastest iteration — no Docker rebuild).
# Requires: docker compose --profile api up -d (infra only; stop pipeline-worker if duplicated).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
export REDIS_HOST="${REDIS_HOST:-localhost}"
export KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
export TIMESCALE_HOST="${TIMESCALE_HOST:-localhost}"
export TIMESCALE_PORT="${TIMESCALE_PORT:-5433}"

exec python -m pipeline.extraction_worker
