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

---

## Session 1 — 2026-05-11
**Duration:** ~3h
**Phase:** Phase 1 — Infrastructure + Slack connector + Decision extractor

### Built

- Renamed `CORTEX_*.md` → canonical doc names (`README.md`, `CLAUDE.md`, etc.)
- `.gitignore` — Python, Node, Docker, Terraform, secrets
- `.env.example` — all 30+ environment variables documented
- `pyproject.toml` — full Python dependency set, ruff, mypy, pytest config
- `docker-compose.yml` — 10 services: Zookeeper, Kafka, Kafka-UI, Neo4j 5, PostgreSQL 15, TimescaleDB, Qdrant v1.9, Redis 7, MLflow, Prometheus, Grafana. API/MCP/Frontend behind Docker profiles.
- `infrastructure/docker/prometheus.yml` — Prometheus scrape config
- `infrastructure/docker/grafana/provisioning/` — Grafana datasource provisioning
- `shared/models.py` — RawEvent, DecisionEvent, Provenance Pydantic v2 schemas. Threshold constants.
- `connectors/slack/producer.py` — normalise_slack_event(), SlackKafkaProducer, SlackConnector
- `extraction/decision_extractor.py` — DecisionExtractor with GPT-4o/Ollama dual backend, content-hash cache
- `graph/migrations/V001–V005` — full Neo4j schema (constraints, RBAC, temporal edges, outcome nodes, coverage indices)
- `graph/migrate.py` — idempotent migration runner
- `tests/connectors/test_slack_producer.py` — 30 tests
- `tests/extraction/test_decision_extractor.py` — 34 tests (20 message samples)
- Git repository initialised: main → dev → feature/phase-1-infrastructure → merged to dev

### State at end
- 64 tests passing, 0 warnings, 0 failures
- All Phase 1 code deliverables complete
- No Docker services running (infrastructure not started yet — Slack app tokens needed)
- Neo4j schema not yet applied (requires running Neo4j container)

### Decisions made
- P-001 resolved: TypeScript for MCP server (already in architecture spec)
- Using timezone-aware datetimes throughout (Python 3.12+ deprecation avoided)

### Blockers
- Slack app not yet created (need OAuth tokens for live connector test)
- Ollama must be running locally for dev extraction tests (non-mocked path)

### Mistakes found
- `pyproject.toml` had incorrect build backend (`setuptools.backends.legacy:build` → `setuptools.build_meta`)
- `json` import left in `connectors/slack/producer.py` — removed

### Next session starts with
1. `scripts/connect_slack.py` — OAuth setup helper
2. `connectors/github/producer.py` — GitHub webhook connector (Phase 2)
3. `connectors/jira/producer.py` — Jira connector (Phase 2)
4. `graph/writer.py` — DecisionEvent → Neo4j write layer
5. `api/main.py` — FastAPI skeleton with /health endpoint (Phase 3 prep)

[OWNER NOTES]
- Cortex emerged as the second major portfolio project alongside Meridian
- Core insight: the market gap between memory systems (Mem0, Zep) and enterprise search (Glean, Dust) is exactly where Cortex sits — confirmed by Foundation Capital context graph thesis
- Key differentiator confirmed by research: importance scoring (noise filter) is the unsolved production problem — every system drowns in noise. Cortex solves it at ingestion.
- MCP adoption by OpenAI, Google, Microsoft (2025) makes MCP server the right distribution mechanism
- Demo scenario: new engineer asks Cursor "why CockroachDB?" → full decision history returned in 3 seconds
- This project targets AI Infrastructure Engineer roles — different hiring pool from Meridian (Data/MLOps)

---

## Session 2 — 2026-05-14
**Duration:** ~2h
**Phase:** Phases 3–6 (API, intelligence, semantic/episodic hooks, dashboard)

### Built
- `intelligence/contradiction_detector.py` — overlap + negation heuristics, Neo4j `Contradiction` nodes, Kafka `cortex.intelligence.contradictions`
- `intelligence/decay_engine.py` — batch importance decay by age (`python -m intelligence.decay_engine`)
- `graph/migrations/V006__contradiction_nodes.cypher` — contradiction constraints and index
- `api/contradictions.py` — `GET /contradictions/pending` human review queue
- `graph/query.py` — `fetch_decisions_by_ids` for hybrid retrieval
- `memory/episodic.py` — optional Timescale append for `RawEvent`
- `memory/semantic.py` — optional Qdrant upsert + search when `CORTEX_SEMANTIC_ENABLED=true`
- `api/memory.py` — merges semantic hits with full-text graph results
- `pipeline/extraction_worker.py` — episodic append, Qdrant upsert, post-write contradiction pass (toggle `CORTEX_CONTRADICTION_ENABLED`)
- `frontend/` — Vite + React dashboard (health + links), production Docker image with nginx
- Tests: `tests/intelligence/*`, contradictions API test, conftest disables contradiction Neo4j in unit tests by default

