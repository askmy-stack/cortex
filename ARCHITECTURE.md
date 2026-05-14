# ARCHITECTURE.md — System Architecture Specification

> Living document. Update on every architectural change.
> Never delete old versions — mark deprecated and move to version history.

---

## Current Version: v0.1 — Design Phase
**Status:** Design only — no code written
**Date:** 2026-05-11
**Research foundation:** MAGMA (arXiv:2601.03236), Zep/Graphiti (arXiv:2501.13956), A-MEM (NeurIPS 2025), Field-Theoretic Memory (arXiv:2602.21220), SSGM Framework (arXiv:2603.11768)

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 1: CAPTURE                                                     │
│  Slack · GitHub · Jira · Linear · Meetings (transcripts) · CI/CD    │
│  Real-time webhooks + OAuth — events published to Kafka             │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │ Kafka topics
┌──────────────────────────────────▼───────────────────────────────────┐
│  LAYER 2: EXTRACTION ENGINE                                           │
│  Decision extractor  → structured DecisionEvent from raw text       │
│  Entity resolver     → canonical org entities (person, system, team) │
│  Event classifier    → decision | exception | rationale | update     │
│  Importance scorer   → 0-1 signal, discard/compress/store           │
│  Trust scorer        → Bayesian confidence + provenance chain       │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │ Scored, structured events
┌──────────────────────────────────▼───────────────────────────────────┐
│  LAYER 3: MEMORY FABRIC                                               │
│  Episodic    → TimescaleDB   (what happened and when)               │
│  Semantic    → Qdrant        (what things mean — vector search)     │
│  Structural  → Neo4j         (relationships, causality, ownership)  │
│  Procedural  → Neo4j         (how things are done, runbooks)        │
│  Hot cache   → Redis         (<50ms retrieval for live agents)      │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
┌──────────────────────────────────▼───────────────────────────────────┐
│  LAYER 4: INTELLIGENCE                                                │
│  Contradiction detector   → flags conflicting memories              │
│  Decay engine             → thermodynamic relevance decay           │
│  Coverage scorer          → per-domain completeness estimate        │
│  Outcome linker           → connects decisions to real metrics      │
│  RBAC enforcer            → graph-level access control per caller   │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
┌──────────────────────────────────▼───────────────────────────────────┐
│  LAYER 5: CONTEXT API                                                 │
│  MCP server (TypeScript)  → Claude, Cursor, any MCP agent           │
│  REST API (FastAPI)        → custom integrations                    │
│  Python SDK               → cortex-py                              │
│  TypeScript SDK           → cortex-ts                              │
│  OpenAI-compatible API    → drop-in for any LLM app                │
└──────────────────────────────────────────────────────────────────────┘

CROSS-CUTTING:
  Storage:       PostgreSQL (org config) · TimescaleDB · Neo4j · Qdrant · Redis
  Observability: Prometheus + Grafana
  ML tracking:   MLflow
  Auth:          Auth0 + JWT + DID (Decentralized Identifier for agents)
  IaC:           Docker Compose (local) → Terraform + AWS ECS (production)
