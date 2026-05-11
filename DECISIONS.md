# DECISIONS.md — Decision Log + Agent Instructions

> Two purposes:
> 1. **Abhinaysai:** Add instructions here. Agent reads this every session start.
> 2. **Agent:** Log every architectural or product decision with rationale.

---

## HOW TO ADD INSTRUCTIONS (for Abhinaysai)

Add at the top of ACTIVE INSTRUCTIONS:

```
### [DATE] — [Instruction title]
Priority: HIGH / MEDIUM / LOW
Status: OPEN
Detail: [What to do, as specific as possible]
```

Agent picks up OPEN instructions at session start, executes, marks DONE.

---

## ACTIVE INSTRUCTIONS

### 2026-05-11 — Build Phase 1: Core infrastructure + Slack connector
Priority: HIGH
Status: OPEN
Detail:
- Write `docker-compose.yml`: Kafka, Zookeeper, Neo4j 5, TimescaleDB, Qdrant, Redis, MLflow, Prometheus, Grafana
- Port map: Neo4j 7474/7687, Kafka 9092, Redis 6379, Qdrant 6333, API 8000, Frontend 3000, Grafana 3001
- Create Slack app at api.slack.com — bot token, event subscriptions (message.channels, message.groups)
- Write `connectors/slack/producer.py`:
  - Pydantic model for raw Slack event
  - Kafka producer (confluent-kafka-python)
  - Topic: `cortex.raw.slack.messages`
  - structlog JSON logging on every event
  - pytest unit tests with mocked Kafka + sample Slack payloads
- Write `extraction/decision_extractor.py`:
  - Input: raw Slack message text
  - Output: DecisionEvent Pydantic model (or None if not a decision)
  - GPT-4o function calling in prod, Ollama Gemma locally via OLLAMA_BASE_URL env var
  - Test with 20 real Slack message samples — verify schema correctness
- Validate Neo4j schema against real extracted events before writing graph loader

---

## DECISION LOG

Decisions are immutable once logged. Reversals require a new entry marked `[REVERSAL]`.

---

### D-001 — 2026-05-11 — Kafka as single event bus
**Status:** Active
**Decision:** All inter-service communication goes through Kafka. No synchronous HTTP between pipeline services.
**Rationale:** Connector events are high-volume and time-series. Kafka gives decoupling, persistence, and replay — critical for backtesting importance scorer and trust scorer against historical events. HTTP would couple services and lose the ability to reprocess.
**Topic naming convention:** `cortex.{layer}.{source}.{event_type}`
Examples: `cortex.raw.slack.messages`, `cortex.extracted.decisions`, `cortex.graph.writes`
**Alternatives rejected:** RabbitMQ (no replay), Redis Pub/Sub (no persistence), direct HTTP (tight coupling)
**Owner:** Abhinaysai

---

### D-002 — 2026-05-11 — Neo4j as structural memory store
**Status:** Active
**Decision:** All relationship data and causal structure lives in Neo4j. No relationship logic in application code.
**Rationale:** Organizational memory is fundamentally a graph problem. Multi-hop queries ("what decisions affect this service, made by people who own that team, triggered by incidents in this time range") are native Cypher, not JOIN chains. MAGMA research confirms four-graph separation (semantic/temporal/causal/entity) — Neo4j handles structural + causal; Qdrant handles semantic.
**Schema versioning:** Manual Cypher scripts in `graph/migrations/` — `V{N}__{description}.cypher`
**Alternatives rejected:** PostgreSQL recursive CTEs (painful for multi-hop), Amazon Neptune (cost), TigerGraph (complexity)
**Owner:** Abhinaysai

---