### State at end
- 207 pytest tests passing
- Phase 7 launch items (video, HN post) remain manual owner tasks

### Next session starts with
1. ~~Run `python -m graph.migrate` (apply V006)~~ — superseded: migrations through **V007**; use `make demo` or `python -m graph.migrate` after schema changes (see Session 4).
2. `docker compose --profile api up` and validate **webhook → worker → graph** on a dev workspace (Slack/GitHub tokens in `.env`).
3. Phase 7: screen recording + README GIF — follow [docs/DEMO_RECORDING.md](docs/DEMO_RECORDING.md).

---

## Session 3 — 2026-05-14
**Duration:** ~45m
**Phase:** Demo readiness (Phase 7 prep — automation, not video)

### Built
- `scripts/demo.sh` — Docker up (Kafka, Neo4j, Redis, Postgres), `graph.migrate` + `seed_demo` inside `api` image (`NEO4J_URI=bolt://neo4j:7687`), `api` + `pipeline-worker` + `frontend`, curl smoke on `POST /query`
- `scripts/seed_demo.py` — idempotent `DecisionEvent` pair (CockroachDB migration + Redis session cache) via `GraphWriter`; `scripts/__init__.py` for test imports
- `Makefile` — `demo`, `demo-dry-run` (`uv run`), `test` (`uv run pytest`)
- `api/Dockerfile` — `COPY scripts ./scripts` so migrate/seed run in-container without bind mounts
- `frontend/src/App.tsx` + `index.css` — **Query memory** form (`/query`); contradictions link uses workspace field
- `README.md` — **One-command demo** subsection (`make demo` / `bash scripts/demo.sh`)
- `tests/scripts/test_seed_demo.py` — stable UUID + decision field assertions (no Neo4j)

### State at end
- Demo automation landed; runtime fixes deferred to Session 4 (compose in-container URIs, migration runner, fulltext repair).

### Next session starts with
1. Superseded by **Session 4** (reliability + CI + recording checklist).

---

## Session 4 — 2026-05-14
**Duration:** ~1h
**Phase:** Demo reliability + CI + Phase 7 prep (documentation)

### Built
- `docker-compose.yml` — `api` / `pipeline-worker` **environment** overrides: `NEO4J_URI=bolt://neo4j:7687`, `REDIS_HOST=redis`, `KAFKA_BOOTSTRAP_SERVERS=kafka:29092` (`.env` defaults target host-local dev only)
- `neo4j` service — stable **`hostname: neo4j`** + **`extra_hosts`** so `InetAddress.getLocalHost()` resolves (fixes crash loop on some Docker setups); Neo4j 5 **server.memory.*** env keys
- `graph/query.py` — full-text bind param renamed to **`$search_text`** (Neo4j async `session.run` reserves `query`)
- `graph/migrate.py` — **`_strip_leading_comments`** so semicolon-split chunks with leading `//` still execute the first `CREATE`/`MERGE` (fixes skipped V005 fulltext)
- `graph/migrations` — **V007** fulltext repair; **V001–V006** `SchemaVersion` **MERGE (v {version}) SET** (stable identity); **V001** dropped Enterprise-only property-existence constraint for Neo4j Community
- `.github/workflows/ci.yml` — **pytest** + **`scripts/seed_demo.py --dry-run`** on Python 3.11
- `tests/graph/test_migrate_strip.py` — unit tests for migration chunk stripping
- `docs/DEMO_RECORDING.md` — Phase 7 recording / GIF checklist; README links to it
- `docs/CONNECTOR_VALIDATION.md` — webhook → Kafka validation steps (GitHub / Slack / Jira); README links to it

### State at end
- **213** pytest passes; CI workflow ready for GitHub Actions on `main` / `develop` / PRs

### Next session starts with
1. **Owner:** Record demo + GIF per [docs/DEMO_RECORDING.md](docs/DEMO_RECORDING.md); add link in README when hosted
2. **Live connector path:** Slack (or GitHub) webhook → Kafka → worker → graph on a real workspace (tokens in `.env`)
3. **Optional:** Slim `api` Docker image (extras in `pyproject.toml`) so CI/local `docker compose build` is not dominated by Torch/spaCy unless needed for that image

---

## Session 5 — 2026-05-14
**Duration:** ~20m
**Phase:** Phase 1 / demo UX (frontend dashboard)

