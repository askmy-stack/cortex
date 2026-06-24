#!/bin/sh
# Production API entrypoint — migrate graph schema, optional one-time seed, then serve.
#
# CORTEX_SEED_DEMO defaults to false so redeploys do not re-seed. Set to "true" only
# on first boot or when intentionally resetting demo data.
set -eu

echo "Running Neo4j migrations..."
python graph/migrate.py

if [ "${CORTEX_SEED_DEMO:-false}" = "true" ]; then
  echo "Seeding local-dev demo workspace (CORTEX_SEED_DEMO=true)..."
  python scripts/seed_demo.py --workspace local-dev --scale small
else
  echo "Skipping demo seed (CORTEX_SEED_DEMO is not true)."
fi

echo "Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
