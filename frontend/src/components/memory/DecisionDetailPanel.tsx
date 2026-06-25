import type { DecisionResult } from "../../types";
import { formatRelativeTime, formatSource, scorePercent } from "../../lib/format";
import { DecisionScores } from "./DecisionScores";
import { buildDecisionShareUrl } from "../../lib/routing";
import { useToast } from "../ui/Toast";
import { IconLink } from "../ui/icons";

type Props = {
  decision: DecisionResult | null;
  onClose: () => void;
  onExplore?: (id: string) => void;
};

/** Side panel with full decision provenance and scores. */
export function DecisionDetailPanel({ decision, onClose, onExplore }: Props) {
  const { showToast } = useToast();

  if (!decision) return null;

  async function copyLink(): Promise<void> {
    const url = buildDecisionShareUrl(decision!.event_id);
    try {
      await navigator.clipboard.writeText(url);
      showToast("Decision link copied");
    } catch {
      showToast("Could not copy link");
    }
  }

  return (
    <aside className="detail-panel" role="complementary" aria-label="Decision details">
      <header className="detail-panel__head">
        <h2 className="detail-panel__title">Decision detail</h2>
        <button type="button" className="btn btn--ghost" onClick={onClose} aria-label="Close panel">
          Close
        </button>
      </header>
      <p className="detail-panel__content">{decision.content}</p>
      <div className="detail-panel__meta">
        <span className="badge badge--source">{formatSource(decision.source)}</span>
        {decision.channel ? <span className="badge badge--muted">{decision.channel}</span> : null}
        <span className={`badge badge--status badge--${decision.status}`}>{decision.status}</span>
        <span className="decision-card__time">{formatRelativeTime(decision.extracted_at)}</span>
      </div>
      <DecisionScores
        importance_score={decision.importance_score}
        trust_score={decision.trust_score}
        extraction_confidence={decision.extraction_confidence}
      />
      {decision.made_by.length > 0 ? (
        <section className="decision-card__section">
          <h4>Who decided</h4>
          <ul className="chip-list">
            {decision.made_by.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {decision.affects.length > 0 ? (
        <section className="decision-card__section">
          <h4>Systems affected</h4>
          <ul className="chip-list chip-list--accent">
            {decision.affects.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {decision.rationale.length > 0 ? (
        <section className="decision-card__section">
          <h4>Why this matters</h4>
          <ul className="rationale-list">
            {decision.rationale.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </section>
      ) : null}
      <footer className="detail-panel__actions">
        <button type="button" className="btn btn--secondary" onClick={() => void copyLink()}>
          <IconLink size={16} aria-hidden /> Copy link
        </button>
        {onExplore ? (
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => onExplore(decision.event_id)}
          >
            Open in memory map
          </button>
        ) : null}
      </footer>
      <p className="muted detail-panel__scores">
        Trust {scorePercent(decision.trust_score)}% · Impact {scorePercent(decision.importance_score)}%
      </p>
    </aside>
  );
}
