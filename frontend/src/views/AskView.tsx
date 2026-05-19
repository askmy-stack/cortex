import { useState } from "react";
import { queryMemory } from "../api/client";
import { useApp } from "../context/AppContext";
import { summarizeQueryResults } from "../lib/assistant";
import { DecisionCard } from "../components/memory/DecisionCard";
import { WorkspaceBar } from "../components/layout/WorkspaceBar";

const EXAMPLES = [
  "Why CockroachDB for payments?",
  "Redis session cache checkout",
  "What affects payments-service?",
];

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

  async function search() {
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
  }

  return (
    <article className="view view--ask fade-in">
      <header className="view__header">
        <h1>Ask your organization</h1>
        <p className="view__subtitle">
          Natural language search over captured decisions — who decided, what systems are affected, and why.
        </p>
      </header>

      <WorkspaceBar />

      <section className="ask-form panel">
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
        />
        <p className="field-hint">
          <kbd>Ctrl</kbd>+<kbd>Enter</kbd> to search · {query.trim().length} characters
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
          <label className="inline-label">
            Max results
            <input
              type="number"
              min={1}
              max={20}
              className="input input--narrow"
              value={limit}
              onChange={(e) => setLimit(Math.min(20, Math.max(1, Number(e.target.value) || 8)))}
            />
          </label>
          <button type="button" className="btn btn--primary" onClick={() => void search()} disabled={loading}>
            {loading ? "Searching memory…" : "Search memory"}
          </button>
        </footer>
      </section>

      {error ? <p className="alert alert--error">{error}</p> : null}

      {lastQuery ? (
        <section className="results panel fade-in">
          <header className="panel__head">
            <h2>
              {lastQuery.total} result{lastQuery.total === 1 ? "" : "s"} · {lastQuery.latency_ms}ms
            </h2>
            <button type="button" className="btn btn--ghost" onClick={() => setView("explore")}>
              Open memory map →
            </button>
          </header>
          {lastQuery.results.length === 0 ? (
            <p className="empty">
              No memories matched. Run <code>make demo</code> to seed example decisions for <code>local-dev</code>.
            </p>
          ) : (
            <div className="decision-list">
              {lastQuery.results.map((d, i) => (
                <DecisionCard
                  key={d.event_id}
                  decision={d}
                  defaultOpen={i === 0}
                  onSelect={(id) => {
                    setSelectedDecisionId(id.startsWith("person:") || id.startsWith("system:") ? lastQuery.results[0]?.event_id ?? id : id);
                    setView("explore");
                  }}
                />
              ))}
            </div>
          )}
        </section>
      ) : null}
    </article>
  );
}
