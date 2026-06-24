#!/usr/bin/env bash
# Start cloudflared tunnel to local Cortex API for Vercel portfolio demo.
# Requires: docker compose api on :8000, cloudflared installed (brew install cloudflared).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_URL="${CORTEX_API_URL:-http://localhost:8000}"
VERCEL_DEMO_URL="${VERCEL_DEMO_URL:-https://frontend-ten-rouge-99.vercel.app}"

if ! curl -sf "${API_URL}/health" >/dev/null 2>&1; then
  echo "ERROR: Cortex API not reachable at ${API_URL}" >&2
  echo "Start the stack: make demo   (or: docker compose --profile api up -d)" >&2
  exit 1
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "ERROR: cloudflared not found. Install: brew install cloudflared" >&2
  exit 1
fi

echo "Starting cloudflared tunnel → ${API_URL}"
echo "When the trycloudflare.com URL appears below:"
echo "  1. Vercel → frontend project → Settings → Environment Variables"
echo "  2. Set CORTEX_API_ORIGIN to that URL (Production)"
echo "  3. Share demo: ${VERCEL_DEMO_URL}"
echo ""
echo "For 24/7 demo without this laptop, see docs/PORTFOLIO_DEMO.md"
echo "---"

exec cloudflared tunnel --url "${API_URL}"