```

---

## Layer 1: Capture — Connector Architecture

### Design principle
Connectors are stateless plugins. They transform tool events into a standard `RawEvent` schema and publish to Kafka. No business logic in connectors.

### Kafka topic naming convention
`cortex.{layer}.{source}.{event_type}`

| Topic | Publisher | Consumer |
|---|---|---|
| `cortex.raw.slack.messages` | Slack connector | Extraction engine |
| `cortex.raw.github.commits` | GitHub connector | Extraction engine |
| `cortex.raw.github.prs` | GitHub connector | Extraction engine |
| `cortex.raw.github.comments` | GitHub connector | Extraction engine |
| `cortex.raw.jira.issues` | Jira connector | Extraction engine |
| `cortex.raw.jira.comments` | Jira connector | Extraction engine |
| `cortex.raw.linear.issues` | Linear connector | Extraction engine |
| `cortex.raw.meetings.transcripts` | Meeting connector | Extraction engine |
| `cortex.extracted.decisions` | Extraction engine | Graph writer |
| `cortex.extracted.entities` | Entity resolver | Graph writer |
| `cortex.graph.writes` | Graph writer | Memory fabric |
| `cortex.intelligence.contradictions` | Contradiction detector | Human review queue |
| `cortex.intelligence.outcomes` | Outcome linker | Graph updater |

**Implementation note (MVP code):** GitHub and Jira use aggregate topics `cortex.raw.github.events` and `cortex.raw.jira.events` so the extraction worker can subscribe once per source; `RawEvent.event_type` carries PR/issue/comment granularity. The per-event-type topic names in earlier rows remain the documented scale-out target.

### RawEvent schema (all connectors output this)
```python
class RawEvent(BaseModel):
    event_id: str               # UUID4
    source: str                 # "slack" | "github" | "jira" | "linear" | "meeting"
    source_id: str              # Original ID from the tool
    workspace_id: str           # Org identifier
    event_type: str             # "message" | "commit" | "pr" | "comment" | etc.
    content: str                # Raw text content
    author: str                 # Canonical author ID (email or username)
    channel: str                # Channel, repo, project, etc.
    timestamp: datetime         # UTC
    metadata: dict              # Source-specific fields
    schema_version: str         # "1.0"
    ingested_at: datetime       # UTC
```

### Connector inventory

| Connector | Status | Auth | Event types | Notes |
|---|---|---|---|---|
| Slack | Phase 1 | OAuth + Bot token | messages, threads | Event subscriptions API |
| GitHub | Phase 2 | OAuth App | commits, PRs, PR comments, issues | Webhooks |
| Jira | Phase 2 | OAuth 2.0 | issues, comments, transitions | REST API + webhooks |
| Linear | Phase 2 | OAuth | issues, comments | GraphQL API |
| Meetings | Phase 8 | Recall.ai / AssemblyAI | transcripts | Post-meeting trigger |
| CI/CD | Phase 9 | Webhook | deploys, pipeline events | GitHub Actions / Jenkins |

---

## Layer 2: Extraction Engine

### Decision extractor

**Input:** `RawEvent`
**Output:** `DecisionEvent | None`

```python
class DecisionEvent(BaseModel):
    # Identity
    event_id: str                     # UUID4
    source_raw_event_id: str          # RawEvent this was extracted from
    workspace_id: str

    # Classification
    event_type: Literal[
        "decision", "exception", "rationale", "update", "escalation"
    ]

    # Content
    content: str                      # Clean summary of the decision
    made_by: list[str]                # Canonical person IDs
    affects: list[str]                # Canonical system/service/team IDs
    rationale: list[str]              # Reasons given
    replaces: str | None              # Decision ID this supersedes
    triggered_by: str | None          # Incident/ticket ID
    status: Literal[
        "active", "superseded", "under_review", "archived"
    ]

    # Quality signals
    extraction_confidence: float      # 0-1, LLM confidence
    importance_score: float           # Computed by importance scorer
    trust_score: float                # Computed by trust scorer

    # Provenance (required on every write)
    provenance: dict = {
        "source": str,
        "channel": str,
        "original_timestamp": datetime,
        "extractor_version": str,
        "extractor_model": str,
        "verified_by": list[str]      # Verifier IDs from CMVK
    }

    extracted_at: datetime
```

**LLM prompt pattern (GPT-4o function calling):**
```
System: You are an organizational memory extractor. Your job is to identify
        if a message contains an organizational decision, exception, or rationale.
        If it does, extract it into the provided schema.
        Be conservative — only extract when confident a real decision was made.
        Do not hallucinate decisions from casual conversation.

User: [raw message text + thread context window]

