import { useState } from "react";
import { fetchContradictions } from "../api/client";
import { useApp } from "../context/AppContext";
import { WorkspaceBar } from "../components/layout/WorkspaceBar";
import type { ContradictionItem } from "../types";

export function ReviewView() {
  const { workspaceId } = useApp();
  const [items, setItems] = useState<ContradictionItem[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setItems(await fetchContradictions(workspaceId.trim() || "local-dev"));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <article className="view view--review fade-in">
      <header className="view__header">
        <h1>Review contradictions</h1>
        <p className="view__subtitle">
          When new decisions conflict with existing memory, they appear here for human review before agents rely on them.
        </p>
      </header>

      <WorkspaceBar />

      <section className="panel">
        <button type="button" className="btn btn--secondary" onClick={() => void load()} disabled={loading}>
          {loading ? "Loading…" : "Load pending items"}
        </button>
      </section>

      {error ? <p className="alert alert--error">{error}</p> : null}

      {items && items.length === 0 ? (
        <section className="empty panel">
          <p>No pending contradictions — your memory graph is consistent for this workspace.</p>
        </section>
      ) : null}

      {items && items.length > 0 ? (
        <ul className="contradiction-list">
          {items.map((c) => (
            <li key={c.id} className="contradiction-card fade-in">
              <header>
                <span className="badge">Score {c.score.toFixed(2)}</span>
                <span className="badge badge--muted">{c.status}</span>
              </header>
              <p>{c.explanation}</p>
              <footer className="contradiction-card__ids">
                {c.new_decision_id ? <span>New: {c.new_decision_id}</span> : null}
                {c.prior_decision_id ? <span>Prior: {c.prior_decision_id}</span> : null}
              </footer>
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}
