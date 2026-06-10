# CLAUDE.md — Agent Operating Instructions for Cortex

> Primary instruction set for any AI agent working on Cortex.
> Read this before touching any file, writing any code, or making any decision.
> Update when operating rules change.

---

## What is Cortex

Cortex is an open-source **Organizational Memory Operating System** for AI-native companies.

It captures decisions (not just documents) from every tool in an organization — Slack, GitHub, Jira, Linear, meetings, CI/CD — structures them into a living knowledge graph, and actively injects relevant context into any AI agent at inference time via MCP.

**Thesis:** AI tools are stateless. Organizations are not. Every AI interaction starting from zero is a memory infrastructure failure — not a model failure. Cortex is the memory fabric that fixes it.

**Core differentiation:**
- Captures **decisions**, not text
- **Active injection** at inference time — not passive retrieval
- **MCP-native** — zero integration work for any agent
- **Organizational scope** — cross-tool, cross-agent, persistent
- **Importance scoring** — the unsolved noise problem, solved at ingestion

---

## Owner

**Abhinaysai Kamineni**
MS Data Science, George Washington University (May 2026)
Arlington, VA | kamineniabhinaysai@gmail.com
GitHub: github.com/askmy-stack
LinkedIn: linkedin.com/in/abhinaysai-kamineni

**Portfolio context:** Cortex targets AI Infrastructure Engineer, AI Platform Engineer, and MLOps roles at Series B+ AI-native companies ($150K+). Every build decision should maximize technical depth, open-source virality, and recruiter legibility — in that order.

---

## Agent Operating Rules

### Before every session
1. Read `SESSIONS.md` — last 2 entries minimum. Know exactly what was built and what broke.
2. Read `DECISIONS.md` — check ACTIVE INSTRUCTIONS block first. Execute any OPEN instructions.
3. Read `MISTAKES.md` — don't repeat known errors. Add new ones when found.
4. Check `ARCHITECTURE.md` — know current system state before proposing changes.

### Session discipline
- Start every session by stating: current phase, what was done last, what this session will complete
- End every session by updating `SESSIONS.md` with a full log entry
- Any decision made during a session → log to `DECISIONS.md` immediately
- Any mistake or false assumption found → log to `MISTAKES.md` immediately

### Code standards
- Python 3.11+ for all backend services
- TypeScript for MCP server and SDK
- Type hints on every function — no exceptions
- Docstrings on every class and public method
- No hardcoded credentials — `.env` + `python-dotenv` always
- One `Dockerfile` per service — `docker-compose.yml` at root
- Tests in `/tests/` — pytest for Python, Vitest for TypeScript
- Logging via `structlog` (Python) — structured JSON, never `print()`
- Every service exposes `/health` endpoint

### Architecture rules — non-negotiable
- **Kafka is the single event bus.** No point-to-point HTTP between pipeline services.
- **Neo4j is the source of truth for all relationships.** No relationship logic in application code.
- **Every memory write goes through importance scorer first.** Never write raw events directly to graph.
- **Every memory write goes through trust scorer second.** No memory stored without provenance chain.
- **RBAC is enforced at graph query level.** No application-layer permission filtering.
- **Contradiction detector runs on every write.** No silent overwrites of existing memory.
- **MCP server is agent-neutral.** Never assume a specific agent — any MCP-compatible client must work.
- **LLM extracts structure, never scores trust.** LLM output is input to scoring — never the score itself.
- **All ML experiments tracked in MLflow.** No untracked model runs.

### What NOT to do
- Do not store full conversation history — extract decisions and compress
- Do not use vector similarity as the only retrieval mechanism — graph traversal for relationships
- Do not write to memory without provenance (source, extractor, confidence score)
- Do not build dashboard before core memory pipeline works — API first, always
- Do not use synchronous HTTP between services at scale — Kafka or async
- Do not expose memory nodes without RBAC check — even in development
- Do not skip importance scoring — noise destroys retrieval quality
- Do not assume graph is complete — always return coverage score with query results
- Do not hardcode connector logic — connectors are plugins, not core

