import { useCallback, useEffect, useState } from "react";
import { useApp } from "../context/AppContext";
import { fetchContradictions } from "../api/client";
import { MemoryGraph } from "../components/memory/MemoryGraph";
import { TimelineView } from "../components/memory/TimelineView";
import { LineageView } from "../components/memory/LineageView";
import { DecisionCard } from "../components/memory/DecisionCard";
import { DecisionDetailPanel } from "../components/memory/DecisionDetailPanel";
import { WorkspaceBar } from "../components/layout/WorkspaceBar";
import { PageHeader } from "../components/ui/PageHeader";
import { StateView } from "../components/ui/StateView";
import { IconGraph } from "../components/ui/icons";
import { resolveDecisionFocus } from "../lib/decision";
import { parseHash } from "../lib/routing";

type ExploreTab = "graph" | "timeline" | "lineage";

export function ExploreView() {
  const {
    exploreDecisions,
    selectedDecisionId,
    setSelectedDecisionId,
    lastQuery,
    workspaceId,
    setView,
    detailDecisionId,
    setDetailDecisionId,
  } = useApp();
  const [tab, setTab] = useState<ExploreTab>("graph");
  const [conflictCount, setConflictCount] = useState(0);

  const focusId = selectedDecisionId ?? exploreDecisions[0]?.event_id ?? null;
  const decisions = exploreDecisions.length > 0 ? exploreDecisions : lastQuery?.results ?? [];
  const focusOnly = decisions.length === 0 && Boolean(selectedDecisionId);

  useEffect(() => {
    const route = parseHash();
    if (route.decisionId) {
      setSelectedDecisionId(route.decisionId);
      setDetailDecisionId(route.decisionId);
    }
  }, [setSelectedDecisionId, setDetailDecisionId]);

  useEffect(() => {
    if (focusOnly) setTab("lineage");
  }, [focusOnly, selectedDecisionId]);

  useEffect(() => {
    const ws = workspaceId.trim() || "local-dev";
    void fetchContradictions(ws)
      .then((items) => setConflictCount(items.length))
      .catch(() => setConflictCount(0));
  }, [workspaceId]);

  const handleCardSelect = useCallback(
    (id: string) => {
      const next = resolveDecisionFocus(id, decisions, focusId);
      if (next) {
        setSelectedDecisionId(next);
        setDetailDecisionId(next);
      }
      if (id.startsWith("person:") || id.startsWith("system:")) {
        setTab("graph");
      }
    },
    [decisions, focusId, setSelectedDecisionId, setDetailDecisionId],
  );

  const handleTimelineSelect = useCallback(
    (decisionId: string) => {
      setSelectedDecisionId(decisionId);
      setDetailDecisionId(decisionId);
      setTab("graph");
    },
    [setSelectedDecisionId, setDetailDecisionId],
  );

  const detailDecision =
    decisions.find((d) => d.event_id === detailDecisionId) ??
    (focusId ? decisions.find((d) => d.event_id === focusId) : null) ??
    null;

  return (
    <article className="view view--explore fade-in">
      <PageHeader
        eyebrow="Connections"
        title="Memory map"
        subtitle="See how decisions, people, and systems connect — timeline and lineage included."
      />

      <WorkspaceBar />

      {lastQuery && decisions.length > 0 ? (
        <p className="explore-context muted" role="status">
          Showing <strong>{decisions.length}</strong> decision{decisions.length === 1 ? "" : "s"}
          {conflictCount > 0 ? (
            <>
              {" "}
              · <strong>{conflictCount}</strong> open conflict{conflictCount === 1 ? "" : "s"}
            </>
          ) : null}{" "}
          for <q>{lastQuery.query}</q>
          {lastQuery.latency_ms ? <> · {lastQuery.latency_ms}ms</> : null}
        </p>
      ) : null}

      {decisions.length === 0 && !selectedDecisionId ? (
        <StateView
          icon={<IconGraph size={28} />}
          title="No memories to map yet"
          action={
            <button type="button" className="btn btn--primary" onClick={() => setView("ask")}>
              Go to Search →
            </button>
          }
        >
          Search organizational memory first — results appear here as an interactive graph,
          timeline, and lineage trace.
        </StateView>
      ) : (
        <>
          <div className="subtabs" role="tablist" aria-label="Visualization mode">
            {(["graph", "timeline", "lineage"] as const).map((t) => (
              <button
                key={t}
                type="button"
                role="tab"
                id={`subtab-${t}`}
                aria-selected={tab === t}
                aria-controls={`subpanel-${t}`}
                className={`subtab ${tab === t ? "subtab--active" : ""}`}
                onClick={() => setTab(t)}
              >
                {t === "graph" ? "Relationships" : t === "timeline" ? "Timeline" : "Lineage"}
                {t === "graph" && decisions.length > 0 ? (
                  <span className="subtab__badge">{decisions.length}</span>
                ) : null}
                {t === "timeline" && conflictCount > 0 ? (
                  <span className="subtab__badge subtab__badge--warn">{conflictCount}</span>
                ) : null}
              </button>
            ))}
          </div>

          <div className="explore-layout">
            <section
              className="panel explore-viz"
              role="tabpanel"
              id={`subpanel-${tab}`}
              aria-labelledby={`subtab-${tab}`}
            >
              {tab === "graph" ? (
                <MemoryGraph
                  decisions={decisions}
                  focusId={focusId}
                  onFocus={(id) => {
                    const next = resolveDecisionFocus(id, decisions, focusId);
                    if (next) {
                      setSelectedDecisionId(next);
                      setDetailDecisionId(next);
                    }
                  }}
                />
              ) : null}
              {tab === "timeline" ? (
                <TimelineView decisions={decisions} onSelect={handleTimelineSelect} />
              ) : null}
              {tab === "lineage" && focusId ? (
                <LineageView
                  decisionId={focusId}
                  workspaceId={workspaceId}
                  onSelectDecision={(id) => {
                    setSelectedDecisionId(id);
                    setDetailDecisionId(id);
                  }}
                />
              ) : null}
              {tab === "lineage" && !focusId ? (
                <StateView title="Select a decision">
                  Pick a decision below to trace supersession and trigger lineage.
                </StateView>
              ) : null}
            </section>

            <DecisionDetailPanel
              decision={detailDecision}
              onClose={() => setDetailDecisionId(null)}
              onExplore={(id) => setSelectedDecisionId(id)}
            />
          </div>

          {decisions.length > 0 ? (
            <section className="panel">
              <h2 className="panel__title">Decisions in this view</h2>
              <div className="decision-list">
                {decisions.map((d) => (
                  <DecisionCard
                    key={d.event_id}
                    decision={d}
                    selected={d.event_id === focusId}
                    onSelect={handleCardSelect}
                    onDetail={setDetailDecisionId}
                  />
                ))}
              </div>
            </section>
          ) : focusOnly && focusId ? (
            <p className="explore-context muted" role="status">
              Tracing lineage for decision <code>{focusId.slice(0, 8)}…</code> — run{" "}
              <strong>Search</strong> to populate the relationship graph.
            </p>
          ) : null}
        </>
      )}
    </article>
  );
}