Function: extract_decision_event → DecisionEvent schema
```

**Confidence thresholds:**
- Below 0.4: discard, do not write
- 0.4 to 0.7: write to human review queue
- Above 0.7: pass to importance scorer

### Entity resolver

Maps free-text mentions to canonical org entities.

**Input:** raw text containing entity mentions
**Output:** `EntityResolution` — canonical IDs + confidence

**Approach:**
1. spaCy NER (PERSON, ORG, PRODUCT) on raw text
2. Fuzzy match against known entities in Neo4j
3. Confidence-weighted canonical ID assignment
4. Unknown entities → create new node with `status: unverified`

### Importance scorer

**Algorithm v1:**

```python
def importance_score(event: DecisionEvent) -> float:
    author_authority = get_author_authority(event.made_by)
    # Computed from: org role, decision history, how often referenced by others

    cross_reference = get_cross_reference_density(event)
    # Count: how many other recent events reference same systems/people

    blast_radius = get_blast_radius(event.affects)
    # High: payments, auth, core infra
    # Low: README, internal tooling, docs

    finality = get_decision_finality(event.content)
    # "we decided" = 1.0, "maybe we should" = 0.2, "just wondering" = 0.0

    recency = compute_recency(event.extracted_at)
    # Exponential decay — events from today score higher than events from last month

    return (
        author_authority * 0.25 +
        cross_reference * 0.25 +
        blast_radius * 0.20 +
        finality * 0.20 +
        recency * 0.10
    )

# Action thresholds:
# < 0.30: discard entirely
# 0.30-0.60: store compressed 3-sentence summary only
# 0.60-0.80: store full DecisionEvent
# > 0.80: store full + extract relationships + notify relevant agents
```

### Trust scorer

**Bayesian model — SuperLocalMemory pattern (arXiv:2603.02240):**

```python
def trust_score(event: DecisionEvent) -> float:
    # Prior: source credibility
    source_prior = {
        "slack_thread_with_reactions": 0.75,
        "github_pr_description": 0.80,
        "jira_ticket_resolution": 0.85,
        "slack_single_message": 0.55,
        "github_comment": 0.60,
    }

    # Update 1: corroboration — same fact in N independent sources
    corroboration_boost = min(0.20, corroboration_count * 0.05)

    # Update 2: author authority weight
    authority_boost = author_authority * 0.10

    # Update 3: contradiction penalty
    contradiction_penalty = -0.30 if contradicts_existing_memory else 0.0

    return min(1.0, source_prior + corroboration_boost +
               authority_boost + contradiction_penalty)

# Trust levels:
# < 0.40: QUARANTINED — stored but never injected into agents
# 0.40-0.70: LOW_CONFIDENCE — stored with label, human review suggested
# > 0.70: TRUSTED — stored and available for injection
```

**CMVK (Cross-Model Verification Kernel) for high-stakes decisions:**
Events with importance > 0.8 are verified by 3 independent LLM verifiers before write. Majority vote required. Disagreement → quarantine + human review.

---

## Layer 3: Memory Fabric

### Neo4j Schema v0.1

#### Node types

```cypher
// Decision — core memory unit
(:Decision {
  id: String,              // UUID
  workspace_id: String,
  event_type: String,      // "decision" | "exception" | "rationale" | "update"
  content: String,
  status: String,          // "active" | "superseded" | "under_review" | "archived"
  importance_score: Float,
  trust_score: Float,
  relevance_score: Float,  // Updated by decay engine
  extracted_at: DateTime,
  valid_at: DateTime,      // When this became true
  invalid_at: DateTime,    // When this was superseded (null if still active)
  access_policy: Map,      // RBAC configuration
  provenance: Map          // source, extractor, verifier chain
})

// Person — org member or agent
(:Person {
  id: String,              // Canonical email or DID
  workspace_id: String,
  name: String,
  role: String,
  team: String,
  authority_score: Float,  // Updated from decision history
  is_agent: Boolean,       // True for AI agents
  access_roles: [String]   // RBAC roles
})

// System — service, component, or infrastructure
(:System {
  id: String,
  workspace_id: String,
  name: String,
  type: String,            // "service" | "database" | "infra" | "library"
  owner_team: String,
  criticality: String,     // "high" | "medium" | "low"
  blast_radius_score: Float
})

// Exception — a known failure mode or edge case
(:Exception {
  id: String,
  workspace_id: String,
  description: String,
  system_id: String,
  resolution: String,
  recurrence_count: Integer,
  first_seen: DateTime,
  last_seen: DateTime
})

