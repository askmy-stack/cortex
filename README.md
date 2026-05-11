# Cortex

**The organizational memory operating system for AI-native companies.**

> Give every AI agent in your organization the same context a senior engineer has — and keep it current as your organization evolves.

---

## The Problem

Every company running AI today has the same silent failure.

Tools think. Agents act. Nothing remembers.

- A Cursor session doesn't know what was decided in the Slack thread
- The support agent doesn't know the sales context from last quarter
- The new engineer's Copilot doesn't know why the architecture was built this way
- The code review bot doesn't know which constraints are architectural vs. temporary

Every AI interaction starts from zero. Every time.

This isn't a model problem. Every major lab has solved reasoning.

**It's a memory infrastructure problem.** And no tool has solved it.

---

## What Cortex Does

```
Captures decisions → Structures them → Injects context → Agents act intelligently
```

**Cortex captures decisions, not documents.**

When your team decides to migrate the payments service to CockroachDB, Cortex captures:

```json
{
  "type": "architectural_decision",
  "decision": "Migrate payments service to CockroachDB",
  "replaces": "PostgreSQL",
  "rationale": ["scale ceiling at 10M txn/day", "multi-region replication needed"],
  "made_by": ["priya@", "dan@"],
  "triggered_by": "incident #247",
  "affects": ["payments-service", "billing-service"],
  "date": "2026-05-09",
  "status": "active"
}
```

Not the Slack message. Not a document. The **decision** — structured, linked, queryable.

**Then Cortex actively injects it.**

When any agent touches the payments service, Cortex enriches its context automatically:

```
"Why does payments use CockroachDB?"
→ Cortex returns: the incident that triggered it, who decided it,
  the tradeoffs discussed, the migration PR, known edge cases since.
→ Agent answers correctly. No hallucination. No archaeology.
```

---

## Key Capabilities

| Capability | Description |
|---|---|
| **Decision capture** | Extracts structured decisions from Slack, GitHub, Jira, Linear, meetings |
| **Knowledge graph** | Neo4j graph: Decision → Person → System → Exception → Outcome |
| **Active injection** | Pushes relevant context to agents before they act — not after they ask |
| **MCP server** | Native MCP endpoint — any Claude, Cursor, or MCP agent gets memory in one config line |
| **Importance scoring** | Filters noise at ingestion — only signal reaches the graph |
| **Trust scoring** | Bayesian confidence per memory node — bad inputs don't corrupt memory |
| **Contradiction detection** | Flags when new events conflict with existing memory — no silent overwrites |
| **Memory decay** | Old memory compresses and archives on a principled schedule |
| **Coverage scoring** | Per-domain completeness estimate — agents know when memory is thin |
| **RBAC** | Graph-level access control — contractors don't see salary decisions |
| **Outcome tracking** | Links decisions to real metrics — memory becomes self-correcting |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  CAPTURE LAYER                                                │
│  Slack · GitHub · Jira · Linear · Meetings · CI/CD          │
│  Real-time event streams via webhooks + OAuth connectors     │
└───────────────────────────────┬──────────────────────────────┘
                                │ Kafka
┌───────────────────────────────▼──────────────────────────────┐
│  EXTRACTION ENGINE                                            │
│  Decision extractor (GPT-4o structured output)              │
│  Entity resolver (spaCy NER → canonical org entities)       │
│  Importance scorer (filters noise before storage)           │
│  Event classifier (decision/exception/rationale/update)     │
└───────────────────────────────┬──────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────┐
│  MEMORY FABRIC                                                │
│  Episodic    → TimescaleDB  what happened and when           │
│  Semantic    → Qdrant       what things mean                 │
│  Structural  → Neo4j        relationships + causal chains    │
│  Procedural  → Neo4j        how things are done              │
│  Hot cache   → Redis        <50ms retrieval for live agents  │
└───────────────────────────────┬──────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────┐
│  INTELLIGENCE LAYER                                           │
│  Contradiction detector · Decay engine · Trust scorer       │
│  Coverage scorer · Outcome linker · RBAC enforcer           │
└───────────────────────────────┬──────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────┐
│  CONTEXT API                                                  │
│  MCP server   · REST API · Python SDK · TypeScript SDK      │
│  cortex.query() · cortex.inject() · cortex.remember()       │
└──────────────────────────────────────────────────────────────┘
```

---

## Quickstart

```bash
# Clone
git clone https://github.com/askmy-stack/cortex
cd cortex

# Configure
cp .env.example .env
# Add: SLACK_BOT_TOKEN, GITHUB_TOKEN, OPENAI_API_KEY (or use local Ollama)

# Run
docker-compose up -d

# Connect your first tool
python scripts/connect_slack.py --workspace your-workspace