### Built
- `frontend/src/index.css` — repaired broken `:root` / universal selector block after a bad `@import` move; **`@import` (DM Sans) is first**, then full CSS variables and `*, *::before, *::after { box-sizing }`
- `frontend/src/App.tsx` — **`apiBase`** resolves to trimmed `VITE_API_URL` without trailing slash, else **`http://localhost:8000`**, so `fetch()` and Tools links hit the API instead of the Vite origin when env is unset

### State at end
- `npm run build` (frontend) succeeds

### Next session starts with
1. Same as Session 4 “Next session” (owner demo recording, live connector validation)
2. Optional: smoke `npm run dev` + API with tabs (overview, search, inject, review, tools)

---

## Session 6 — 2026-05-18
**Duration:** ~1h
**Phase:** Gap closure vs external review — graph reads, Linear, SDK, tests

### Built
- `graph/query.py` — `find_decisions_by_system`, `trace_causal_chain`, `find_conflict_candidates` (+ RBAC)
- `api/schemas.py`, `api/deps.py` — shared models/deps (avoids circular imports)
- `api/decisions.py` — `GET /decisions/by-system/{id}`, `/{id}/chain`, `/{id}/conflicts`
- `api/remember.py` — `POST /remember` → `cortex.raw.manual.events`
- `sdk/client.py` — `CortexClient` (`query`, `inject`, `remember`, `decisions_by_system`, `causal_chain`)
- `connectors/linear/producer.py` + `POST /webhooks/linear`
- `pipeline/extraction_worker.py` — consumes `cortex.raw.linear.events` + `cortex.raw.manual.events`
- `mcp/server.js` — `cortex_remember` tool
- Tests: graph query, decisions API, remember, linear connector, SDK, pipeline failures, webhook security
- `shared/models.py` — `manual` source for API-submitted memory
- README / `.env.example` — API table, SDK snippet, correct MCP stdio config

### State at end
- **228** pytest passes (~80% coverage)

### Next session starts with
1. Owner demo recording ([docs/DEMO_RECORDING.md](docs/DEMO_RECORDING.md))
2. Live webhook validation with real Slack/GitHub/Linear tokens
3. Optional: graph explorer UI tab calling `/decisions/.../chain`

---

## Session — 2026-05-19 — Production refinement pass
**Duration:** ~2h
**Phase:** Phase 6 polish (dashboard) + Phase 0 hardening (backend)

### Built
**Backend correctness & quality**
- `graph/query.py`: `_CAUSAL_CHAIN` query rewritten — depth is now a clamped literal (D-017). Added `list_pending_contradictions` and `health()` on `GraphQueryService` so the contradiction route and `/health` reuse the shared async driver.
- `api/contradictions.py`: rewrote to `async def`, removed per-request `GraphDatabase.driver()`; now calls `MemoryService.pending_contradictions`.
- `api/main.py`: `_check_neo4j` / `_check_redis` reuse `MemoryService` instead of opening a new driver per `/health` poll.
- `api/memory.py`: added `pending_contradictions`, `neo4j_health`, `redis_health`.
- `pipeline/extraction_worker.py`: bounded LRU dedup cache (`_BoundedSeenCache`) replaces the unbounded `set`. Capacity tuned via `CORTEX_DEDUP_CACHE_SIZE`.
- Removed dead imports in `memory/semantic.py`, `intelligence/contradiction_detector.py`, `api/decisions.py`.

**Frontend correctness, perf, and UX**
- `frontend/package.json`: build now runs `tsc --noEmit && vite build`. `tsconfig.json` enables `noUnusedLocals` / `noUnusedParameters`.
- `App.tsx`: `ExploreView`, `AgentsView`, `ReviewView` are `React.lazy` + `<Suspense>` fallbacks (skeleton). Cuts initial bundle ~30%.
- New shared UI primitives: `components/ui/Skeleton.tsx`, `StateView.tsx`, `TypingIndicator.tsx`.
- `index.css`: bumped `--text-muted` contrast, added `--focus-ring` + global `:focus-visible`, skeleton shimmer, typing animation, `prefers-reduced-motion` overrides, mobile sidebar redone as horizontal scrollable tabs at ≤768 with 44px tap targets, breakpoint at ≥1440.
- `HomeView`, `AskView`, `AgentsView`, `ReviewView`, `LineageView`: skeleton + error/empty states via `<StateView />`. `ReviewView` auto-loads on mount.
- `AskView`: debounced character counter, `useMemo`/`useCallback` for result list, fixed person/system chip selector heuristic.
- `DecisionCard`: chevron rotates 180° with motion-token; wrapped in `React.memo` with a custom equality check.
- `AssistantPanel`: three-dot typing indicator with `aria-live`; message timestamp via tooltip; Send disabled when empty; thinking timer cleaned up on unmount and on rapid re-send.
- `MemoryGraph`: Space key activation + `aria-pressed` + `aria-label` per node.

