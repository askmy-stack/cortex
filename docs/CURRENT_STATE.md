# Cortex CURRENT_STATE — V2 Phase 0 Audit

**Date:** 2026-09-18  
**Baseline:** Cortex **V1 closed** (phases 0–7) — see [V1_RELEASE.md](V1_RELEASE.md)  
**Spec:** [CORTEX_V2.md](CORTEX_V2.md)  
**Tracking:** GitHub [#67](https://github.com/askmy-stack/cortex/issues/67) · epic [#78](https://github.com/askmy-stack/cortex/issues/78)

> Phase 0 deliverable only. No Claim/Evidence migrations or Reliability Gate code in this document’s accompanying PR.

---

## 1. Executive summary

Cortex V1 is a working decision-capture → Kafka → extract → score → Neo4j → query/inject/MCP pipeline with RBAC, GDPR, contradictions, decay, and a React dashboard. It is **not** yet a memory control plane: there is no Evidence Graph, no Reliability Gate (`ACT|VERIFY|ASK|ESCALATE|BLOCK`), no temporal state-at-time API, no procedure memory, and no CortexBench.

V2 should **extend** existing modules (`scoring/`, `intelligence/`, `graph/`, `memory/`, `api/`, `mcp/`) rather than replace Kafka, Neo4j, or the dashboard.

---

## 2. Capability matrix

| Capability | Status | Evidence / path | Notes |
|---|---|---|---|
| Kafka ingestion | **Full** | `connectors/*`, `pipeline/extraction_worker.py` | Slack, GitHub, Jira, Linear, manual |
| Decision extraction | **Full** | `extraction/decision_extractor.py` | GPT-4o / Ollama; single-message (thread hardening → #65) |
| Importance scoring | **Full** | `scoring/importance.py` | Rule-based at write |
| Trust scoring | **Full** | `scoring/trust_scorer.py` | Bayesian; hardcoded source priors (#42) |
| CMVK | **Full** | `scoring/cmvk.py`, `cmvk_llm.py` | Heuristic / openai / ollama |
| Write pipeline gate | **Full** | `scoring/write_pipeline.py` | importance → CMVK → trust |
| Quarantine audit | **Partial** | `memory/quarantine.py` | Write rejects only; no retrieval firewall |
| Neo4j Decision graph | **Full** | `graph/writer.py`, `graph/query.py` | MERGE idempotent |
| RBAC (graph) | **Full** | `graph/rbac.py`, V002/V009 | Read-path filter |
| GDPR erase | **Full** | `graph/gdpr.py`, `api/gdpr.py` | + Qdrant/Timescale purge |
| Redis query cache | **Full** | `api/memory.py`, `memory/cache_epoch.py` | Epoch bump on GDPR + **writes** (V1 closeout) |
| Semantic (Qdrant) | **Partial** | `memory/semantic.py` | Flag `CORTEX_SEMANTIC_ENABLED` |
| Episodic (Timescale) | **Partial** | `memory/episodic.py` | Optional append / GDPR purge |
| Contradiction detector | **Full** | `intelligence/contradiction_detector.py` | + API resolve |
| Decay engine | **Full** | `intelligence/decay_engine.py` | CLI + Compose `decay-worker` (V1 closeout) |
| Outcome nodes | **Schema only** | `V004__outcome_nodes.cypher` | No linker — #63 / #75 |
| Coverage indices | **Schema only** | `V005__coverage_indices.cypher` | No scorer; UI optional field — #62 / #76 |
| Claim / Evidence | **Missing** | — | V2 P0 #68–#69 |
| Temporal state-at-time API | **Missing** | Partial `valid_at`/`invalid_at` on edges | V2 P0 #70 |
| Reliability Gate | **Missing** | — | V2 P0 #71 |
| Procedure memory | **Missing** | — | V2 P1 #74 |
| Memory Firewall | **Partial** | quarantine + CMVK | Needs PII/injection guards — #73 |
| Abstention / gaps | **Missing** | — | V2 P2 #76 |
| CortexBench | **Missing** | — | V2 P0 #72 |
| MCP query/inject/remember | **Full** | `mcp/server.js` — `cortex_query`, `cortex_remember`, `cortex_inject` | |
| MCP evaluate/explain/outcome | **Missing** | — | #71, #77, #75 |
| Meetings connector | **Missing** | README historically overclaimed | #64 |
| Dashboard | **Full** | `frontend/` | Ask/Explore/Review/Assist |
| Live demo URL | **Partial** | Vercel UI; API needs `CORTEX_API_ORIGIN` | #61 |

---

## 3. README / docs mismatches (post V1 closeout)

Addressed in V1 closeout (`docs/V1_RELEASE.md`):

- Meetings / coverage / outcome tracking no longer claimed as shipped
- ARCHITECTURE.md status updated from “Design only”

Still stale / watch:

- `ARCHITECTURE.md` body still describes Phase 8+ designs as future — OK if read as target architecture
- `docs/PRODUCTION_READINESS.md` is a historical 2026-06-10 report (test counts outdated)
- Frontend `coverage_score?` type remains for forward UI; API does not return it

---

## 4. Reuse points for V2

| V2 need | Reuse |
|---|---|
| Claim adapter | `DecisionEvent` + `Provenance` in `shared/models.py`; `GraphWriter.write()` |
| Evidence / authority | Extend `scoring/trust_scorer.py` priors (#42); write path in `write_pipeline.py` |
| Temporal | Existing `valid_at` / `invalid_at` / `SUPERSEDES` in `graph/writer.py`, `graph/query.py` causal chain |
| Reliability Gate | New `reliability/` package; call from `api/` + MCP; consume RBAC from `graph/rbac.py` |
| Firewall | Extend `write_pipeline.py` + `memory/quarantine.py`; retrieval guard beside `MemoryService.query_decisions` |
| Outcomes | V004 Outcome indices; new `intelligence/` or `outcomes/` module |
| Coverage / gaps | V005 indices; new scorer; wire into `/query` response schema |
| Eval | New `evals/`; seed via `scripts/demo_catalog.py` patterns |
| Migrations | Continue `graph/migrations/V010+` via `graph/migrate.py` |

**Feature flags (recommended):** `CORTEX_EVIDENCE_GRAPH`, `CORTEX_RELIABILITY_GATE` — default off until P0 stable.

---

## 5. Duplicate / inconsistent logic

| Area | Note |
|---|---|
| Trust vs importance | Separate scores — keep; V2 adds usefulness / action_confidence (do not overload trust) |
| Quarantine vs CMVK reject | Both reject writes; firewall should unify reason codes |
| Decision as only memory unit | V2 Claim sits beside Decision via adapter — avoid forking two write paths long-term |
| Aggregate Kafka topics | GitHub/Jira use `cortex.raw.*.events` (D-013) — keep for V2 connectors |

---

## 6. Recommended module placement

Prefer **new packages** only where V2 domains are first-class (per CORTEX_V2 §21):

```text
reliability/     # gate, risk, policies, reason_codes, confidence
evidence/        # models helpers, authority, explain (or under graph/)
temporal/        # validity helpers used by graph/query
procedures/      # P1
outcomes/        # P1 — or intelligence/outcome_linker.py
firewall/        # P1 — or scoring/firewall_*.py
gaps/            # P2
evals/           # CortexBench
```

Do **not** create empty folders until the implementing PR needs them.

---

## 7. Suggested V2 implementation order (locked)

1. **Phase 0 (this doc)** — #67  
2. **P0:** #68 data foundations → #69 Evidence → #70 Temporal → #71 Gate + #77 explain → #72 CortexBench  
3. **P1:** #73 Firewall → #74 Procedures → #75 Outcomes  
4. **P2:** #76 Abstention / gaps (+ #62 coverage)

**Do not start #68 until this Phase 0 audit is merged.**

---

## 8. Definition of ready for V2 Phase 1

- [x] V1 closed (`docs/V1_RELEASE.md`)
- [x] `docs/CORTEX_V2.md` checked in
- [x] This `CURRENT_STATE.md` merged
- [ ] Issue #67 closed by maintainer
- [ ] D-018 / ACTIVE instruction Phase 0 marked DONE
