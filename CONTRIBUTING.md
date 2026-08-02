# Contributing to Cortex

Thank you for helping make Cortex the organizational memory layer for AI-native
teams. This guide covers local development, environment configuration, and how
to submit changes.

## Before You Start

- Read the [README](README.md) for product context and architecture.
- Follow our [Code of Conduct](CODE_OF_CONDUCT.md).
- For security issues, see [SECURITY.md](SECURITY.md) — do **not** open public
  issues for vulnerabilities.

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Docker** | Recent desktop or engine | Kafka, Neo4j, Redis, Postgres, demo stack |
| **Python** | 3.11+ | API, pipeline worker, tests |
| **uv** | Latest | Dependency install and test runner (recommended) |
| **Node.js** | 20+ | MCP server (`mcp/`) and dashboard (`frontend/`) |

Optional for full pipeline verification:

- **Ollama** — local LLM extraction when `EXTRACTION_BACKEND=ollama`
- **OpenAI API key** — when using `EXTRACTION_BACKEND=openai` or CMVK with OpenAI

## Local Development

### Fastest path — full demo stack

From the repo root, with Docker running:

```bash
git clone https://github.com/askmy-stack/cortex
cd cortex
cp .env.example .env   # optional; compose defaults work for local demo
make demo              # infra + migrations + seed + API + worker + dashboard
open http://localhost:3000
```

On the dashboard, open **Ask**, use workspace `local-dev`, and try:
*Why CockroachDB for payments?*

`make demo` runs `scripts/demo.sh`, which brings up services, applies Neo4j
migrations, seeds demo decisions, starts the API and pipeline worker, and
runs a sample `POST /query` smoke check.

### Manual setup

```bash
# Core infra only (Kafka, Neo4j, Redis, Postgres)
docker compose up -d

# API + pipeline worker + dashboard (production-like via Docker)
docker compose --profile api --profile frontend up -d --build

# Connect Slack (optional — requires tokens in .env)
python scripts/connect_slack.py --workspace your-workspace
```

**UI development (hot reload):**

```bash
cd frontend && npm run dev   # http://localhost:5173
```

The Docker dashboard is served on port **3000**. Rebuild the frontend image
after UI changes, or use the Vite dev server on **5173** during active work.

### Python API without Docker profiles

With infra running and `.env` configured:

```bash
uv pip install -e ".[dev]"
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### MCP server

```bash
cd mcp && npm install && npm test
node server.js   # expects CORTEX_API_URL=http://localhost:8000
```

See the MCP block in [README.md](README.md#quickstart) for Claude/Cursor config.

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed. Never commit `.env`.

| Area | Key variables | Notes |
|------|---------------|-------|
| **Neo4j** | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Default `bolt://localhost:7687` for host-local uvicorn |
| **Kafka** | `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` on host; compose uses internal `kafka:29092` |
| **Redis / Postgres** | `REDIS_*`, `POSTGRES_*`, `TIMESCALE_*` | Compose overrides hostnames inside containers |
| **LLM extraction** | `EXTRACTION_BACKEND`, `OPENAI_API_KEY`, `OLLAMA_*` | `ollama` for local dev; `openai` for production-like runs |
| **API auth** | `CORTEX_API_KEYS`, `CORTEX_DEMO_API_KEY` | Unset = open dev mode; set for staging/production |
| **CMVK** | `CORTEX_CMVK_BACKEND`, `CORTEX_CMVK_ENABLED` | Default `heuristic` needs no LLM; worker fails fast if misconfigured |
| **Connectors** | `SLACK_*`, `GITHUB_*`, `JIRA_*`, `LINEAR_*` | Optional; required only when testing real webhooks |
| **MCP** | `CORTEX_API_URL`, `CORTEX_API_KEY` | `CORTEX_API_KEY` required when `ENVIRONMENT=production` |

Full comments and defaults live in [`.env.example`](.env.example).

## Running Tests

### Python (matches CI)

```bash
make test          # uv run pytest tests/
make ci            # pytest + seed_demo dry-run (same as CI test job)
```

Or without Make:

```bash
uv pip install -e ".[dev]"
CORTEX_CONTRADICTION_ENABLED=false pytest tests/
python scripts/seed_demo.py --dry-run
python scripts/staging_smoke.py --dry-run
```

Most unit tests do not require Docker. Integration tests that need Neo4j or
Kafka are skipped or gated when services are unavailable.

### Frontend

```bash
cd frontend
npm ci
npm test
npm run build
npm run test:e2e    # Playwright; installs Chromium on first run
```

### MCP

```bash
cd mcp && npm test
```

CI runs all of the above on every pull request — see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make demo` | Full local demo stack + smoke query |
| `make demo-dry-run` | Verify seed script without Neo4j |
| `make test` | Run Python test suite |
| `make ci` | Local CI parity (tests + dry-run seed) |
| `make stack` | Start API profile Docker stack |
| `make init-kafka` | Pre-create Kafka topics |
| `make pipeline-restart` | Restart pipeline worker after Python changes |
| `make verify-connectors` | End-to-end connector pipeline checks |

## Project Layout

```
cortex/
├── api/           FastAPI application
├── pipeline/      Kafka extraction worker
├── mcp/           MCP server (TypeScript)
├── frontend/      React dashboard
├── sdk/           Python client
├── tests/         Pytest suite
├── scripts/       Demo, seed, verification utilities
└── docs/          Deploy guides, ADRs, demo recording
```

Deeper architecture notes: [ARCHITECTURE.md](ARCHITECTURE.md),
[docs/DEPLOY.md](docs/DEPLOY.md), [docs/DEPLOY-FREE.md](docs/DEPLOY-FREE.md).

## Submitting Changes

1. **Open an issue** (or comment on an existing one) before large changes so
   we can align on approach.
2. **Fork and branch** from `main` with a descriptive name, e.g.
   `fix/query-cache-invalidation` or `docs/connector-validation`.
3. **Keep PRs focused** — one logical change per pull request when possible.
4. **Run tests locally** — at minimum `make ci` for Python-only changes;
   include frontend/MCP tests when you touch those areas.
5. **Update docs** when behavior, env vars, or setup steps change.
6. **Write clear commit messages** — explain *why*, not just *what*.

Pull requests should describe the problem, the solution, and how you verified
it (commands run, screenshots for UI changes).

## Code Style

- **Python:** follow existing patterns in the module you edit; type hints and
  pydantic models where the codebase already uses them.
- **TypeScript:** match `mcp/` and `frontend/` conventions; run linters/tests
  before pushing.
- **Cypher / SQL migrations:** add numbered files under `graph/migrations/`;
  never mutate applied migration history.

## Questions

- **Bugs and features:** [GitHub Issues](https://github.com/askmy-stack/cortex/issues)
- **Security:** [SECURITY.md](SECURITY.md)
- **Conduct:** [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

We appreciate every contribution — from typo fixes to new connectors.