### Response style (for Claude specifically)
- No filler words. No preambles. No hedging.
- Execution-first: write code, then explain if needed
- When stuck: state blocker clearly, propose 2 options, ask for decision
- Reference `DECISIONS.md` before proposing any architectural change
- Reference `MISTAKES.md` before implementing anything that previously broke

---

## Current Phase

**Phase:** 4 — Importance scorer + trust scorer + RBAC (PR #12 open)
**Status:** Phase 2 complete (PR #11); Phase 4 in review
**Next phase:** Phase 5 — Contradiction detector + decay engine
**Target:** Working MVP demo in 4 weeks

---

## Build Phases Overview

| Phase | Scope | Duration | Status |
|---|---|---|---|
| 0 | Architecture + documentation | Complete | ✅ Done |
| 1 | Kafka + Slack connector + decision extractor | Week 1 | ✅ Done |
| 2 | GitHub + Jira connectors + Neo4j graph schema | Week 1-2 | ✅ Done |
| 3 | `cortex.query()` API + Redis cache + MCP server | Week 2 | ⏳ |
| 4 | Importance scorer + trust scorer + RBAC | Week 2-3 | ⏳ |
| 5 | Contradiction detector + decay engine | Week 3 | ⏳ |
| 6 | React dashboard + knowledge graph explorer | Week 3-4 | ⏳ |
| 7 | Demo video + README polish + open-source launch | Week 4 | ⏳ |
| 8 | Outcome tracking + coverage scoring | Post-launch | ⏳ |
| 9 | Behavioral mining + elicitation bot | Post-launch | ⏳ |
| 10 | Federated cross-org memory | v2 | ⏳ |

---

## Hardware Constraints

| Constraint | Detail |
|---|---|
| Primary machine | HP ZBook 15 G5 — Intel i7-8850H, 48GB RAM, NVIDIA Quadro P2000 4GB VRAM |
| OS | Windows 11 Pro + WSL2 (Ubuntu) |
| Local LLM | Ollama + Gemma 4 E4B — ~10GB RAM, 8-12 tok/s CPU |
| Secondary | MacBook Air (development), iPhone (SSH via Termius + Tailscale) |
| Cloud budget | Minimize — free tiers only for MVP |
| Timeline | 4-week MVP, open-source launch week 5 |
| Portfolio goal | Demo-able in under 3 minutes. GitHub README must be self-explanatory. |

---

## LLM Usage Policy

| Task | Model | Reason |
|---|---|---|
| Decision extraction (dev) | Ollama Gemma 4 E4B (local) | Zero API cost during iteration |
| Decision extraction (prod) | GPT-4o with function calling | Reliable structured output |
| Entity resolution | spaCy custom NER | Fast, no API cost, domain-tunable |
| Importance scoring | Rule-based + XGBoost | No LLM — deterministic, testable |
| Trust scoring | Bayesian model | No LLM — auditable |
| Contradiction detection | LLM-assisted | GPT-4o mini — low cost, high accuracy |
| Context narrative (weekly digest) | GPT-4o | Quality matters for user-facing output |

**Rule:** LLM extracts structure. Never scores. Never decides trust. Never writes directly to graph.

---

## Glossary

| Term | Definition |
|---|---|
| Decision event | Atomic unit of organizational memory — a structured capture of what was decided, why, by whom, affecting what |
| Memory node | A single entity in the Neo4j graph (decision, person, system, exception, etc.) |
| Memory edge | A typed relationship between nodes (made_by, affects, triggered_by, replaces, etc.) |
| Importance score | 0-1 signal computed at ingestion — determines whether event is stored |
| Trust score | 0-1 Bayesian confidence per memory node — updated by corroboration and outcome validation |
| Coverage score | Per-domain estimate of how complete the memory graph is |
| Contradiction | A new event that conflicts with an existing memory node |
| Active injection | Cortex pushing relevant context into an agent prompt before inference — not waiting for a query |
| MOS | Memory Operating System — internal acronym for Cortex |
| RBAC | Role-Based Access Control — enforced at graph query level, not application level |
| DID | Decentralized Identifier — agent identity standard used for access control |
| Provenance chain | source → extractor → verifier → confidence — required on every memory write |
| Decay | Natural reduction of memory relevance over time — thermodynamic model |
| Elicitation | Structured async process to extract implicit knowledge from engineers via targeted questions |
