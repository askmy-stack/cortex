# Cortex V1 — Release Closeout

**Status:** Closed  
**Date:** 2026-09-18  
**Scope:** Build phases 0–7 (organizational memory MVP)

## What V1 is

Cortex V1 is a working **organizational memory** system:

- Capture decisions from Slack, GitHub, Jira, Linear → Kafka
- Extract structured `DecisionEvent`s → importance / trust / CMVK write gates
- Persist to Neo4j with graph-level RBAC; optional Qdrant semantic merge
- Query / inject / remember via FastAPI + MCP
- Contradiction detection, decay batch job (+ Compose `decay-worker`), GDPR erase
- React dashboard + seeded demo + live Vercel URL

## What V1 is not (deferred to V2)

| Claim often seen in older docs | Reality |
|---|---|
| Coverage scoring on `/query` | Schema/UI stub only — V2 / #62 / #76 |
| Outcome linking to metrics | Schema only (V004) — V2 / #63 / #75 |
| Meeting / CI/CD connectors | Not implemented — V2 / #64 |
| Memory Reliability Gate | V2 P0 / #71 |
| Evidence Graph | V2 P0 / #68–#69 |
| Procedural memory / firewall | V2 P1 / #73–#74 |

## V1 closeout fixes (this release)

- Redis query-cache epoch bumped on **pipeline graph writes** (not only GDPR) — #33
- `decay-worker` scheduled service under Compose `api` profile — #36
- README / ARCHITECTURE honesty pass (no overclaimed coverage/outcomes/meetings)
- Formal V1 closed; Phase 8–10 folded into Cortex V2 roadmap (#78)

## Ops remaining (not blockers for V1 close)

- Set `CORTEX_API_ORIGIN` on Vercel after Render/Plan A API deploy (#61)
- Public webhook URLs for live connectors (optional for demos; inject scripts work)

## Next

1. **V2 Phase 0 only:** `docs/CORTEX_V2.md` + `docs/CURRENT_STATE.md` (#67)  
2. Do **not** start V2 Phase 1 (Claim/Evidence migrations) until Phase 0 merges.