// Outcome — measured result of a decision
(:Outcome {
  id: String,
  decision_id: String,
  metric_name: String,
  metric_source: String,   // "datadog" | "cloudwatch" | "custom"
  target_value: Float,
  actual_value: Float,
  target_met: Boolean,
  measured_at: DateTime,
  side_effects: Map
})

// Team — organizational unit
(:Team {
  id: String,
  workspace_id: String,
  name: String,
  domain: [String],        // Areas this team owns
  lead_id: String
})
```

#### Edge types

```cypher
// Decision relationships
(:Decision)-[:MADE_BY {role: String}]->(:Person)
(:Decision)-[:AFFECTS {impact_level: String}]->(:System)
(:Decision)-[:AFFECTS {impact_level: String}]->(:Team)
(:Decision)-[:REPLACES {reason: String}]->(:Decision)
(:Decision)-[:TRIGGERED_BY {context: String}]->(:Exception)
(:Decision)-[:HAS_OUTCOME]->(:Outcome)
(:Decision)-[:RATIONALE_FOR]->(:Decision)

// System relationships
(:System)-[:OWNED_BY]->(:Team)
(:System)-[:DEPENDS_ON {criticality: String}]->(:System)
(:System)-[:HAS_EXCEPTION]->(:Exception)

// Person relationships
(:Person)-[:MEMBER_OF]->(:Team)
(:Person)-[:OWNS]->(:System)

// Temporal validity (Zep/Graphiti pattern)
// All edges carry: valid_at, invalid_at (null = still active)
// This enables: "what did we believe about this system on 2025-12-01?"
```

#### Key Cypher queries

```cypher
// What decisions affect a given service?
MATCH (d:Decision)-[:AFFECTS]->(s:System {name: "payments-service"})
WHERE d.status = "active"
  AND d.workspace_id = $workspace_id
  AND cortex.rbac_check(d.access_policy, $caller_roles) = true
RETURN d
ORDER BY d.importance_score DESC, d.valid_at DESC

// Full decision context for a system (multi-hop)
MATCH (s:System {name: "payments-service"})
MATCH (d:Decision)-[:AFFECTS]->(s)
MATCH (d)-[:MADE_BY]->(p:Person)
OPTIONAL MATCH (d)-[:REPLACES]->(prev:Decision)
OPTIONAL MATCH (d)-[:TRIGGERED_BY]->(e:Exception)
OPTIONAL MATCH (d)-[:HAS_OUTCOME]->(o:Outcome)
WHERE d.status = "active"
  AND cortex.rbac_check(d.access_policy, $caller_roles) = true
RETURN d, p, prev, e, o

// Contradiction check before write
MATCH (existing:Decision)-[:AFFECTS]->(s:System)
WHERE s.id IN $new_decision_affects
  AND existing.status = "active"
  AND existing.workspace_id = $workspace_id
RETURN existing

// Decision lineage (causal chain)
MATCH path = (d:Decision)-[:REPLACES*1..10]->(:Decision)
WHERE d.id = $decision_id
RETURN path

// Coverage score per domain
MATCH (s:System {type: "service"})
WHERE s.workspace_id = $workspace_id
OPTIONAL MATCH (d:Decision)-[:AFFECTS]->(s)
WHERE d.extracted_at > datetime() - duration({days: 90})
RETURN s.name,
       count(d) as decision_count,
       CASE WHEN count(d) > 5 THEN "high"
            WHEN count(d) > 1 THEN "medium"
            ELSE "low" END as coverage_level
