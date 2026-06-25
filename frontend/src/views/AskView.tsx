import { useCallback, useEffect, useMemo, useState } from "react";
import { queryMemory } from "../api/client";
import { useApp } from "../context/AppContext";
import { summarizeQueryResults } from "../lib/assistant";
import { isUnauthorizedMessage } from "../lib/auth";
import { scorePercent } from "../lib/format";
import { DecisionCard } from "../components/memory/DecisionCard";
import { DecisionDetailPanel } from "../components/memory/DecisionDetailPanel";
import { WorkspaceBar } from "../components/layout/WorkspaceBar";
import { PageHeader } from "../components/ui/PageHeader";
import { StoryStrip } from "../components/ui/StoryStrip";
import { Skeleton } from "../components/ui/Skeleton";
import { StateView } from "../components/ui/StateView";
import { IconEmpty } from "../components/ui/icons";

const EXAMPLES = [
  "Why CockroachDB for payments?",
  "Redis session cache checkout",
  "What affects payments-service?",
];

const ENTITY_PREFIXES = ["person:", "system:"];
const SOURCE_FILTERS = ["all", "slack", "github", "jira", "linear"] as const;
type SourceFilter = (typeof SOURCE_FILTERS)[number];

function sortByRank(a: { importance_score: number; trust_score: number }, b: typeof a): number {
  const rankA = a.importance_score * a.trust_score;
  const rankB = b.importance_score * b.trust_score;
  return rankB - rankA;
}

export function AskView() {
  const {
    workspaceId,
    pushMessage,
    setLastQuery,
    setExploreDecisions,
    setSelectedDecisionId,
    setView,
    lastQuery,
    pendingAskQuery,
    setPendingAskQuery,
    detailDecisionId,
    setDetailDecisionId,
  } = useApp();
  const [query, setQuery] = useState("Why CockroachDB for payments?");
  const [limit, setLimit] = useState(8);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [minTrust, setMinTrust] = useState(0);

  const [debouncedLength, setDebouncedLength] = useState(query.trim().length);
  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedLength(query.trim().length), 200);
    return () => window.clearTimeout(handle);
  }, [query]);

  useEffect(() => {
    if (!pendingAskQuery || pendingAskQuery.length < 3) return;
    const q = pendingAskQuery;
    setPendingAskQuery(null);
    setQuery(q);
    setLoading(true);
    setError(null);
    void queryMemory({
      query: q,
      workspace_id: workspaceId.trim() || "local-dev",
      limit,
    })
      .then((result) => {
        setLastQuery(result);
        setExploreDecisions(result.results);
        if (result.results[0]) setSelectedDecisionId(result.results[0].event_id);
        pushMessage("user", q);
        pushMessage("assistant", summarizeQueryResults(result));
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => setLoading(false));
  }, [
    pendingAskQuery,
    setPendingAskQuery,
    workspaceId,
    limit,
    setLastQuery,
    setExploreDecisions,
    setSelectedDecisionId,
    pushMessage,
  ]);

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
      if (ENTITY_PREFIXES.some((p) => id.startsWith(p))) {
        const firstId = lastQuery?.results[0]?.event_id;
        if (firstId) setSelectedDecisionId(firstId);
      } else {
        setSelectedDecisionId(id);
      }
      const decisionId =
        id.startsWith("person:") || id.startsWith("system:") ? undefined : id;
      setView("explore", decisionId ? { decision: decisionId } : undefined);
    },
    [lastQuery, setSelectedDecisionId, setView],
  );

  const rawResults = lastQuery?.results ?? [];
  const filteredResults = useMemo(() => {
    let list = [...rawResults];
    if (sourceFilter !== "all") {
      list = list.filter((d) => d.source.toLowerCase().includes(sourceFilter));
    }
    if (minTrust > 0) {
      list = list.filter((d) => d.trust_score >= minTrust);
    }
    return list.sort(sortByRank);
  }, [rawResults, sourceFilter, minTrust]);

  const detailDecision =
    filteredResults.find((d) => d.event_id === detailDecisionId) ??
    rawResults.find((d) => d.event_id === detailDecisionId) ??
    null;

  const topResult = filteredResults[0] ?? rawResults[0];

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
        <StateView tone="error" title="Search failed">
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
            setView("explore", { decision: topResult.event_id });
          }}
        />
      ) : null}

      {lastQuery ? (
        <section className="results panel fade-in" aria-live="polite">
          <header className="panel__head">
            <h2>
              {filteredResults.length} shown · {lastQuery.total} total · {lastQuery.latency_ms}ms
              {typeof lastQuery.coverage_score === "number" ? (
                <>
                  {" "}
                  · coverage{" "}
                  <span
                    className="coverage-badge"
                    title="Heuristic memory completeness for this workspace"
                  >
                    {Math.round(lastQuery.coverage_score * 100)}%
                  </span>
                </>
              ) : null}
            </h2>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => setView("explore")}
            >
              Open memory map →
            </button>
          </header>

          <div className="ask-filters" role="toolbar" aria-label="Filter results">
            {SOURCE_FILTERS.map((src) => (
              <button
                key={src}
                type="button"
                className={`chip ${sourceFilter === src ? "chip--active" : ""}`}
                onClick={() => setSourceFilter(src)}
              >
                {src === "all" ? "All sources" : src}
              </button>
            ))}
            <label className="ask-filters__trust">
              Min trust {scorePercent(minTrust)}%
              <input
                type="range"
                min={0}
                max={0.9}
                step={0.1}
                value={minTrust}
                onChange={(e) => setMinTrust(Number(e.target.value))}
              />
            </label>
          </div>

          <div className="ask-results-layout">
            <div className="decision-list">
              {filteredResults.length === 0 ? (
                <StateView icon={<IconEmpty size={28} />} title="No memories matched filters">
                  Broaden your query or lower the trust threshold. If this workspace is new, capture
                  decisions from your tools or the AI agents view.
                </StateView>
              ) : (
                filteredResults.map((d, i) => (
                  <DecisionCard
                    key={d.event_id}
                    decision={d}
                    defaultOpen={i === 0}
                    onSelect={handleCardSelect}
                    onDetail={setDetailDecisionId}
                    selected={d.event_id === detailDecisionId}
                  />
                ))
              )}
            </div>
            <DecisionDetailPanel
              decision={detailDecision}
              onClose={() => setDetailDecisionId(null)}
              onExplore={(id) => {
                setSelectedDecisionId(id);
                setView("explore", { decision: id });
              }}
            />
          </div>
        </section>
      ) : null}
    </article>
  );
}