# Open dashboard
open http://localhost:3000
```

**Add to any MCP-compatible agent (Claude, Cursor):**

```json
{
  "mcpServers": {
    "cortex": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

That's it. Every agent in your org now has organizational memory.

---

## The Demo

New engineer opens Cursor. Asks:

> *"Why does the payments service use CockroachDB instead of Postgres?"*

Without Cortex: the agent guesses, or says it doesn't know.

With Cortex: the agent returns the incident that triggered the migration, who decided it, why, the tradeoffs that were discussed, the migration PR, and known edge cases discovered since.

Full context. 3 seconds. No Slack archaeology.

---

## Project Structure

```
cortex/
├── connectors/           # Tool connectors (Slack, GitHub, Jira, Linear)
│   ├── slack/
│   ├── github/
│   ├── jira/
│   └── linear/
├── extraction/           # Decision extractor, entity resolver, classifier
├── scoring/              # Importance scorer, trust scorer, coverage scorer
├── graph/                # Neo4j schema, migrations, Cypher queries
│   └── migrations/       # V001__initial_schema.cypher, etc.
├── memory/               # Memory fabric — read/write layer
├── intelligence/         # Contradiction detector, decay engine, outcome linker
├── api/                  # FastAPI application
├── mcp/                  # MCP server (TypeScript)
├── sdk/
│   ├── python/           # cortex-py
│   └── typescript/       # cortex-ts
├── frontend/             # React dashboard
├── infrastructure/       # Terraform, Docker configs
├── tests/
├── scripts/              # Setup, seed data, utilities
├── docs/                 # Architecture diagrams, ADRs
├── CLAUDE.md             # Agent operating instructions
├── SESSIONS.md           # Build session log
├── DECISIONS.md          # Decision log + agent instructions
├── MISTAKES.md           # Errors and learnings
└── ARCHITECTURE.md       # Full system architecture spec
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Event streaming | Apache Kafka |
| Decision extraction | GPT-4o function calling (prod) / Ollama Gemma (dev) |
| NER + entity resolution | spaCy + custom models |
| Knowledge graph | Neo4j 5 |
| Vector store | Qdrant |
| Time-series | TimescaleDB |
| Cache | Redis |
| API | FastAPI + JWT |
| MCP server | TypeScript (MCP SDK) |
| Agent runtime | LangGraph |
| Frontend | React + D3.js (graph explorer) |
| IaC | Terraform + AWS ECS |
| Observability | Prometheus + Grafana |
| ML tracking | MLflow |
| Auth | Auth0 + JWT + DID (agent identity) |

---

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| Phase 1 | Kafka + Slack connector + decision extractor | 🔄 In progress |
| Phase 2 | GitHub + Jira connectors + Neo4j graph schema | ⏳ Planned |
| Phase 3 | `cortex.query()` API + Redis cache + MCP server | ⏳ Planned |
| Phase 4 | Importance scorer + trust scorer + RBAC | ⏳ Planned |
| Phase 5 | Contradiction detector + decay engine | ⏳ Planned |
| Phase 6 | React dashboard + graph explorer | ⏳ Planned |
| Phase 7 | Open-source launch | ⏳ Planned |
| Phase 8 | Outcome tracking + coverage scoring | ⏳ Post-launch |
| Phase 9 | Elicitation bot (implicit knowledge) | ⏳ Post-launch |
| Phase 10 | Federated cross-org memory | ⏳ v2 |

---

## Why This Exists

Every existing solution falls into one of two camps:

**Memory systems** (Mem0, Zep, Cognee) — deep on architecture, no cross-tool capture, single-agent scope, no decision extraction.

**Enterprise search** (Glean, Notion AI, Dust) — deep on connectors, pull-based only, no temporal graph, no causal reasoning, no decision capture.

Cortex is the infrastructure layer in the gap between both camps.

The combination — cross-tool capture + decision extraction + temporal causal graph + active MCP injection + importance scoring + organizational scope — does not exist in any open-source or commercial product.

---

## Research Foundation

Built on:
- **MAGMA** (arXiv:2601.03236) — four-graph memory architecture (semantic/temporal/causal/entity)
- **Zep/Graphiti** (arXiv:2501.13956) — temporal edge invalidation, 90% latency reduction
- **A-MEM** (NeurIPS 2025, arXiv:2502.12110) — Zettelkasten dynamic memory linking
- **Field-Theoretic Memory** (arXiv:2602.21220) — thermodynamic memory decay (+116% F1)
- **SSGM Framework** (arXiv:2603.11768) — memory stability and safety governance
- **Context Engineering** (arXiv:2603.09619) — CE as organizational infrastructure

---

## Author

**Abhinaysai Kamineni** — MS Data Science, George Washington University
[GitHub](https://github.com/askmy-stack) · [LinkedIn](https://linkedin.com/in/abhinaysai-kamineni)

---

## License

Apache 2.0 — use it, fork it, build on it.