```

### Migration system

```
graph/migrations/
├── V001__initial_schema.cypher        # Core node types and constraints
├── V002__rbac_access_policy.cypher    # Add access_policy to all node types
├── V003__temporal_edges.cypher        # Add valid_at/invalid_at to all edges
├── V004__outcome_nodes.cypher         # Add Outcome node type
└── V005__coverage_indices.cypher      # Performance indices for coverage queries
```

Schema version tracked in Neo4j: `MERGE (:SchemaVersion {version: N, applied_at: datetime()})`

---

## Layer 4: Intelligence

### Contradiction detector

```python
async def check_contradiction(new_event: DecisionEvent) -> ContradictionResult:
    # Query existing active decisions affecting same systems
    existing = await neo4j.query(CONTRADICTION_CHECK_QUERY,
                                  affects=new_event.affects,
                                  workspace_id=new_event.workspace_id)

    for existing_decision in existing:
        # LLM semantic comparison
        conflict_score = await llm.compare_decisions(
            new=new_event.content,
            existing=existing_decision.content
        )

        if conflict_score > 0.75:
            # Contradiction detected
            await publish_contradiction(new_event, existing_decision)
            await notify_decision_owners(existing_decision.made_by)
            await suspend_agent_actions(scope=new_event.affects)
            return ContradictionResult(
                detected=True,
                conflicting_decision_id=existing_decision.id,
                conflict_score=conflict_score,
                action="quarantine_new + notify_owners + suspend_agents"
            )

    return ContradictionResult(detected=False)
```

### Decay engine

```python
def compute_relevance(node: MemoryNode, now: datetime) -> float:
    """Thermodynamic decay — Field-Theoretic Memory (arXiv:2602.21220)"""
    age_days = (now - node.valid_at).days
    decay_rates = {
        "decision": 0.002,    # Slow decay — decisions are long-lived
        "exception": 0.005,   # Medium decay — exceptions get resolved
        "rationale": 0.003,   # Slow decay — rationale stays relevant
        "update": 0.010,      # Fast decay — status updates become stale
    }
    λ = decay_rates.get(node.event_type, 0.005)

    # Access boost — recent reads reset decay clock
    access_boost = node.access_count_last_30d * 0.01

    base_decay = node.importance_score * math.exp(-λ * age_days)
    return min(1.0, base_decay + access_boost)

# Lifecycle transitions (run nightly):
# relevance > 0.60 → ACTIVE    (injected into agents)
# relevance 0.30-0.60 → WARM   (queryable, not auto-injected)
# relevance 0.10-0.30 → COLD   (compressed to 3-sentence summary)
# relevance < 0.10 → ARCHIVED  (stored in cold storage, not graph)
# GDPR request → DELETED        (cascade delete with audit log)
```

### Coverage scorer

```python
async def domain_coverage(domain: str, workspace_id: str) -> CoverageReport:
    stats = await neo4j.query(COVERAGE_QUERY, domain=domain)
    connector_status = await check_connector_coverage(workspace_id)

    coverage_score = compute_coverage(
        decision_count=stats.decision_count,
        recency_score=stats.decisions_last_90d / max(stats.decision_count, 1),
        connector_coverage=len(connector_status.active) / len(CONNECTORS),
        team_coverage=stats.unique_authors / stats.expected_team_size
    )

    return CoverageReport(
        domain=domain,
        coverage_score=coverage_score,
        decision_count=stats.decision_count,
        last_activity_gap_days=stats.last_activity_gap,
        low_coverage_areas=identify_gaps(stats),
        missing_connectors=[c for c in CONNECTORS if c not in connector_status.active],
        recommendation=generate_recommendation(coverage_score, stats)
    )