### D-003 — 2026-05-11 — Decision events as atomic memory unit
**Status:** Active
**Decision:** Cortex captures decisions, not text. Every memory write is a structured DecisionEvent, not a raw message.
**Rationale:** Existing tools (Glean, Notion AI, Dust) store text and do semantic search. This retrieves words, not meaning. A decision event captures: what was decided, why, by whom, affecting what, replacing what, with what outcome expectation. This is the organizational unit that agents actually need. Storing text and hoping RAG finds the right sentence is a fundamentally weaker architecture.
**DecisionEvent schema (v1):**
```
type: decision | exception | rationale | update | escalation
content: str
made_by: list[str]           # Canonical person IDs
affects: list[str]           # Canonical system/service IDs
rationale: list[str]
replaces: str | None         # Previous decision this supersedes
triggered_by: str | None     # Incident/ticket/event ID
status: active | superseded | under_review | archived
confidence: float            # Extraction confidence 0-1
source_provenance: dict      # source, channel, timestamp, extractor version
```
**Owner:** Abhinaysai

---

### D-004 — 2026-05-11 — Active injection via MCP, not pull-based retrieval
**Status:** Active
**Decision:** Cortex's primary interface is active context injection via MCP server — not a search UI or pull API.
**Rationale:** Every existing tool is pull-based. Humans or agents must explicitly query. Active injection means Cortex enriches agent prompts automatically based on the agent's current task context — before the agent even knows it needs the information. This is the architectural difference between a search tool and memory infrastructure.
**MCP implementation:** TypeScript MCP server exposing:
- `cortex_query` — explicit query by intent + scope
- `cortex_inject` — auto-enrich a prompt based on extracted intent
- `cortex_remember` — manual write from agent interaction
- `cortex_coverage` — check memory completeness for a domain
**OpenAI-compatible API also exposed** — drop-in for any LLM app not using MCP.
**Owner:** Abhinaysai

---

### D-005 — 2026-05-11 — Importance scoring at ingestion, not retrieval
**Status:** Active
**Decision:** Every event is scored for importance before being written to the graph. Events below threshold are discarded or compressed. Scoring happens in the extraction pipeline, not at query time.
**Rationale:** Production memory systems fail because they store everything and drown in noise — confirmed by multiple 2026 papers. Scoring at retrieval is too late — noise is already in the graph, degrading traversal performance and retrieval quality. Scoring at ingestion keeps the graph clean.
**Algorithm v1:**
```
importance = (
    author_authority_score * 0.25 +
    cross_reference_density * 0.25 +
    system_blast_radius * 0.20 +
    decision_finality_score * 0.20 +
    recency_score * 0.10
)
Thresholds: <0.3 discard | 0.3-0.6 compressed summary | 0.6-0.8 full | >0.8 full + relationship extraction
```
**Owner:** Abhinaysai

---

### D-006 — 2026-05-11 — Bayesian trust scoring with majority voting
**Status:** Active
**Decision:** Every memory node carries a trust score computed via Bayesian model. Writes require cross-source corroboration before high-trust classification. CMVK (Cross-Model Verification Kernel) pattern from Microsoft Agent Governance Toolkit used for multi-verifier majority voting.
**Rationale:** MINJA research shows 95%+ injection success rates against production agents. Memory poisoning is OWASP ASI06 — top agentic AI risk 2026. Trust scoring at write time prevents bad inputs from corrupting organizational memory permanently.
**Trust levels:** quarantined (<0.4) | low-confidence (0.4-0.7) | trusted (>0.7)
**Provenance required:** every node stores source + extractor + verifier + confidence score
**Owner:** Abhinaysai

---

### D-007 — 2026-05-11 — Thermodynamic memory decay model
**Status:** Active
**Decision:** Memory relevance decays over time using a thermodynamic model (Field-Theoretic Memory, arXiv:2602.21220). No memory is deleted by decay — it compresses and archives.
**Rationale:** Field-theoretic approach achieved +116% F1 on multi-session reasoning, +43.8% temporal reasoning vs. discrete memory baselines. Unaccessed memories decay naturally; frequently accessed memories resist decay. This prevents the graph from becoming organizational debt.
**Decay function:** `relevance(t) = initial_importance × e^(-λt) × access_boost(t)`
**Lifecycle:** ACTIVE (>0.6) → WARM (0.3-0.6) → COLD (0.1-0.3, compressed) → ARCHIVED (<0.1) → DELETED (GDPR or TTL)
**GDPR:** Right to Erasure triggers immediate cascade delete with audit log.
**Owner:** Abhinaysai

