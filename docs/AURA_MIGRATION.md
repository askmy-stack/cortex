# Migrate production Neo4j from Railway to Aura

Railway’s community Neo4j image is fine for first deploy but lacks managed backups and stable memory limits. **Neo4j Aura Free** is the recommended production graph for the portfolio demo.

## Why migrate

| Railway Neo4j | Neo4j Aura Free |
|---------------|-----------------|
| 256MB heap, manual ops | Managed, auto-patches |
| No backups | Daily backups (paid tiers) / export on free |
| Crash loops under load | Stable for demo scale |
| Internal DNS only | `neo4j+s://` public bolt |

Decision **P-003** in [DECISIONS.md](../DECISIONS.md): Aura for production graph; Railway hosts API + Redis only.

## Steps

### 1. Create Aura instance

1. Sign in at [console.neo4j.io](https://console.neo4j.io).
2. **New instance** → **Free** → region close to Railway API (e.g. `us-east-1`).
3. Save connection URI, user (`neo4j`), and password.

### 2. Export from Railway (if data exists)

From a machine that can reach Railway Neo4j:

```bash
export NEO4J_URI=bolt://neo4j-db.railway.internal:7687  # or public proxy if configured
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=<current-railway-password>

uv run python graph/migrate.py
# Optional: dump via neo4j-admin if you have shell access on the container
```

Simplest path for demo data: **re-seed on Aura** instead of dump/restore:

```bash
export NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=<aura-password>

uv run python graph/migrate.py
CORTEX_SEED_DEMO=true uv run python scripts/seed_demo.py --workspace local-dev --scale small
uv run python scripts/import_github_graph.py --org tiangolo --repo fastapi --workspace oss-tiangolo-fastapi --limit 30
```

### 3. Point Railway API at Aura

Railway → **cortex-api** → Variables:

```env
NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=<new-aura-password>
CORTEX_SEED_DEMO=false
```

Redeploy API. Verify:

```bash
curl -s https://cortex-api-production-fbd5.up.railway.app/health | jq .
```

### 4. Rotate credentials

1. Change Aura password in console after migration.
2. Update Railway env vars (never commit passwords).
3. If the old Railway Neo4j password appeared in chat/logs, rotate it and decommission the Railway Neo4j service.

### 5. Uptime

Keep Railway Neo4j stopped or deleted after cutover to avoid split-brain confusion.

See [DEPLOY.md](./DEPLOY.md) and [PORTFOLIO_DEMO.md](./PORTFOLIO_DEMO.md).