```

---

## Layer 5: Context API

### MCP Server (TypeScript)

```typescript
// Tools exposed via MCP
const tools = [
  {
    name: "cortex_query",
    description: "Query organizational memory by intent and scope",
    inputSchema: {
      intent: { type: "string" },        // Natural language query
      scope: { type: "string" },         // System, team, or domain scope
      depth: { type: "string" },         // "decisions" | "full" | "causal_chain"
      caller_id: { type: "string" }      // DID of calling agent
    }
  },
  {
    name: "cortex_inject",
    description: "Auto-enrich a prompt with relevant organizational context",
    inputSchema: {
      prompt: { type: "string" },        // Agent's current prompt
      scope: { type: "string" },         // Scope hint for context retrieval
      caller_id: { type: "string" }
    }
  },
  {
    name: "cortex_remember",
    description: "Manually capture a decision or insight from agent interaction",
    inputSchema: {
      content: { type: "string" },
      event_type: { type: "string" },
      affects: { type: "array" },
      caller_id: { type: "string" }
    }
  },
  {
    name: "cortex_coverage",
    description: "Check memory completeness for a domain before acting",
    inputSchema: {
      domain: { type: "string" },
      caller_id: { type: "string" }
    }
  }
]
```

### REST API (FastAPI)

```
POST /api/v1/query                    # Query memory by intent
POST /api/v1/inject                   # Auto-enrich a prompt
POST /api/v1/remember                 # Manual capture
GET  /api/v1/coverage/{domain}        # Coverage score
GET  /api/v1/decisions/{id}           # Single decision detail
GET  /api/v1/systems/{id}/decisions   # All decisions for a system
GET  /api/v1/contradictions           # Active contradictions (human review)
POST /api/v1/contradictions/{id}/resolve  # Resolve contradiction
GET  /api/v1/graph/explore            # Graph explorer data
POST /api/v1/connectors/slack/webhook # Slack event receiver
POST /api/v1/connectors/github/webhook # GitHub event receiver
GET  /api/v1/health                   # Service health
```

---

## Storage Architecture

| Store | Technology | Data | Retention |
|---|---|---|---|
| Org config | PostgreSQL 15 | Workspaces, connectors, users, agent registry | Permanent |
| Time-series | TimescaleDB | Raw events, importance/trust scores, query logs | 5 years |
| Semantic | Qdrant | Decision embeddings for semantic search | 2 years |
| Structural | Neo4j 5 | Knowledge graph — all decisions, relationships | Permanent |
| Cache | Redis | Hot context, API response cache, session data | 24h TTL |
| ML artifacts | MLflow + S3 | Extractor versions, scorer experiments | Permanent |
| Cold storage | S3 | ARCHIVED memory nodes (compressed) | 7 years |
| Audit log | PostgreSQL | Every memory write, read, delete with caller identity | 7 years |

---

## Infrastructure

### Local (Docker Compose)

```yaml
Services:
  zookeeper, kafka
  neo4j (7474, 7687)
  postgres (5432)
  timescaledb (5433)
  qdrant (6333, 6334)
  redis (6379)
  mlflow (5000)
  prometheus (9090)
  grafana (3001)
  api (FastAPI — 8000)
  mcp-server (TypeScript — 8001)
  frontend (React — 3000)
```

### Production (Terraform + AWS ECS)

```
ECS Fargate: connector services, extraction engine, API, MCP server
RDS PostgreSQL + TimescaleDB: managed, Multi-AZ
Amazon MSK: managed Kafka
Neo4j AuraDB: managed (or EC2 self-hosted for cost)
ElastiCache Redis: managed
Qdrant Cloud: managed vector store
S3: cold storage, MLflow artifacts, static frontend
CloudFront: frontend CDN
ALB: API load balancer
Route53: DNS
Secrets Manager: all credentials
CloudWatch + Prometheus + Grafana: observability
```

---

## Gap Solutions — Build Phase Mapping

| Gap | Solution | Phase | Tech |
|---|---|---|---|
| Memory poisoning | Multi-source corroboration + CMVK | 4 | Bayesian trust, majority voting |
| Reasoning trap | Pre-execution schema validation | 5 | MCP middleware, schema registry |
| Graph completeness | Coverage scoring per domain | 4 (basic) | Graph density metrics |
| Access control | Memory-native RBAC + DID | 4 (must-have before real data) | Graph ACL, GDPR cascade |
| Memory decay | Thermodynamic decay engine | 5 | Field-theoretic model |
| Cross-org federation | Differential privacy patterns | v2 | OpenDP, SMPC |
| Outcome tracking | Decision outcome linker | 8 | Metric connectors, DoWhy |
| Implicit knowledge | Elicitation bot (Slack) | 9 | SBERT, targeted questions |

---

## Build Phases — Detailed

### Phase 1 — Kafka + Slack connector + Decision extractor (Week 1)
```
Deliverables:
  docker-compose.yml (all services)
  connectors/slack/producer.py (Slack → Kafka)
  extraction/decision_extractor.py (raw text → DecisionEvent)
  extraction/entity_resolver.py (text → canonical IDs)
  tests/test_slack_connector.py
  tests/test_decision_extractor.py (20 real message samples)

