# MISTAKES.md — Errors, Learnings, and Understanding

> Read before writing code. Every entry was caught before or during build.
> Agent: check this file when stuck — the answer may already be here.
> Owner: add entries whenever something breaks, an assumption fails, or a decision reverses.

---

## Entry Format

```
### [M-NNN] — [DATE] — [Short title]
**Phase:** [Which build phase]
**Type:** Architecture / Data / ML / Infra / Product / Process / Security
**What happened:** [Specific description]
**Why it happened:** [Root cause]
**Impact:** [What it cost or would have cost]
**Fix / Learning:** [What to do instead]
**Prevents:** [Future mistake this entry stops]
```

---

## MISTAKES LOG

### [M-001] — 2026-05-11 — Treating Cortex as a search tool during architecture
**Phase:** Phase 0
**Type:** Product
**What happened:** Early architecture drafts framed Cortex's primary interface as a search API — users query for context. This is the same mistake every existing tool makes (Glean, Notion AI, Dust). Pull-based retrieval only.
**Why it happened:** Defaulting to familiar patterns (RAG, search) rather than reasoning from first principles.
**Impact:** Would have produced a weaker product that competes directly with Glean on Glean's home turf.
**Fix / Learning:** The architectural insight that separates Cortex: **active injection, not passive retrieval**. Cortex enriches agent prompts before agents ask. The MCP server is the primary interface, not the search endpoint.
**Prevents:** Building a search bar instead of memory infrastructure.

---

### [M-002] — 2026-05-11 — Storing text instead of decisions
**Phase:** Phase 0
**Type:** Architecture
**What happened:** First memory model stored raw messages and relied on RAG to find relevant context. Same approach as Mem0, Zep, Cognee.
**Why it happened:** Easier to implement — no extraction step needed.
**Impact:** RAG retrieves text similarity, not organizational meaning. "CockroachDB" retrieves every message mentioning the word — not the decision that matters.
**Fix / Learning:** The atomic memory unit is the DecisionEvent — a structured extraction of what was decided, why, by whom, affecting what. Raw text is input to the extractor, not output to the graph.
**Prevents:** Building yet another vector search over Slack messages.

---

### [M-003] — 2026-05-11 — Skipping importance scoring until "later"
**Phase:** Phase 0
**Type:** Architecture
**What happened:** Initial build plan had importance scoring in Phase 5. Core memory pipeline was going to run without it for the first 4 phases.
**Why it happened:** Optimizing for speed to demo rather than for graph quality.
**Impact:** A graph without importance scoring fills with noise in days. Every Slack message, every commit comment, every Jira status update would be stored. Retrieval would degrade immediately. The demo would show a useless system.
**Fix / Learning:** Importance scoring is Phase 4 — before the graph gets any real data. The graph must be clean from the first write. Noisy graph = dead product.
**Prevents:** Building a fast demo that breaks immediately in production.

---

### [M-004] — 2026-05-11 — No RBAC in MVP scope
**Phase:** Phase 0
**Type:** Security
**What happened:** RBAC (graph-level access control) was initially scoped as a post-launch feature. MVP was going to use basic API auth only.
**Why it happened:** RBAC is complex and slows initial build. Tempting to defer.
**Impact:** Any demo with real org data (decisions mentioning salaries, M&A, personnel) would expose sensitive data to any agent querying the API. A security incident at demo stage = immediate credibility destruction.
**Fix / Learning:** RBAC must be built before any real data enters the system. The access policy structure is part of the Neo4j schema — retrofitting it later requires migrating every existing node. Build it first.
**Prevents:** Sensitive data exposure in demo or early testing.

---

### [M-005] — 2026-05-11 — Assuming Slack message → decision is simple extraction
**Phase:** Phase 0
**Type:** ML / Data
**What happened:** Architecture assumed GPT-4o would reliably extract decisions from Slack messages. Simple prompt, structured output.
**Why it happened:** LLMs are good at this in demos. Real Slack channels are noisy, informal, context-dependent.
**Impact:** Real Slack data contains: jokes, partial discussions, references to prior context, sarcasm, code snippets, reactions. A naive extractor will hallucinate decisions from non-decisions and miss real decisions that span multiple threads.
**Fix / Learning:**
- Decision extraction is a classification problem first (is this a decision?) then extraction (what are the fields?)
- Multi-message context window: extract from thread, not single message
- Confidence threshold: only write to graph if extraction confidence > 0.7
- Human review queue: low-confidence extractions (0.4-0.7) go to a review UI, not directly to graph
- Test with 50 real Slack messages from a real workspace before claiming extraction works
**Prevents:** Graph pollution from hallucinated decisions.

