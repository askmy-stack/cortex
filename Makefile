.PHONY: demo demo-dry-run test ci stack init-kafka pipeline-restart pipeline-local verify-pipeline verify-github verify-jira verify-linear verify-connectors portfolio-demo seed-dev import-oss import-oss-graph seed-cloud verify-dual verify-dual-production verify-production

# Production API URL for smoke tests (override on CLI).
CORTEX_PRODUCTION_URL ?= https://cortex-api-production-fbd5.up.railway.app

# Local portfolio demo: Docker infra + migrations + seed + API + worker + frontend.
demo:
	bash scripts/demo.sh

# Verify seed script builds without touching Neo4j (requires Python env with project installed).
demo-dry-run:
	uv run python scripts/seed_demo.py --dry-run

test:
	uv run pytest tests/

# Match CI workflow locally (no Docker).
ci: test
	uv run python scripts/seed_demo.py --dry-run -q

# Start API profile stack (Kafka, Neo4j, API, pipeline-worker, …).
stack:
	docker compose --profile api up -d

# Pre-create Kafka topics (eliminates worker UNKNOWN_TOPIC errors on cold start).
init-kafka:
	python scripts/init_kafka_topics.py

# Fast worker reload after Python changes (volume-mounted code; no image rebuild).
pipeline-restart:
	docker compose --profile api restart pipeline-worker

# Host-native worker — use when iterating on extraction/scoring (stop container worker first).
pipeline-local:
	bash scripts/run_pipeline_worker_local.sh

# End-to-end: inject → Ollama extract → Neo4j Decision node.
verify-pipeline:
	python scripts/verify_slack_pipeline.py --source slack --timeout 120

verify-github:
	python scripts/verify_slack_pipeline.py --source github --timeout 120

verify-jira:
	python scripts/verify_slack_pipeline.py --source jira --timeout 120

verify-linear:
	python scripts/verify_slack_pipeline.py --source linear --timeout 120

verify-connectors: verify-pipeline verify-github verify-jira verify-linear

# Dual-workspace: synthetic dev seed vs OSS import smoke.
seed-dev:
	uv run python scripts/seed_demo.py --workspace local-dev

import-oss:
	uv run python scripts/import_github_org.py --org tiangolo --repo fastapi --dry-run

# Direct Neo4j import (no Kafka) — use for cloud / portfolio backends.
import-oss-graph:
	uv run python scripts/import_github_graph.py --org tiangolo --repo fastapi --workspace oss-tiangolo-fastapi --limit 30

# Synthetic OSS workspace seed when GitHub import is unavailable.
seed-oss-fastapi:
	uv run python scripts/seed_oss_fastapi_demo.py --workspace oss-tiangolo-fastapi

# Seed + OSS import against remote Neo4j (set NEO4J_URI / credentials in env).
seed-cloud: seed-dev seed-oss-fastapi

verify-dual:
	uv run python scripts/dual_workspace_smoke.py --workspaces local-dev,oss-tiangolo-fastapi

verify-production:
	uv run python scripts/staging_smoke.py --url $(CORTEX_PRODUCTION_URL) --query "Why CockroachDB for payments?"

verify-dual-production:
	uv run python scripts/dual_workspace_smoke.py --url $(CORTEX_PRODUCTION_URL) --workspaces local-dev,oss-tiangolo-fastapi

# Vercel frontend build smoke (injects API rewrites when CORTEX_API_ORIGIN is set).
verify-vercel-build:
	cd frontend && npm run build

# Portfolio demo: Docker API must be up; starts cloudflared and prints Vercel env instructions.
portfolio-demo:
	@./scripts/start_portfolio_demo.sh
