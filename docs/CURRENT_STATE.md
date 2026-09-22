# Cortex CURRENT_STATE — Post V2 Scaffold Land

**Date:** 2026-09-22  
**Baseline:** Cortex **V1 closed** (phases 0–7) — see [V1_RELEASE.md](V1_RELEASE.md)  
**Spec:** [CORTEX_V2.md](CORTEX_V2.md)  
**Tracking:** Epic [#78](https://github.com/askmy-stack/cortex/issues/78) (close when hot-path deepening + signature demo land)

> Phase 0 audit (2026-09-18) delivered the gap report. PRs **#82–#91** then landed V2 modules on `main`. This document reflects **code on main as of 2026-09-22**, not the pre-implementation audit.

---

## 1. Executive summary

Cortex V1 remains a working decision-capture → Kafka → extract → score → Neo4j → query/inject/MCP pipeline with RBAC, GDPR, contradictions, decay, and a React dashboard.

**V2 scaffold is on `main`:** Evidence Graph (flagged), Temporal Truth, Reliability Gate + MCP `cortex_evaluate` / `cortex_explain_memory`, CortexBench baseline, Memory Firewall helpers, Procedure models, Outcome ledger API, Abstention/gaps API.

**Not done yet:** full hot-path wiring (write pipeline / `/query` / MCP inject), procedure extractor + versioning, outcome→incident linker, coverage on query responses, signature BLOCK demo, and live demo API origin (#61). Treat V2 as **landed scaffold + APIs**, not a complete memory control plane.

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
| Quarantine audit | **Partial** | `memory/quarantine.py` | Write rejects; firewall helpers exist but not fully unified |
| Neo4j Decision graph | **Full** | `graph/writer.py`, `graph/query.py` | MERGE idempotent |
| RBAC (graph) | **Full** | `graph/rbac.py`, V002/V009 | Read-path filter |
| GDPR erase | **Full** | `graph/gdpr.py`, `api/gdpr.py` | + Qdrant/Timescale purge |
| Redis query cache | **Full** | `api/memory.py`, `memory/cache_epoch.py` | Epoch bump on GDPR + writes (V1 closeout / #33) |
| Semantic (Qdrant) | **Partial** | `memory/semantic.py` | Flag `CORTEX_SEMANTIC_ENABLED` |
| Episodic (Timescale) | **Partial** | `memory/episodic.py` | Optional append / GDPR purge |
| Contradiction detector | **Full** | `intelligence/contradiction_detector.py` | + API resolve |
| Decay engine | **Full** | `intelligence/decay_engine.py` | CLI + Compose `decay-worker` (V1 closeout / #36) |
| Claim / Evidence | **Scaffold** | `shared/v2_models.py`, `evidence/*`, V010, `api/evidence.py` | Behind `CORTEX_EVIDENCE_GRAPH` (default off); deepen write-path |
| Temporal state-at-time | **Scaffold** | `temporal/*`, `api/memory_state.py` | State-at-time API landed; deepen ranking vs query path |
| Reliability Gate | **Scaffold** | `reliability/*`, `api/reliability.py`, MCP `cortex_evaluate` | ACT\|VERIFY\|ASK\|ESCALATE\|BLOCK; wire into inject |
| MCP explain | **Scaffold** | MCP `cortex_explain_memory` | Explain path present; tie to signature demo |
| CortexBench | **Baseline** | `evals/*`, `docs/EVALS.md` | Baseline scenarios; expand suite + CI report |
| Memory Firewall | **Scaffold** | `firewall/*` | write/retrieval/secret helpers; not fully on hot path |
| Procedure memory | **Models** | `procedures/models.py` | Need extractor / versioning / env compatibility |
| Outcome ledger | **Scaffold** | `outcomes/ledger.py`, `api/outcomes.py` | Usefulness API; linker to metrics/incidents still #63 |
| Coverage / abstention | **Scaffold** | `gaps/*`, `api/gaps.py` | Not yet on `/query` + MCP inject (#62 depth) |
| MCP query/inject/remember | **Full** | `mcp/server.js` | V1 tools |
| Meetings connector | **Missing** | — | #64 |
| Dashboard | **Full** | `frontend/` | Ask/Explore/Review/Assist |
| Live demo URL | **Partial** | Vercel UI; API needs `CORTEX_API_ORIGIN` | #61 |

---

## 3. README / docs mismatches

Addressed in V1 closeout + this hygiene pass:

- Meetings / coverage / outcome linking not claimed as fully shipped
- V2 described as **scaffold on main**, with deepening called out
- `ARCHITECTURE.md` body may still describe longer-term designs — read as target where marked future

Still watch:

- `docs/PRODUCTION_READINESS.md` is a historical 2026-06-10 report (test counts outdated)
- Frontend `coverage_score?` type remains for forward UI; query path may not always populate it

---

## 4. Reuse points (unchanged)

| V2 need | Reuse |
|---|---|
| Claim adapter | `DecisionEvent` + `Provenance`; `evidence/adapters.py` |
| Evidence / authority | `evidence/authority.py` + trust priors (#42) |
| Temporal | `temporal/validity.py`, `temporal/state.py` |
| Reliability Gate | `reliability/gate.py` ← API + MCP |
| Firewall | Extend `write_pipeline.py` + query guards with `firewall/*` |
| Outcomes | `outcomes/ledger.py` + V004 indices; linker still open |
| Coverage / gaps | `gaps/detector.py`; wire into `/query` |
| Eval | `evals/`; expand scenarios |
| Migrations | `graph/migrations/V010+` via `graph/migrate.py` |

**Feature flags:** `CORTEX_EVIDENCE_GRAPH` (and gate flags as added) — default off until hot-path stable.

---

## 5. Merged V2 PRs (reference)

| PR | Scope |
|---|---|
| #82 | Claim/Evidence foundations + Neo4j V010 (#68) |
| #83 | Evidence Graph + explain API (#69) |
| #84 | Temporal Truth + `/memory/state` (#70) |
| #85 | Reliability Gate + MCP `cortex_evaluate` (#71) |
| #86 | MCP `cortex_explain_memory` (#77) |
| #87 | CortexBench baseline (#72) |
| #88 | Memory Firewall (#73) |
| #89 | Procedural memory models (#74) |
| #90 | Outcome ledger + usefulness (#75) |
| #91 | Abstention + KnowledgeGap (#76) |

---

## 6. Remaining work (priority)

1. **Deepen V2 hot path** — Evidence/Firewall/Gate/coverage on write + `/query` + MCP inject  
2. **Signature demo** — CORTEX_V2.md §19 “restart payments?” → BLOCK + explain  
3. **#61** — live demo `CORTEX_API_ORIGIN`  
4. **#65** — thread-aware extraction  
5. **#63 / #64** — outcome linker; meeting connector  
6. Expand CortexBench + keep README claims honest  

---

## 7. Definition of ready — Phase 0 (complete)

- [x] V1 closed (`docs/V1_RELEASE.md`)
- [x] `docs/CORTEX_V2.md` checked in
- [x] Phase 0 `CURRENT_STATE` audit merged (#80)
- [x] V2 P0–P2 scaffold PRs #82–#91 merged
- [ ] Hot-path deepening + signature demo (next)
- [ ] Epic #78 closed when control-plane DoD is demonstrable
