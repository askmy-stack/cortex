# Deploying Cortex

Cortex is a **multi-service stack** (Kafka, Neo4j, Redis, API, pipeline worker, dashboard). Vercel hosts the **dashboard only**; the API and worker run elsewhere.

## Recommended split

| Component | Host | Notes |
|-----------|------|-------|
| Dashboard | **Vercel** (`frontend/`) | Vite static + API rewrites |
| API | Railway / Render / Fly | `api/Dockerfile` |
| pipeline-worker | Same as API | `pipeline/Dockerfile` |
| Neo4j | Neo4j Aura | Bolt URI in env |
| Redis | Upstash | Query cache |
| Kafka | Upstash Kafka / Confluent Cloud | Event bus |

## Vercel (frontend)

**Do not deploy the Python API on Vercel.** If the build log shows `Using Python 3.12 from pyproject.toml` or installs `uv.lock`, Vercel is treating the repo as FastAPI — that bundle (~5 GB) exceeds Lambda limits.

**Fix (pick one):**

| Approach | Settings |
|----------|----------|
| **Recommended** | Project Settings → General → **Root Directory** → `frontend` → Save → Redeploy |
| **Repo root** | Keep Root Directory `.` — root `vercel.json` forces `framework: vite` and builds `frontend/dist` only (no Python) |

After changing Root Directory, clear the Framework Preset override if it still says **FastAPI** — it should be **Vite** or **Other**.

**Project settings (Root Directory = `frontend`)**

- Root Directory: `frontend`
- Framework: Vite
- Build: `npm run build`
- API proxy: `middleware.ts` reads `CORTEX_API_ORIGIN` at **runtime** (Vercel parses `vercel.json` before build — build-time rewrites cannot inject env vars)

**Environment variables**

| Variable | Purpose |
|----------|---------|
| `CORTEX_API_ORIGIN` | Public API URL — Edge Middleware proxies `/query`, `/health`, etc. server-side |
| ~~`VITE_API_URL`~~ | **Do not** point at `loca.lt` — causes 511 tunnel interstitial errors |

**Do not** import the repo root with Framework Preset **FastAPI**. That installs the full `uv.lock` (~5 GB) and exceeds Lambda limits.

```bash
cd frontend
npx vercel deploy --prod
```

Set `CORTEX_API_ORIGIN=https://your-api.example.com` in the Vercel project before deploy.

## Local full stack

```bash
make demo
open http://localhost:3000   # dashboard (nginx → API)
open http://localhost:8000/docs
```

## Dev preview (laptop + tunnel)

For short-lived public demos while the API runs locally:

```bash
cloudflared tunnel --url http://localhost:8000
# Set CORTEX_API_ORIGIN to the trycloudflare.com URL on Vercel, redeploy frontend
```

Prefer **cloudflared** over localtunnel — localtunnel returns **511** for browser `fetch()` calls.

## Dual-workspace testing

See [DATA_SOURCES.md](./DATA_SOURCES.md) for `local-dev` vs `oss-*` workspaces.

```bash
python scripts/seed_demo.py --workspace local-dev
python scripts/import_github_org.py --org tiangolo --repo fastapi --dry-run
make verify-dual
```

## Railway / Render (API v1)

Deploy **only the API** — not Kafka or the pipeline worker. Pre-seed Neo4j with `scripts/seed_demo.py` so `/query` works without live ingestion.

### Railway

```bash
# Install CLI: https://docs.railway.com/guides/cli
railway login
railway init          # link this repo
railway up            # uses railway.toml → api/Dockerfile
```

**Required environment variables** (Railway → Variables):

| Variable | Example |
|----------|---------|
| `NEO4J_URI` | `neo4j+s://xxxx.databases.neo4j.io` |
| `NEO4J_USER` | `neo4j` |
| `NEO4J_PASSWORD` | Aura password |
| `REDIS_URL` | `rediss://default:token@host.upstash.io:6379` |
| `CORTEX_API_KEYS` | `demo-readonly:authenticated` (optional abuse control) |
| `CORTEX_SEMANTIC_ENABLED` | `false` |
| `CORTEX_SEED_DEMO` | `true` **first deploy only** — then set `false` so restarts skip re-seed |

Copy the public Railway URL (e.g. `https://cortex-api-production.up.railway.app`), set `CORTEX_API_ORIGIN` on Vercel, and redeploy the frontend.

**Production startup:** `scripts/start_api_production.sh` runs migrations on every boot. Demo seed runs only when `CORTEX_SEED_DEMO=true`.

### Render

Use [render.yaml](../render.yaml) as a Blueprint, or create a **Web Service** with Docker runtime and `api/Dockerfile` as the Dockerfile path. Same env vars as Railway.

### Seed production graph (one-time)

**Option A — first Railway deploy:** set `CORTEX_SEED_DEMO=true` on the API service, deploy once, then set `CORTEX_SEED_DEMO=false`.

**Option B — from laptop** with Neo4j credentials in `.env`:

```bash
export NEO4J_URI=neo4j+s://...
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=...
uv run python graph/migrate.py
uv run python scripts/seed_demo.py --workspace local-dev --scale small
uv run python scripts/import_github_graph.py --org tiangolo --repo fastapi --workspace oss-tiangolo-fastapi --limit 30
make verify-dual-production
```

Direct graph import (no Kafka): [scripts/import_github_graph.py](../scripts/import_github_graph.py).

### Neo4j Aura migration

See [AURA_MIGRATION.md](./AURA_MIGRATION.md). Rotate passwords after any credential exposure — update Railway env vars only, never commit secrets.

### Optional demo API key (abuse control)

For public demos, use a read-only key so anonymous traffic cannot hammer write endpoints:

```bash
CORTEX_API_KEYS=demo-readonly:authenticated
```

Dashboard users paste the key in **Connection** settings. Open `/query` and `/health` remain usable without a key when `CORTEX_API_KEYS` is unset.

### Wire Vercel → API

```bash
# Vercel project → Settings → Environment Variables
CORTEX_API_ORIGIN=https://your-api.railway.app

cd frontend && npx vercel deploy --prod
```

Verify:

```bash
curl -s https://your-vercel-app.vercel.app/health
curl -s -X POST https://your-vercel-app.vercel.app/query \
  -H "Content-Type: application/json" \
  -d '{"query":"Why CockroachDB?","workspace_id":"local-dev","limit":5}'
```

## Auth on preview

```bash
CORTEX_API_KEYS=preview-key:admin;authenticated
CORTEX_DEMO_API_KEY=preview-key
```

`make demo` and `scripts/demo.sh` send `Authorization` when these are set.

## Optional cloud webhook path (v2)

Full ingestion uses Kafka + pipeline-worker locally. For cloud v1 without Kafka, use direct graph import:

```bash
make import-oss-graph    # real GitHub PRs → Neo4j
make seed-oss-fastapi    # synthetic OSS demo fallback
```

Future v2: deploy pipeline-worker as a second Railway service + Upstash Kafka, or add `POST /webhooks/github` → synchronous extract/write for demo scale. See [LAUNCH.md](./LAUNCH.md).
