# Cortex — Production Refinement Audit

> Audit produced before `feature/production-refinement`. Items marked `[x]` were fixed
> in this branch; `[ ]` items were deliberately deferred (see _Deferred_ section).
> Baseline before refinement: 228 backend tests passing, frontend build clean (no TS check).

## Bugs / runtime / type / lint

- [x] **A-01** `graph/query.py::_CAUSAL_CHAIN` uses `[:SUPERSEDES*1..$max_depth]`. Neo4j 5 does **not** allow parameterised variable-length depth; the query would raise at runtime. Inline a validated integer instead.
- [x] **A-02** `api/contradictions.py` creates a new `neo4j.GraphDatabase` driver on every request and is `def` (not `async`), so it blocks the event loop. Move to async driver via `MemoryService`.
- [x] **A-03** `api/main.py::_check_neo4j` / `_check_redis` create a brand-new driver / Redis client on every `/health` poll (called per pod by Docker healthcheck every 30s). Reuse the shared async driver and Redis client from `MemoryService`.
- [x] **A-04** `pipeline/extraction_worker.py::self._processed` is an unbounded `set[str]` — memory leak under sustained load. Switch to an `OrderedDict`-backed LRU.
- [x] **A-05** `memory/semantic.py::upsert_decision_vector` imports `FieldCondition, Filter, MatchValue` that the function never uses. Dead imports.
- [x] **A-06** `intelligence/contradiction_detector.py` imports unused `Any` from `typing`. Lint noise.
- [x] **A-07** `frontend/package.json::scripts.build` runs only `vite build`; **no `tsc` typecheck**, so TS errors silently ship. Add `tsc -b --noEmit` to the build pipeline.

## Missing logic / placeholders / dead code

- [x] **B-01** `ReviewView` requires a manual button-click to load pending contradictions; should auto-fetch when the user opens the view.
- [x] **B-02** `HomeView` renders nothing while `loading` (returns `null` from `health`) — no skeleton, no progress hint.
- [x] **B-03** `AskView` empty-state / error-state UI is missing: no skeleton list while fetching, no friendly empty hint when zero results.
- [x] **B-04** `AgentsView` has no skeleton during inject; user sees a blank panel during inference.
- [x] **B-05** `AssistantPanel` "sending" indicator is a single italic line — needs a typing-style affordance and `aria-live` for screen readers.

## Architecture / DX

- [x] **C-01** `health()` should consult the live `MemoryService` connection state, not open a new driver. Reduces tail latency and shared mutable state.
- [x] **C-02** `D-017` added to `DECISIONS.md` documenting the integer-inlined variable-depth Cypher and TS strictness bump.
- [x] **C-03** `tsconfig.json` did not enforce `noUnusedLocals` / `noUnusedParameters`; turning them on caught two genuinely unused params.
- [ ] **C-04** Pipeline worker still re-opens an asyncio loop per event via `memory.episodic.append_raw_event` (synchronous wrapper). Deferred — requires upgrade to async TimescaleDB driver. Worker is single-process so cost is bounded.

## UI / UX gaps

- [x] **D-01** Typography rhythm: hero used `clamp(2rem, 5vw, 2.75rem)` with `line-height: 1.1` — tightened the scale, added explicit `letter-spacing`, and harmonised metric/value contrast.
- [x] **D-02** No global `:focus-visible` ring; interactive elements relied on browser default outlines (often invisible against dark surfaces). Added a teal-accent focus ring tokenised via `--focus-ring`.
- [x] **D-03** `--text-muted` (`#94a3b8`) on `--surface-glass` was ~3.9:1 contrast — below WCAG AA. Bumped to `#a8b3c2` and tuned glass panels.
- [x] **D-04** No loading skeletons; every fetch view used italic placeholder text. Added a reusable `<Skeleton />` primitive with `prefers-reduced-motion` support.
- [x] **D-05** Sidebar on mobile collapsed labels but kept full-height — wasted ~30% of mobile viewport. Re-laid out as horizontal scrollable tabs at ≤768px with proper tap targets (44px min).
- [x] **D-06** `DecisionCard` chevron didn't rotate on expand — broke the affordance. Added a 180ms transform.
- [x] **D-07** `MemoryGraph` lacked keyboard activation for nodes; added `role="button"`, `tabIndex={0}` activation on Enter/Space, and high-contrast focus styles.
- [x] **D-08** `AssistantPanel` typing indicator promoted to an animated three-dot affordance with `aria-live="polite"`.
- [x] **D-09** No `prefers-reduced-motion: reduce` overrides — all keyframes now respect that media query.
- [x] **D-10** Responsive breakpoints at 360 / 768 / 1100 / 1440 added; tested via CSS only (sticky-top header collapses to a single row at ≤768).

## Performance

- [x] **E-01** Heavy views (`ExploreView`, `AgentsView`, `ReviewView`) loaded eagerly. Wrapped in `React.lazy` + `<Suspense>` with a skeleton fallback.
- [x] **E-02** `AskView` posted a new query on every keystroke during Enter-style submit; debounced the suggestion-derived query updates with a 200ms timer.
- [x] **E-03** `DecisionCard` had no `React.memo`; lists of 20+ cards re-rendered on unrelated context updates.
- [x] **E-04** `MemoryGraph` recomputed full layout on every render — memoised by results identity.

## Code quality

- [x] **F-01** Removed dead imports across `memory/semantic.py`, `intelligence/contradiction_detector.py`, `api/decisions.py` (`Field` unused after dataclass move).
- [x] **F-02** `api/contradictions.py` switched to the shared async memory service and dropped its bespoke per-request driver factory.
- [x] **F-03** Frontend `client.ts` error path now surfaces the upstream status code in the thrown `Error` for easier debugging.
- [x] **F-04** Centralised the "loading / empty / error" tri-state UI into a `<StateView />` helper to remove copy-paste across views.

## Deferred (and why)

- **C-04** Async TimescaleDB driver — requires bumping `psycopg` and the schema migration runner; out of scope for a UX-focused pass.
- **G-01** Frontend test framework (Vitest + Testing Library) — non-trivial scaffold; CLAUDE.md baseline is "tests in `/tests/`" (Python). Recommended as a follow-up PR.
- **G-02** Storybook / visual regression for the dashboard — large dependency footprint, explicitly out of scope per task constraints (no heavy new deps).

---

_Tests after refinement: see SESSIONS.md entry for this branch._
