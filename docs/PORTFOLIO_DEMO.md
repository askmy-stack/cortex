# Cortex — Portfolio & LinkedIn Demo

Use this page when linking Cortex from your portfolio site, GitHub README, or LinkedIn posts.

## Live demo (share this URL)

**https://frontend-ten-rouge-99.vercel.app**

### 30-second walkthrough (for recruiters)

1. Open the link — Cortex dashboard loads (Vercel CDN).
2. Confirm workspace is **`local-dev`** (preset chip).
3. Go to **Ask** and query: **`Why CockroachDB for payments?`**
4. Point out: decisions from Slack/GitHub/Jira, trust scores, graph relationships — not raw chat logs.

### What to say in one line

> *Cortex is an organizational memory OS — it captures decisions from every tool, stores them in a knowledge graph, and injects relevant context into AI agents at inference time via MCP.*

---

## How the public demo is wired

```text
Browser → Vercel (React dashboard)
              ↓ Edge Middleware (CORTEX_API_ORIGIN)
         API (FastAPI + Neo4j + Redis)
```

- **Dashboard:** Vercel project `frontend` (static Vite build).
- **API proxy:** `frontend/middleware.ts` forwards `/query`, `/health`, etc. server-side.
- **Do not** set `VITE_API_URL` on Vercel — same-origin `/query` avoids CORS and tunnel 511 errors.

---

## Keeping the demo online

| Mode | Uptime | Setup |
|------|--------|--------|
| **Production** (live) | 24/7 | Railway API + Neo4j + Redis on `cortex-api-demo` project |
| **Dev tunnel** (fallback) | While your Mac + Docker + `cloudflared` run | `make portfolio-demo` |

### Quick dev tunnel (laptop demo)

```bash
make portfolio-demo
```

Starts `cloudflared` to `localhost:8000`, prints the tunnel URL, and reminds you to set `CORTEX_API_ORIGIN` on Vercel if the URL changed.

### Production backend (deployed)

| Service | URL |
|---------|-----|
| API | https://cortex-api-production-fbd5.up.railway.app |
| Dashboard | https://frontend-ten-rouge-99.vercel.app |
| Railway project | `cortex-api-demo` |

Vercel `CORTEX_API_ORIGIN` → Railway API URL (no laptop required).

### Re-deploy from scratch

1. `railway login` → `railway init` (or use existing `cortex-api-demo` project).
2. Add **Redis** (`railway add --database redis`) and **Neo4j** (`neo4j:5.20-community` image).
3. Deploy API: `railway up --service cortex-api` (uses `api/Dockerfile.query`).
4. Set env on the API service:

   ```env
   NEO4J_URI=neo4j+s://...
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=...
   REDIS_URL=rediss://...
   CORTEX_SEMANTIC_ENABLED=false
   CORTEX_API_KEYS=preview-key:admin;authenticated
   ```

5. Seed the graph once from your machine:

   ```bash
   export NEO4J_URI=neo4j+s://...
   uv run python graph/migrate.py
   uv run python scripts/seed_demo.py --workspace local-dev --scale small
   ```

   Or set `CORTEX_SEED_DEMO=true` on first API deploy, then **`CORTEX_SEED_DEMO=false`** after boot.

6. Vercel → Project **frontend** → Environment Variables → `CORTEX_API_ORIGIN` = your public API URL (e.g. `https://cortex-api.onrender.com`). No frontend redeploy needed — middleware reads it at runtime.

**Custom domain:** [CUSTOM_DOMAIN.md](./CUSTOM_DOMAIN.md)  
**Neo4j Aura:** [AURA_MIGRATION.md](./AURA_MIGRATION.md)  
**Launch checklist:** [LAUNCH.md](./LAUNCH.md)

---

## Vercel project settings

| Setting | Value |
|---------|--------|
| Root Directory | `frontend` |
| Framework | Vite |
| Production URL | https://frontend-ten-rouge-99.vercel.app |
| Env var | `CORTEX_API_ORIGIN` = public API base URL (no trailing slash) |

Redeploy frontend after code changes:

```bash
cd frontend && npx vercel deploy --prod
```
