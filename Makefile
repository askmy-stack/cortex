.PHONY: demo demo-dry-run test ci stack init-kafka pipeline-restart pipeline-local verify-pipeline verify-github verify-jira verify-linear verify-connectors

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
