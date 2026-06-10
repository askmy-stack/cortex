import { useState } from "react";
import { useApp } from "../context/AppContext";
import { MemoryGraph } from "../components/memory/MemoryGraph";
import { TimelineView } from "../components/memory/TimelineView";
import { LineageView } from "../components/memory/LineageView";
import { DecisionCard } from "../components/memory/DecisionCard";
import { StateView } from "../components/ui/StateView";

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

  return (
    <article className="view view--explore fade-in">
      <header className="view__header">
        <h1>Memory map</h1>
        <p className="view__subtitle">
          See how decisions, people, and systems connect — plus timeline and lineage views.
        </p>
      </header>

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
                // Graph focus drives card highlight + lineage, both of which need a
                // real decision id. Person/system nodes are prefixed, so ignore them.
                onFocus={(id) => {
                  if (!id.startsWith("person:") && !id.startsWith("system:")) {
                    setSelectedDecisionId(id);
                  }
                }}
              />
            ) : null}
            {tab === "timeline" ? <TimelineView decisions={decisions} /> : null}
            {tab === "lineage" && focusId ? (
              <LineageView decisionId={focusId} workspaceId={workspaceId} />
            ) : null}
            {tab === "lineage" && !focusId ? (
              <p className="muted">Select a decision below to trace its lineage.</p>
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
                  onSelect={() => setSelectedDecisionId(d.event_id)}
                />
              ))}
            </div>
          </section>
        </>
      )}
    </article>
  );
}
