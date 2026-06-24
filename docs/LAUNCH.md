# Phase 7 — Open-source launch checklist

Use this when posting to HN, LinkedIn, and GitHub.

## Assets

- [ ] Live demo: https://frontend-ten-rouge-99.vercel.app (or custom domain — [CUSTOM_DOMAIN.md](./CUSTOM_DOMAIN.md))
- [ ] 3-min video: [DEMO_RECORDING.md](./DEMO_RECORDING.md) (cloud + local scripts)
- [ ] README **Live demo** badge at top
- [ ] MCP wiring: [MCP_SETUP.md](./MCP_SETUP.md)

## Smoke before posting

```bash
make verify-production          # health + query against Railway
make verify-dual-production     # local-dev + oss-tiangolo-fastapi
```

## Hacker News (Show HN draft)

**Title:** Show HN: Cortex – organizational memory OS for AI agents (Neo4j + MCP)

**Body:**

Cortex captures **decisions** (not documents) from Slack, GitHub, Jira, etc., stores them in a knowledge graph, and injects relevant context into agents via MCP at inference time.

Live demo (no install): https://frontend-ten-rouge-99.vercel.app  
Try workspace `local-dev`, query: *Why CockroachDB for payments?*

Stack: Kafka ingestion pipeline, Neo4j graph, importance/trust scoring, contradiction detection, FastAPI query layer, React dashboard, TypeScript MCP server.

GitHub: https://github.com/askmy-stack/Cortex

Feedback welcome — especially on the “active injection vs passive RAG” thesis.

## LinkedIn post (draft)

Shipped a live demo of **Cortex** — an organizational memory OS for AI-native teams.

Instead of dumping docs into a vector DB, Cortex:
- Extracts **decisions** from Slack, GitHub, Jira
- Scores importance + trust at ingestion
- Stores relationships in **Neo4j**
- Injects context into any MCP agent at inference time

Try it: https://frontend-ten-rouge-99.vercel.app  
Query: *Why CockroachDB for payments?* (workspace: local-dev)

Open source: github.com/askmy-stack/Cortex  
#AI #MLOps #OpenSource #KnowledgeGraph

## Optional v2 (post-launch)

- Cloud webhook → API → graph write (bypass Kafka for demo) — see [DEPLOY.md](./DEPLOY.md)
- Railway worker service for live GitHub ingestion
- Contradiction pair in Review tab for demo narrative

## CI

Scheduled production smoke: `.github/workflows/production-smoke.yml` (optional `CORTEX_PRODUCTION_URL` secret).