**Tests added**
- `tests/graph/test_query.py`: causal-chain inline depth, depth clamp bounds, `trace_causal_chain` round-trip asserting the query no longer carries `$max_depth`, `list_pending_contradictions` RBAC filter.
- `tests/pipeline/test_extraction_worker.py`: LRU eviction + recency promotion.
- `tests/api/test_main.py`: rewrote `test_contradictions_pending` against the new async path + added a 503 failure case.

### State at end
- **235 pytest passing · 81.07% coverage.**
- `cd frontend && npm run build` — clean (`tsc --noEmit` → `vite build`, no warnings, 4-chunk split).
- No public API change. RBAC, signature verification, and `make demo` semantics preserved.

### Decisions made
- D-017 logged in `DECISIONS.md`.

### Next session starts with
- Owner review of the PR opened against `main` from `feature/production-refinement`.
- Optional: introduce Vitest + Testing Library for the frontend (deferred — out of scope per task constraints).

---

## Session — 2026-06-10 — Phase 1 Slack pipeline (handoff)
**Duration:** ~3h (gap closure passes + ops stabilization + Phase 1 start)
**Phase:** Phase 1 — Kafka + Slack connector + decision extractor

### Built
**Gap closure & ops (merged PRs #5–#7; PR #8 ops stabilization)**
- E2E Playwright, k6 load test, staging smoke, Prometheus `/metrics`, OTel + Jaeger profile
- mlflow port **5001**, Qdrant TCP healthcheck, CI k6 via `grafana/setup-k6-action@v1`

**Phase 1 Slack pipeline (branch `feature/phase-1-slack-pipeline`, uncommitted)**
- `docker-compose.yml` — `KAFKA_BOOTSTRAP_SERVERS` on **api** service (webhook can publish)
- `connectors/slack/producer.py` — skip Slack retries (`slack_retry_num > 0`); **flush after publish**
- `api/webhooks.py` — reads `X-Slack-Retry-Num`, passes to connector
- `scripts/inject_slack_message.py` — dev inject to `cortex.raw.slack.messages` (`--dry-run` supported)
- Tests: retry skip + flush assertions; `tests/integration/test_slack_pipeline_e2e.py`; inject script tests

### State at end
- Branch **`feature/phase-1-slack-pipeline`** with uncommitted changes (see git status)
- Slack unit + integration tests pass locally; full suite should be re-run before PR
- **Not yet validated:** live inject → pipeline-worker → Neo4j with Ollama/OpenAI running
- **Not yet done:** commit, push, open PR

### Next session starts with
1. `pytest tests/` on `feature/phase-1-slack-pipeline`
2. Stack up: `docker compose --profile api up -d`
3. Live path: `python scripts/inject_slack_message.py` → watch pipeline-worker → verify Decision in Neo4j
4. Commit, push, `gh pr create` for Phase 1 branch
5. Confirm PR #8 merged and staging-validation CI green on `main`

[OWNER NOTES]
- Pick up Phase 1 from this branch; no commit yet — owner decides message/PR scope.

---

## Session — 2026-06-10 (cont.) — Live Slack E2E + dev workflow
**Duration:** ~1h
**Phase:** Phase 1 — Kafka + Slack connector + decision extractor

### Built
- **Docker dev workflow:** `pipeline-worker` + `api` volume-mount `./:/app` with `PYTHONPATH=/app` — code changes need `make pipeline-restart` (~3s), not image rebuild (~8min)
- **Ollama extraction fix:** example-based JSON prompt + `response_format=json_object`; reject schema-echo responses
- **Compose env:** `OLLAMA_BASE_URL=host.docker.internal`, Timescale service DNS for worker
- **`scripts/verify_slack_pipeline.py`** + **`make verify-pipeline`** — live inject → Neo4j Decision count check
- **`scripts/run_pipeline_worker_local.sh`** + **`make pipeline-local`** — host-native worker for fastest iteration
- **Makefile:** `stack`, `pipeline-restart`, `pipeline-local`, `verify-pipeline`

### State at end
- **`make verify-pipeline` PASS** — 11 → 12 Decision nodes in ~26s (Ollama llama3.1:8b)
- **295** pytest passing (approx., re-run before merge)
- Branch **`feature/phase-1-live-e2e`** ready for PR

### Next session starts with
1. Merge live E2E PR; configure real Slack app webhook
2. Optional: slim pipeline-worker Docker image (worker-only deps)
3. Demo recording per `docs/DEMO_RECORDING.md`
