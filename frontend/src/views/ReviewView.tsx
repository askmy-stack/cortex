import { useCallback, useEffect, useState } from "react";
import { fetchContradictions, resolveContradiction } from "../api/client";
import { isUnauthorizedMessage } from "../lib/auth";
import { shortId } from "../lib/format";
import { useApp } from "../context/AppContext";
import { useToast } from "../components/ui/Toast";
import { WorkspaceBar } from "../components/layout/WorkspaceBar";
import { PageHeader } from "../components/ui/PageHeader";
import { Skeleton } from "../components/ui/Skeleton";
import { StateView } from "../components/ui/StateView";
import type { ContradictionItem } from "../types";

export function ReviewView() {
  const { workspaceId, setView, setSelectedDecisionId, setExploreDecisions } = useApp();
  const { showToast } = useToast();
  const [items, setItems] = useState<ContradictionItem[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const ws = workspaceId.trim() || "local-dev";

  const openInMap = useCallback(
    (decisionId: string) => {
      setExploreDecisions([]);
      setSelectedDecisionId(decisionId);
      setView("explore");
    },
    [setExploreDecisions, setSelectedDecisionId, setView],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await fetchContradictions(ws));
    } catch (e) {
      setItems(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [ws]);

  const resolve = useCallback(
    async (id: string, resolution: "acknowledged" | "dismissed") => {
      setResolvingId(id);
      try {
        await resolveContradiction(id, ws, resolution);
        setItems((prev) => prev?.filter((c) => c.id !== id) ?? null);
        showToast(
          resolution === "acknowledged"
            ? "Conflict acknowledged — agents may proceed with caution."
            : "Conflict dismissed from the review queue.",
        );
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
      } finally {
        setResolvingId(null);
      }
    },
    [ws, showToast],
  );

  useEffect(() => {
    setItems(null);
  }, [workspaceId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <article className="view view--review fade-in">
      <PageHeader
        eyebrow="Governance"
        title="Review conflicts"
        subtitle="When new decisions conflict with existing memory, resolve them here before agents act on stale knowledge."
      />

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
            {isUnauthorizedMessage(error) ? (
              <p className="muted">
                Open <strong>Connection</strong> above and save your API key.
              </p>
            ) : null}
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
                <header className="contradiction-card__head">
                  <span className="badge">Score {c.score.toFixed(2)}</span>
                  <span className="badge badge--muted">{c.status}</span>
                </header>
                <p className="contradiction-card__body">{c.explanation}</p>
                <footer className="contradiction-card__foot">
                  <div className="contradiction-card__ids">
                    {c.new_decision_id ? (
                      <span title={c.new_decision_id}>New: {shortId(c.new_decision_id)}</span>
                    ) : null}
                    {c.prior_decision_id ? (
                      <span title={c.prior_decision_id}>Prior: {shortId(c.prior_decision_id)}</span>
                    ) : null}
                  </div>
                  <div className="contradiction-card__actions">
                    {c.new_decision_id ? (
                      <button
                        type="button"
                        className="btn btn--ghost btn--sm"
                        onClick={() => openInMap(c.new_decision_id!)}
                      >
                        View new
                      </button>
                    ) : null}
                    {c.prior_decision_id ? (
                      <button
                        type="button"
                        className="btn btn--ghost btn--sm"
                        onClick={() => openInMap(c.prior_decision_id!)}
                      >
                        View prior
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="btn btn--primary btn--sm"
                      disabled={resolvingId === c.id}
                      onClick={() => void resolve(c.id, "acknowledged")}
                    >
                      {resolvingId === c.id ? "Saving…" : "Acknowledge"}
                    </button>
                    <button
                      type="button"
                      className="btn btn--secondary btn--sm"
                      disabled={resolvingId === c.id}
                      onClick={() => void resolve(c.id, "dismissed")}
                    >
                      Dismiss
                    </button>
                  </div>
                </footer>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </article>
  );
}
