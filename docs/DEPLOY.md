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
- Build: `npm run build` (runs `scripts/vercel-api-rewrites.mjs`)

**Environment variables**

| Variable | Purpose |
|----------|---------|
| `CORTEX_API_ORIGIN` | Public API URL — Vercel rewrites `/query`, `/health`, etc. server-side |
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

## Auth on preview

```bash
CORTEX_API_KEYS=preview-key:admin;authenticated
CORTEX_DEMO_API_KEY=preview-key
```

`make demo` and `scripts/demo.sh` send `Authorization` when these are set.
