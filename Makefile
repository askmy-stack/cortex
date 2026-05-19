.PHONY: demo demo-dry-run test

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
