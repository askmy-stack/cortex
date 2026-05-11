# SESSIONS.md — Build Session Log

> Every session logged here. Read the last 2 entries before starting any new session.
> Format: Date · What was built · What broke · What's next.

---

## How to use this file

**Agent:** Read last 2 entries at session start. Append new entry at session end using template below.

**Owner (Abhinaysai):** Add corrections or context in `[OWNER NOTES]` blocks. Flag anything that needs re-evaluation.

---

## Session Template

```
---
## Session [N] — [DATE]
**Duration:** Xh Ym
**Phase:** [Phase name and number]

### Built
- [Completed items — be specific, include file paths]

### State at end
- [What works / what is broken / what is untested]

### Decisions made
- [Any decisions — also log to DECISIONS.md]

### Blockers
- [What is blocking next steps]

### Mistakes found
- [Any false assumptions or errors — also log to MISTAKES.md]

### Next session starts with
- [Exact first task — no ambiguity]

[OWNER NOTES]
- [Abhinaysai adds corrections or context here]
```

---

## Session 0 — 2026-05-11
**Duration:** ~5h (research + ideation + architecture + documentation sprint)
**Phase:** Phase 0 — Concept, Research, and Architecture

### Built

**Research completed:**
- Full literature review: MAGMA (arXiv:2601.03236), Zep/Graphiti (arXiv:2501.13956), A-MEM (NeurIPS 2025), Mem0 (ECAI 2025), SSGM Framework (arXiv:2603.11768), Context Engineering paper (arXiv:2603.09619), Field-Theoretic Memory (arXiv:2602.21220)
- Market landscape analysis: Mem0, Zep, Cognee, Dust, Glean, Coworker.ai, Cloudflare Agent Memory — none covers Cortex's combination
- Gap analysis: 8 structural gaps identified with research-grounded solutions for each
- Gartner validation: context engineering declared top AI skill 2026, 80% of AI tools by 2028
- Enterprise validation: 78% of enterprises have pilots, only 14% scaled — memory/context gap confirmed

**Product definition completed:**
- Core thesis: AI tools are stateless. Organizations are not. Memory infrastructure is the fix.
- Three core differentiators: decision capture (not docs), active injection (not retrieval), MCP-native
- Four memory types: episodic (TimescaleDB), semantic (Qdrant), structural (Neo4j), procedural (Neo4j)
- Importance scoring algorithm: author authority (0.25) + cross-reference density (0.25) + blast radius (0.20) + decision finality (0.20) + recency (0.10)
- Contradiction detector design: flags conflicts → notifies owners → suspends agent actions → human resolution
- Memory decay model: thermodynamic (Field-Theoretic Memory paper) — field-based diffusion and decay

**Architecture completed:**
- 5-layer system: capture → extraction → memory fabric → intelligence → context API
- Full connector list: Slack, GitHub, Jira, Linear, meetings, CI/CD
- Neo4j schema: Decision, Person, System, Exception, Outcome, Team nodes + typed edges
- RBAC design: graph-level ACL, DID identity, GDPR cascade delete
- Gap solutions mapped to build phases (8 gaps, 8 solutions, phased implementation)

**All 6 documentation files created:**
- `CLAUDE.md` — agent operating instructions, code standards, architecture rules
- `README.md` — public-facing product documentation, quickstart, architecture diagram
- `SESSIONS.md` — this file
- `DECISIONS.md` — 12 decisions logged (D-001 through D-012), active instructions
- `MISTAKES.md` — 6 mistakes + 5 learnings pre-logged from research
- `ARCHITECTURE.md` — full system specification, Neo4j schema, API design, build phases

### State at end
- All documentation complete and internally consistent
- Zero code written
- Zero infrastructure provisioned
- Architecture validated against research — all design decisions have paper backing
- Neo4j schema designed but not validated against real connector output schemas yet

### Decisions made
- Kafka as single event bus (D-001)
- Neo4j as knowledge graph (D-002)
- Decision events as atomic memory unit, not raw text (D-003)
- Active injection via MCP, not pull-based retrieval (D-004)
- Importance scoring at ingestion, not at retrieval (D-005)
- Bayesian trust scoring with majority voting (D-006)
- Thermodynamic decay model (D-007)
- Graph-level RBAC with DID identity (D-008)
- GPT-4o for production extraction, Ollama Gemma for development (D-009)
- Apache 2.0 license (D-010)
- LangGraph for agent orchestration (D-011)
- 4-week MVP target with open-source launch week 5 (D-012)

### Blockers
- Slack app not yet created (need OAuth tokens for connector)
- GitHub OAuth app not yet registered
- OpenAI API key for production extraction not confirmed
- Neo4j local instance not running
- Kafka Docker Compose not written

### Mistakes found
- See MISTAKES.md M-001 through M-006

### Next session starts with
1. `docker-compose.yml` — Kafka, Zookeeper, Neo4j, PostgreSQL, TimescaleDB, Qdrant, Redis
2. Slack app creation at api.slack.com — get bot token, configure event subscriptions
3. First connector: `connectors/slack/producer.py` — Pydantic schema, Kafka publish, structlog
4. First extraction test: run 10 real Slack messages through GPT-4o → verify decision event schema
5. Validate Neo4j schema against real extracted events — adjust before writing graph loader

[OWNER NOTES]
- Cortex emerged as the second major portfolio project alongside Meridian
- Core insight: the market gap between memory systems (Mem0, Zep) and enterprise search (Glean, Dust) is exactly where Cortex sits — confirmed by Foundation Capital context graph thesis
- Key differentiator confirmed by research: importance scoring (noise filter) is the unsolved production problem — every system drowns in noise. Cortex solves it at ingestion.
- MCP adoption by OpenAI, Google, Microsoft (2025) makes MCP server the right distribution mechanism
- Demo scenario: new engineer asks Cursor "why CockroachDB?" → full decision history returned in 3 seconds
- This project targets AI Infrastructure Engineer roles — different hiring pool from Meridian (Data/MLOps)