---

### [M-006] — 2026-05-11 — No demo video in initial scope
**Phase:** Phase 0
**Type:** Product / Process
**What happened:** Launch plan included HN post and LinkedIn post. No demo video or animated GIF for README.
**Why it happened:** Focused on technical build, not distribution.
**Impact:** Open-source repos without demo GIFs get significantly fewer stars. HN "Show HN" posts without live demos get fewer upvotes. The technical work becomes invisible.
**Fix / Learning:** Week 4 deliverable must include:
- 3-minute Loom demo video (new engineer asking Cursor "why CockroachDB?" → Cortex returns full decision history)
- Animated GIF for README (same scenario, compressed to 30 seconds)
- Plan this in advance — not bolted on after the fact
**Prevents:** Shipping a working product that nobody engages with.

---

### [M-007] — 2026-05-11 — Memory poisoning not designed for from the start
**Phase:** Phase 0
**Type:** Security
**What happened:** Trust scoring and memory poisoning defense were initially Phase 6+ features. The first 5 phases would store anything extracted without verification.
**Why it happened:** Security is always tempting to defer until "after the demo."
**Impact:** MINJA research shows 95%+ injection success rates. A poisoned memory (one malicious Slack message crafted to inject false architectural decisions) corrupts every agent using Cortex permanently. The demo could be compromised.
**Fix / Learning:** Trust scorer is Phase 4 — same phase as importance scorer. Both must exist before any real external data enters the graph. Bayesian trust model with provenance chain on every write. Low-trust events quarantined, never injected into agents.
**Prevents:** Persistent memory corruption from poisoned inputs.

---

## LEARNINGS (positive — things that worked well)

### [L-001] — 2026-05-11 — MCP as distribution mechanism, not feature
**What:** MCP was initially designed as one of several API options. Reframed as the primary distribution mechanism — the reason agents get memory without any integration work.
**Why it matters:** OpenAI, Google, and Microsoft all adopted MCP in 2025. It's becoming the standard agent-tool protocol. A Cortex MCP server means every Claude, Cursor, and custom agent with MCP support gets organizational memory by adding one line to their config. This is the adoption flywheel.
**Apply to:** Every design decision about the API surface — always ask "how does this feel from the MCP client perspective?"

---

### [L-002] — 2026-05-11 — Research papers as architecture validation, not inspiration
**What:** Used MAGMA, Zep, A-MEM, and Field-Theoretic Memory papers not as inspiration but as validation. Each architectural choice has a paper backing it with benchmark numbers.
**Why it matters:** When a recruiter or hiring manager asks "why did you design it this way?" the answer isn't "it seemed right." It's "MAGMA (2026) showed four-graph separation outperforms monolithic memory stores on LoCoMo by X%. We use the same separation."
**Apply to:** Every non-obvious design decision — find the paper that validates it.

---

### [L-003] — 2026-05-11 — The gap between memory systems and enterprise search is the product
**What:** Spent time mapping what Mem0, Zep, Glean, Dust, Cognee each do. The gap between them — cross-tool capture + decision extraction + temporal causal graph + active injection + importance scoring + org scope — is exactly what Cortex is. The gap isn't abstract. It's confirmed by market analysis and research.
**Why it matters:** Knowing precisely where the product lives relative to everything else makes every build decision easier. When someone asks "why not just use Glean?" the answer is specific, not vague.
**Apply to:** Every feature decision — does this make Cortex more clearly itself, or does it make Cortex more like an existing tool?

---

### [L-004] — 2026-05-11 — Importance scoring is the product's core value, not a feature
**What:** Initially treated importance scoring as a quality-of-life feature. Reframed as the core value proposition — the reason Cortex doesn't become noise like every other tool.
**Why it matters:** Every memory system paper from 2024-2026 identifies noise accumulation as the primary production failure. Cortex solves this at ingestion. That's the moat.
**Apply to:** Importance scorer should be the most tested, most tuned component in the system.

---

### [L-005] — 2026-05-11 — Four-week MVP discipline
**What:** Full architecture includes trust scorer, RBAC, contradiction detector, decay engine, outcome tracker, behavioral mining, federated memory. If all of that is Phase 1, nothing ships.
**Why it matters:** Portfolio project needs a demo in 4 weeks. Open-source project needs stars in 5 weeks. The job search timeline is real. MVP is: Slack + GitHub connectors + Neo4j graph + MCP server + basic dashboard + demo video. Everything else is post-launch.
**Apply to:** Every temptation to add "just one more feature" before shipping — check the 4-week constraint first.
