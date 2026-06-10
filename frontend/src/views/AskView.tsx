import { useCallback, useEffect, useMemo, useState } from "react";
import { queryMemory } from "../api/client";
import { useApp } from "../context/AppContext";
import { summarizeQueryResults } from "../lib/assistant";
import { isUnauthorizedMessage } from "../lib/auth";
import { DecisionCard } from "../components/memory/DecisionCard";
import { WorkspaceBar } from "../components/layout/WorkspaceBar";
import { PageHeader } from "../components/ui/PageHeader";
import { StoryStrip } from "../components/ui/StoryStrip";
import { Skeleton } from "../components/ui/Skeleton";
import { StateView } from "../components/ui/StateView";

const EXAMPLES = [
  "Why CockroachDB for payments?",
  "Redis session cache checkout",
  "What affects payments-service?",
];

const ENTITY_PREFIXES = ["person:", "system:"];

export function AskView() {
  const {
    workspaceId,
    pushMessage,
    setLastQuery,
    setExploreDecisions,
    setSelectedDecisionId,
    setView,
    lastQuery,
  } = useApp();
  const [query, setQuery] = useState("Why CockroachDB for payments?");
  const [limit, setLimit] = useState(8);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debounce the character counter so rapid typing doesn't churn React.
  const [debouncedLength, setDebouncedLength] = useState(query.trim().length);
  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedLength(query.trim().length), 200);
    return () => window.clearTimeout(handle);
  }, [query]);

  const search = useCallback(async () => {
    const q = query.trim();
    if (q.length < 3) {
      setError("Please enter at least 3 characters.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await queryMemory({
        query: q,
        workspace_id: workspaceId.trim() || "local-dev",
        limit,
      });
      setLastQuery(result);
      setExploreDecisions(result.results);
      if (result.results[0]) setSelectedDecisionId(result.results[0].event_id);
      pushMessage("user", q);
      pushMessage("assistant", summarizeQueryResults(result));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [
    query,
    limit,
    workspaceId,
    pushMessage,
    setLastQuery,
    setExploreDecisions,
    setSelectedDecisionId,
  ]);

  const handleCardSelect = useCallback(
    (id: string) => {
      // Chip clicks pass `person:<id>` / `system:<id>`; keep the original decision
      // focused so the memory map highlights the right node.
      if (ENTITY_PREFIXES.some((p) => id.startsWith(p))) {
        const firstId = lastQuery?.results[0]?.event_id;
        if (firstId) setSelectedDecisionId(firstId);
      } else {
        setSelectedDecisionId(id);
      }
      setView("explore");
    },
    [lastQuery, setSelectedDecisionId, setView],
  );

  const results = lastQuery?.results ?? [];
  const resultList = useMemo(
    () =>
      results.map((d, i) => (
        <DecisionCard
          key={d.event_id}
          decision={d}
          defaultOpen={i === 0}
          onSelect={handleCardSelect}
        />
      )),
    [results, handleCardSelect],
  );

  const topResult = results[0];

  return (
    <article className="view view--ask fade-in">
      <PageHeader
        eyebrow="Search memory"
        title="Ask your organization anything"
        subtitle="Natural language search over captured decisions — who decided, what systems are affected, and why."
      />

      <WorkspaceBar />

      <section className="ask-form panel ask-hero">
        <label className="field-label" htmlFor="ask-input">
          Your question
        </label>
        <textarea
          id="ask-input"
          className="textarea textarea--lg"
          rows={3}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. Why did we choose CockroachDB for payments?"
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              void search();
            }
          }}
          aria-describedby="ask-hint"
        />
        <p className="field-hint" id="ask-hint">
          <kbd>Ctrl</kbd>+<kbd>Enter</kbd> to search · {debouncedLength} characters
        </p>

        <p className="field-label">Try an example</p>
        <div className="chip-row">
          {EXAMPLES.map((ex) => (
            <button key={ex} type="button" className="chip" onClick={() => setQuery(ex)}>
              {ex}
            </button>
          ))}
        </div>

        <footer className="ask-form__actions">
          <details className="ask-advanced">
            <summary className="muted">Advanced options</summary>
            <label className="inline-label">
              Max results
              <input
                type="number"
                min={1}
                max={20}
                className="input input--narrow"
                value={limit}
                onChange={(e) =>
                  setLimit(Math.min(20, Math.max(1, Number(e.target.value) || 8)))
                }
              />
            </label>
          </details>
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => void search()}
            disabled={loading}
          >
            {loading ? "Searching memory…" : "Search memory"}
          </button>
        </footer>
      </section>

      {error ? (
        <StateView tone="error" icon="!" title="Search failed">
          {error}
          {isUnauthorizedMessage(error) ? (
            <p className="muted">Open <strong>Connection</strong> above and save your API key.</p>
          ) : null}
        </StateView>
      ) : null}

      {loading && !lastQuery ? (
        <section className="panel" aria-live="polite">
          <header className="panel__head">
            <h2 style={{ width: "100%" }}>
              <Skeleton variant="title" />
            </h2>
          </header>
          <Skeleton variant="card" />
          <Skeleton variant="card" />
        </section>
      ) : null}

      {lastQuery && topResult ? (
        <StoryStrip
          decision={topResult}
          onExplore={() => {
            setSelectedDecisionId(topResult.event_id);
            setView("explore");
          }}
        />
      ) : null}

      {lastQuery ? (
        <section className="results panel fade-in" aria-live="polite">
          <header className="panel__head">
            <h2>
              {lastQuery.total} result{lastQuery.total === 1 ? "" : "s"} ·{" "}
              {lastQuery.latency_ms}ms
            </h2>
            <button type="button" className="btn btn--ghost" onClick={() => setView("explore")}>
              Open memory map →
            </button>
          </header>
          {results.length === 0 ? (
            <StateView icon="◇" title="No memories matched">
              Try a broader query, or run <code>make demo</code> to seed example decisions
              for <code>local-dev</code>.
            </StateView>
          ) : (
            <div className="decision-list">{resultList}</div>
          )}
        </section>
      ) : null}
    </article>
  );
}
