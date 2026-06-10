import { useCallback, useState } from "react";
import { useApp } from "../context/AppContext";
import { MemoryGraph } from "../components/memory/MemoryGraph";
import { TimelineView } from "../components/memory/TimelineView";
import { LineageView } from "../components/memory/LineageView";
import { DecisionCard } from "../components/memory/DecisionCard";
import { WorkspaceBar } from "../components/layout/WorkspaceBar";
import { PageHeader } from "../components/ui/PageHeader";
import { StateView } from "../components/ui/StateView";
import { resolveDecisionFocus } from "../lib/decision";

type ExploreTab = "graph" | "timeline" | "lineage";

export function ExploreView() {
  const {
    exploreDecisions,
    selectedDecisionId,
    setSelectedDecisionId,
    lastQuery,
    workspaceId,
    setView,
  } = useApp();
  const [tab, setTab] = useState<ExploreTab>("graph");

  const focusId = selectedDecisionId ?? exploreDecisions[0]?.event_id ?? null;
  const decisions = exploreDecisions.length > 0 ? exploreDecisions : lastQuery?.results ?? [];

  const handleCardSelect = useCallback(
    (id: string) => {
      setSelectedDecisionId(resolveDecisionFocus(id, decisions, focusId));
      if (id.startsWith("person:") || id.startsWith("system:")) {
        setTab("graph");
      }
    },
    [decisions, focusId, setSelectedDecisionId],
  );

  const handleTimelineSelect = useCallback(
    (decisionId: string) => {
      setSelectedDecisionId(decisionId);
      setTab("graph");
    },
    [setSelectedDecisionId],
  );

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
          Showing <strong>{decisions.length}</strong> result{decisions.length === 1 ? "" : "s"} for{" "}
          <q>{lastQuery.query}</q>
          {lastQuery.latency_ms ? <> · {lastQuery.latency_ms}ms</> : null}
        </p>
      ) : null}

      {decisions.length === 0 ? (
        <StateView
          icon="◎"
          title="No memories to map yet"
          action={
            <button type="button" className="btn btn--primary" onClick={() => setView("ask")}>
              Go to Ask →
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
              </button>
            ))}
          </div>

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
                  if (next) setSelectedDecisionId(next);
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
                onSelectDecision={setSelectedDecisionId}
              />
            ) : null}
            {tab === "lineage" && !focusId ? (
              <StateView icon="◇" title="Select a decision">
                Pick a decision below to trace supersession and trigger lineage.
              </StateView>
            ) : null}
          </section>

          <section className="panel">
            <h2 className="panel__title">Decisions in this view</h2>
            <div className="decision-list">
              {decisions.map((d) => (
                <DecisionCard
                  key={d.event_id}
                  decision={d}
                  selected={d.event_id === focusId}
                  onSelect={handleCardSelect}
                />
              ))}
            </div>
          </section>
        </>
      )}
    </article>
  );
}
