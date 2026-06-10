import { useCallback, useEffect, useState } from "react";
import { fetchContradictions, fetchHealth, queryMemory } from "../api/client";
import type { DecisionResult, Health } from "../types";
import { useApp } from "../context/AppContext";
import { buildDashboardMetrics, trustHeadline } from "../lib/insights";
import { scorePercent } from "../lib/format";
import { PageHeader } from "../components/ui/PageHeader";
import { MetricCard } from "../components/ui/MetricCard";
import { DecisionTeaser } from "../components/dashboard/DecisionTeaser";
import { MemoryGraph } from "../components/memory/MemoryGraph";
import { Skeleton } from "../components/ui/Skeleton";
import { StateView } from "../components/ui/StateView";

export function HomeView() {
  const {
    setView,
    setExploreDecisions,
    setSelectedDecisionId,
    setLastQuery,
    workspaceId,
    setAssistantOpen,
  } = useApp();
  const [decisions, setDecisions] = useState<DecisionResult[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const ws = workspaceId.trim() || "local-dev";
    try {
      const [queryRes, contradictions, healthRes] = await Promise.all([
        queryMemory({ query: "organizational decisions architecture payments", workspace_id: ws, limit: 12 }),
        fetchContradictions(ws).catch(() => []),
        fetchHealth().catch(() => null),
      ]);
      setDecisions(queryRes.results);
      setLastQuery(queryRes);
      setExploreDecisions(queryRes.results);
      if (queryRes.results[0]) setSelectedDecisionId(queryRes.results[0].event_id);
      setHealth(healthRes);
      setMetrics(buildDashboardMetrics(queryRes.results, contradictions));
    } catch (e) {
      setDecisions([]);
      setHealth(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [workspaceId, setLastQuery, setExploreDecisions, setSelectedDecisionId]);

  const [metrics, setMetrics] = useState(() =>
    buildDashboardMetrics([], []),
  );

  useEffect(() => {
    void load();
  }, [load]);

  function openDecision(id: string) {
    setSelectedDecisionId(id);
    setView("explore");
  }

  return (
    <article className="view view--home fade-in">
      <PageHeader
        eyebrow="Organizational intelligence"
        title="See what your team decided — and why it matters"
        subtitle="A living memory of decisions across Slack, GitHub, Jira, and more. Understand impact, people, and systems in seconds."
        actions={
          <>
            {health ? (
              <span className="status-pill" title="System status">
                <span
                  className={`status-pill__dot ${health.status === "ok" ? "" : "status-pill__dot--bad"}`}
                  aria-hidden
                />
                {health.status === "ok" ? "Memory online" : "Needs attention"}
              </span>
            ) : null}
            <button type="button" className="btn btn--primary" onClick={() => setView("ask")}>
              Ask a question
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => setAssistantOpen(true)}>
              Ask Assist
            </button>
          </>
        }
      />

      {error ? (
        <StateView tone="error" icon="!" title="Can't load organizational memory" action={
          <button type="button" className="btn btn--secondary" onClick={() => void load()}>
            Retry
          </button>
        }>
          {error}
        </StateView>
      ) : null}

      {loading ? (
        <div className="metrics-row" aria-hidden>
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} variant="card" />
          ))}
        </div>
      ) : (
        <section className="metrics-row" aria-label="Executive summary">
          <MetricCard
            icon="◈"
            label="Decisions in view"
            value={String(metrics.decisionCount)}
            hint="Captured organizational memory"
            tone="accent"
          />
          <MetricCard
            icon="◎"
            label="Memory confidence"
            value={trustHeadline(metrics.avgTrust)}
            hint={metrics.decisionCount ? `${scorePercent(metrics.avgTrust)}% avg trust` : "Search to populate"}
            tone="ok"
          />
          <MetricCard
            icon="⚡"
            label="Avg impact"
            value={metrics.decisionCount ? `${scorePercent(metrics.avgImpact)}%` : "—"}
            hint="Importance across decisions"
          />
          <MetricCard
            icon="⚖"
            label="Open conflicts"
            value={String(metrics.pendingConflicts)}
            hint={metrics.pendingConflicts ? "Needs review" : "Graph is consistent"}
            tone={metrics.pendingConflicts ? "warn" : "ok"}
          />
        </section>
      )}

      <div className="dashboard-grid">
        <section className="dashboard-panel" aria-labelledby="recent-decisions">
          <h2 id="recent-decisions" className="dashboard-panel__title">
            Recent decisions
          </h2>
          {loading ? (
            <>
              <Skeleton variant="row" />
              <Skeleton variant="row" />
            </>
          ) : metrics.recentDecisions.length === 0 ? (
            <StateView
              icon="◇"
              title="No decisions yet"
              action={
                <button type="button" className="btn btn--primary" onClick={() => setView("ask")}>
                  Search memory
                </button>
              }
            >
              Run <code>make demo</code> to seed example memories, or capture a decision from the AI agents view.
            </StateView>
          ) : (
            <div className="decision-feed">
              {metrics.recentDecisions.map((d) => (
                <DecisionTeaser key={d.event_id} decision={d} onSelect={openDecision} />
              ))}
            </div>
          )}
          {metrics.recentDecisions.length > 0 ? (
            <footer style={{ marginTop: "var(--space-4)" }}>
              <button type="button" className="btn btn--ghost" onClick={() => setView("explore")}>
                Open full memory map →
              </button>
            </footer>
          ) : null}
        </section>

        <aside className="dashboard-panel" aria-labelledby="insights-panel">
          <h2 id="insights-panel" className="dashboard-panel__title">
            Memory insights
          </h2>

          {metrics.trendingSystems.length > 0 ? (
            <>
              <h3 className="field-label">Trending systems</h3>
              <ul className="trending-list">
                {metrics.trendingSystems.map((t) => (
                  <li key={t.name}>
                    <span>{t.name}</span>
                    <span className="trending-list__count">{t.count} decisions</span>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="muted">Systems will appear as decisions are captured.</p>
          )}

          {metrics.activePeople.length > 0 ? (
            <>
              <h3 className="field-label" style={{ marginTop: "var(--space-4)" }}>
                Active decision makers
              </h3>
              <div className="people-chips">
                {metrics.activePeople.map((p) => (
                  <span key={p} className="people-chip">
                    {p.split("@")[0]}
                  </span>
                ))}
              </div>
            </>
          ) : null}

          {decisions.length > 0 ? (
            <div className="dashboard-graph-preview">
              <h3 className="field-label" style={{ marginTop: "var(--space-4)" }}>
                Knowledge graph preview
              </h3>
              <MemoryGraph
                decisions={decisions.slice(0, 6)}
                focusId={decisions[0]?.event_id}
                onFocus={(id) => {
                  if (id.startsWith("person:") || id.startsWith("system:")) {
                    const primary = decisions[0]?.event_id;
                    if (primary) openDecision(primary);
                  } else {
                    openDecision(id);
                  }
                }}
              />
            </div>
          ) : null}
        </aside>
      </div>
    </article>
  );
}
