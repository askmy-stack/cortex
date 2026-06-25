import { useCallback, useEffect, useState } from "react";
import { fetchCausalChain } from "../../api/client";
import type { DecisionResult } from "../../types";
import { formatRelativeTime } from "../../lib/format";
import { Skeleton } from "../ui/Skeleton";
import { StateView } from "../ui/StateView";

type Props = {
  decisionId: string;
  workspaceId: string;
  onSelectDecision?: (id: string) => void;
};

export function LineageView({ decisionId, workspaceId, onSelectDecision }: Props) {
  const [nodes, setNodes] = useState<DecisionResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchCausalChain(decisionId, workspaceId);
      setNodes(res.nodes);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setNodes([]);
    } finally {
      setLoading(false);
    }
  }, [decisionId, workspaceId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div aria-live="polite">
        <Skeleton variant="row" />
        <Skeleton variant="row" />
        <Skeleton variant="row" />
      </div>
    );
  }
  if (error) {
    return (
      <StateView
        tone="error"
        title="Couldn't trace lineage"
        action={
          <button type="button" className="btn btn--secondary" onClick={() => void load()}>
            Retry
          </button>
        }
      >
        {error}
      </StateView>
    );
  }
  if (nodes.length === 0) {
    return (
      <StateView title="No lineage yet">
        This decision hasn't superseded or been triggered by anything else in the graph yet.
      </StateView>
    );
  }

  return (
    <ol className="lineage">
      {nodes.map((d, i) => (
        <li key={d.event_id} className="lineage__step">
          <span className="lineage__index">{i + 1}</span>
          <article
            className={`lineage__card ${onSelectDecision ? "lineage__card--interactive" : ""}`}
            role={onSelectDecision ? "button" : undefined}
            tabIndex={onSelectDecision ? 0 : undefined}
            onClick={onSelectDecision ? () => onSelectDecision(d.event_id) : undefined}
            onKeyDown={
              onSelectDecision
                ? (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelectDecision(d.event_id);
                    }
                  }
                : undefined
            }
          >
            <p className="lineage__content">{d.content}</p>
            <p className="lineage__meta">
              {formatRelativeTime(d.extracted_at)} · {d.status}
              {d.supersedes_ids && d.supersedes_ids.length > 0
                ? ` · supersedes ${d.supersedes_ids.length}`
                : ""}
            </p>
          </article>
          {i < nodes.length - 1 ? (
            <span className="lineage__arrow" aria-hidden>
              ↓
            </span>
          ) : null}
        </li>
      ))}
    </ol>
  );
}