Done when:
  Real Slack messages flow through Kafka → extractor → DecisionEvent
  Extraction confidence > 0.7 on 15/20 test messages
  All tests pass
```

### Phase 2 — GitHub + Jira connectors + Neo4j schema (Week 1-2)
```
Deliverables:
  connectors/github/producer.py (commits, PRs, comments)
  connectors/jira/producer.py (issues, comments)
  graph/migrations/V001__initial_schema.cypher
  graph/migrations/V002__rbac_access_policy.cypher
  graph/migrations/V003__temporal_edges.cypher
  graph/writer.py (DecisionEvent → Neo4j)

Done when:
  GitHub PR descriptions extract decisions reliably
  Neo4j graph loads with real extracted decisions
  Temporal edges (valid_at/invalid_at) on all relationships
```

### Phase 3 — cortex.query() API + Redis cache + MCP server (Week 2)
```
Deliverables:
  api/main.py (FastAPI with /query, /inject, /health)
  api/memory.py (query layer over Neo4j + Qdrant + Redis)
  mcp/server.ts (MCP server with cortex_query, cortex_inject tools)
  mcp/package.json

Done when:
  `cortex.query(intent="why CockroachDB?", scope="payments-service")` returns correct context
  MCP server connects to Claude Desktop
  Redis cache serving repeated queries < 50ms
```

### Phase 4 — Importance scorer + Trust scorer + RBAC (Week 2-3)
```
Deliverables:
  scoring/importance_scorer.py
  scoring/trust_scorer.py (Bayesian model + CMVK)
  graph/rbac.py (graph-level access control)
  graph/migrations/V004__rbac_enforcement.cypher

Done when:
  No decision written to graph without importance + trust score
  No query executed without RBAC check
  Quarantined events never appear in agent context
  GDPR delete cascade tested and verified
```

### Phase 5 — Contradiction detector + Decay engine (Week 3)
```
Deliverables:
  intelligence/contradiction_detector.py
  intelligence/decay_engine.py (nightly job)
  api/contradictions.py (human review endpoints)

Done when:
  Conflicting decisions detected and flagged within 60 seconds of write
  Nightly decay job runs and correctly transitions node lifecycle states
  Human review queue accessible via API
```

### Phase 6 — React dashboard + Graph explorer (Week 3-4)
```
Deliverables:
  frontend/ (React + D3.js or React Flow)
  Dashboard: decision timeline, coverage heatmap, contradiction queue
  Graph explorer: interactive Neo4j visualization
  Animated GIF for README (demo scenario)

Done when:
  Dashboard loads in < 2 seconds
  Graph explorer navigable without instructions
  GIF captures the "new engineer asks why CockroachDB?" demo
```

### Phase 7 — Open-source launch (Week 5)
```
Deliverables:
  README.md final polish
  docker-compose.yml tested on clean machine (no residual config)
  3-minute Loom demo video
  Animated GIF in README
  Hacker News "Show HN" post
  LinkedIn post
  dev.to technical writeup

Done when:
  Fresh clone + docker-compose up + working demo in < 10 minutes
  HN post submitted
```

---

## ML Model Registry

| Model | Version | Framework | Status | Tracked |
|---|---|---|---|---|
| Decision extractor (GPT-4o) | v0.1 | OpenAI function calling | Design | MLflow |
| Decision extractor (local) | v0.1 | Ollama Gemma 4 E4B | Design | MLflow |
| Entity resolver (NER) | v0.1 | spaCy en_core_web_lg | Design | MLflow |
| Importance scorer | v0.1 | XGBoost (Phase 6+) / Rules (Phase 4) | Design | MLflow |
| Trust scorer | v0.1 | Bayesian (hmmlearn + custom) | Design | MLflow |
| Decision embeddings | v0.1 | sentence-transformers (all-MiniLM-L6-v2) | Design | MLflow |
| Coverage predictor | v0.1 | GraphSAGE (Phase 8+) | Design | MLflow |

---

## Version History

| Version | Date | Changes |
|---|---|---|
| v0.1 | 2026-05-11 | Initial architecture design — Session 0 |

---

## Deprecated Versions
*None yet.*
