import { useEffect, useState } from "react";
import { fetchCausalChain } from "../../api/client";
import type { DecisionResult } from "../../types";
import { formatRelativeTime } from "../../lib/format";

type Props = {
  decisionId: string;
  workspaceId: string;
};

export function LineageView({ decisionId, workspaceId }: Props) {
  const [nodes, setNodes] = useState<DecisionResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchCausalChain(decisionId, workspaceId)
      .then((res) => {
        if (!cancelled) setNodes(res.nodes);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [decisionId, workspaceId]);

  if (loading) return <p className="loading-text">Tracing decision lineage…</p>;
  if (error) return <p className="alert alert--error">{error}</p>;
  if (nodes.length === 0) return <p className="muted">No lineage found for this decision.</p>;

  return (
    <ol className="lineage">
      {nodes.map((d, i) => (
        <li key={d.event_id} className="lineage__step">
          <span className="lineage__index">{i + 1}</span>
          <article className="lineage__card">
            <p className="lineage__content">{d.content}</p>
            <p className="lineage__meta">
              {formatRelativeTime(d.extracted_at)} · {d.status}
              {d.supersedes_ids && d.supersedes_ids.length > 0
                ? ` · supersedes ${d.supersedes_ids.length}`
                : ""}
            </p>
          </article>
          {i < nodes.length - 1 ? <span className="lineage__arrow" aria-hidden>↓</span> : null}
        </li>
      ))}
    </ol>
  );
}
