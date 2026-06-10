import type { DecisionResult } from "../../types";
import { formatRelativeTime, scoreLabel, truncate } from "../../lib/format";

type Props = {
  decision: DecisionResult;
  onSelect: (id: string) => void;
};

/** Compact decision row for dashboard feeds — no UUIDs, human labels only. */
export function DecisionTeaser({ decision, onSelect }: Props) {
  const who = decision.made_by[0]?.split("@")[0] ?? "Team";
  const system = decision.affects[0] ?? "org-wide";

  return (
    <button type="button" className="decision-teaser" onClick={() => onSelect(decision.event_id)}>
      <p className="decision-teaser__content">{truncate(decision.content, 100)}</p>
      <footer className="decision-teaser__meta">
        <span>{who}</span>
        <span aria-hidden>·</span>
        <span>{formatRelativeTime(decision.extracted_at)}</span>
        <span aria-hidden>·</span>
        <span>{system}</span>
        <span className="decision-teaser__trust">{scoreLabel(decision.trust_score)} trust</span>
      </footer>
    </button>
  );
}