---

### D-008 — 2026-05-11 — Graph-level RBAC with DID agent identity
**Status:** Active
**Decision:** Access control enforced at graph query level. Every memory node carries an access policy. Every caller (human or agent) has a DID (Decentralized Identifier). All Cypher queries automatically scoped by caller identity.
**Rationale:** Application-layer permission filtering is brittle and easy to bypass. Graph-level enforcement means no code path can accidentally expose restricted memory. DID gives agents a portable, verifiable identity standard — aligns with Microsoft Agent Governance Toolkit and emerging agent identity standards.
**Node access policy structure:**
```
access_policy: {
  roles: [list of allowed roles],
  deny: [list of explicitly denied identities],
  classification: public | internal | confidential | restricted,
  gdpr_subject: bool
}
```
**Must be built before any data is stored.** Non-negotiable.
**Owner:** Abhinaysai

---

### D-009 — 2026-05-11 — GPT-4o production, Ollama Gemma development
**Status:** Active
**Decision:** Decision extraction uses GPT-4o with function calling in production. Local Ollama + Gemma 4 E4B in development. Switched via `EXTRACTION_BACKEND` env var.
**Rationale:** GPT-4o function calling gives reliable structured DecisionEvent output. Local Gemma avoids API costs during iteration (development generates hundreds of test calls per session). Same extraction interface — backend is swappable.
**Cost controls:** Cache extraction results by content hash — identical messages never call API twice. Batch extraction every 60 seconds — never per-event in real-time.
**Owner:** Abhinaysai

---

### D-010 — 2026-05-11 — Apache 2.0 license
**Status:** Active
**Decision:** Apache 2.0 for all open-source components.
**Rationale:** Permissive — allows commercial use, maximizing enterprise adoption and contributor network. Standard for AI infrastructure open-source (Airflow, Kafka, LangChain, LangGraph all Apache 2.0). GPL would scare enterprise users. MIT has no patent protection clause.
**Owner:** Abhinaysai

---

### D-011 — 2026-05-11 — LangGraph for agent orchestration
**Status:** Active
**Decision:** Agent workflows built with LangGraph.
**Rationale:** LangGraph is the production leader for stateful agent orchestration (confirmed by December 2025 market analysis). Supports durable state across steps, human-in-the-loop approval workflows (required for contradiction resolution), and streaming. CrewAI and AutoGen considered but LangGraph has better production track record and Anthropic alignment.
**Owner:** Abhinaysai

---

### D-012 — 2026-05-11 — 4-week MVP, open-source launch week 5
**Status:** Active
**Decision:** MVP shipped in 4 weeks. Open-source launch (HN, LinkedIn, dev.to) in week 5.
**MVP scope:**
- Slack + GitHub connectors
- Decision extractor + importance scorer (basic)
- Neo4j graph with core schema
- `cortex.query()` REST API
- MCP server
- React dashboard (read-only, graph explorer)
- Demo video (3 min max)
- README with animated GIF
**NOT in MVP:** Trust scorer, contradiction detector, decay engine, outcome tracker, Jira/Linear connectors, RBAC (basic auth only), elicitation bot
**Rationale:** Ship something real. Extend after traction. The Jira connector, decay engine, and RBAC can be added as community contributions once the repo has stars.
**Owner:** Abhinaysai

---

## PENDING DECISIONS (need resolution before build)

| # | Decision needed | Options | Deadline | Status |
|---|---|---|---|---|
| P-001 | MCP server language | TypeScript (MCP SDK native) / Python (FastMCP) | Before Phase 3 | Open |
| P-002 | Local Slack message storage for testing | Real Slack workspace / Slack test fixture files | Before Phase 1 | Open |
| P-003 | Neo4j hosting for production | Neo4j AuraDB free tier / Self-hosted EC2 | Before Phase 7 | Open |
| P-004 | Dashboard visualization library | D3.js (full control) / React Flow (faster) | Before Phase 6 | Open |
| P-005 | Meeting transcript connector | Recall.ai / AssemblyAI / Whisper self-hosted | Before Phase 8 | Open |
