import { useCallback, useEffect, useState } from "react";
import { fetchContradictions } from "../api/client";
import { useApp } from "../context/AppContext";
import { WorkspaceBar } from "../components/layout/WorkspaceBar";
import { Skeleton } from "../components/ui/Skeleton";
import { StateView } from "../components/ui/StateView";
import type { ContradictionItem } from "../types";

export function ReviewView() {
  const { workspaceId } = useApp();
  const [items, setItems] = useState<ContradictionItem[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await fetchContradictions(workspaceId.trim() || "local-dev"));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  // Auto-load when the user opens the view and whenever the workspace changes.
  useEffect(() => {
    void load();
  }, [load]);

  return (
    <article className="view view--review fade-in">
      <header className="view__header">
        <h1>Review contradictions</h1>
        <p className="view__subtitle">
          When new decisions conflict with existing memory, they appear here for human
          review before agents rely on them.
        </p>
      </header>

      <WorkspaceBar />

      <section className="panel">
        <header className="panel__head">
          <h2 className="panel__title">Pending queue</h2>
          <button
            type="button"
            className="btn btn--secondary"
            onClick={() => void load()}
            disabled={loading}
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </header>

        {loading && !items ? (
          <>
            <Skeleton variant="row" />
            <Skeleton variant="row" />
            <Skeleton variant="row" />
          </>
        ) : null}

        {error ? (
          <StateView
            tone="error"
            icon="!"
            title="Couldn't load contradictions"
            action={
              <button type="button" className="btn btn--secondary" onClick={() => void load()}>
                Try again
              </button>
            }
          >
            {error}
          </StateView>
        ) : null}

        {items && items.length === 0 && !loading && !error ? (
          <StateView icon="✓" title="Your memory graph is consistent">
            No pending contradictions for this workspace.
          </StateView>
        ) : null}

        {items && items.length > 0 ? (
          <ul className="contradiction-list">
            {items.map((c) => (
              <li key={c.id} className="contradiction-card fade-in">
                <header style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                  <span className="badge">Score {c.score.toFixed(2)}</span>
                  <span className="badge badge--muted">{c.status}</span>
                </header>
                <p style={{ marginTop: "0.5rem" }}>{c.explanation}</p>
                <footer className="contradiction-card__ids">
                  {c.new_decision_id ? <span>New: {c.new_decision_id}</span> : null}
                  {c.prior_decision_id ? <span>Prior: {c.prior_decision_id}</span> : null}
                </footer>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </article>
  );
}
