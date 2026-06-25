import { memo, useId, useState } from "react";
import type { DecisionResult } from "../../types";
import { formatRelativeTime, formatSource } from "../../lib/format";
import { buildDecisionShareUrl } from "../../lib/routing";
import { useToast } from "../ui/Toast";
import { DecisionScores } from "./DecisionScores";
import { IconLink } from "../ui/icons";

type Props = {
  decision: DecisionResult;
  defaultOpen?: boolean;
  onSelect?: (id: string) => void;
  onDetail?: (id: string) => void;
  selected?: boolean;
};

function DecisionCardInner({
  decision: d,
  defaultOpen,
  onSelect,
  onDetail,
  selected,
}: Props) {
  const [open, setOpen] = useState(!!defaultOpen);
  const panelId = useId();
  const { showToast } = useToast();

  async function copyLink(): Promise<void> {
    try {
      await navigator.clipboard.writeText(buildDecisionShareUrl(d.event_id));
      showToast("Decision link copied");
    } catch {
      showToast("Could not copy link");
    }
  }

  return (
    <article className={`decision-card fade-in ${selected ? "decision-card--selected" : ""}`}>
      <button
        type="button"
        className="decision-card__header"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => {
          setOpen((v) => !v);
          onDetail?.(d.event_id);
        }}
      >
        <span className="decision-card__type">{d.event_type}</span>
        <h3 className="decision-card__title">{d.content}</h3>
        <span
          className={`decision-card__chevron ${open ? "decision-card__chevron--open" : ""}`}
          aria-hidden
        >
          ▾
        </span>
      </button>

      <div className="decision-card__meta">
        <span className="badge badge--source">{formatSource(d.source)}</span>
        {d.channel ? <span className="badge badge--muted">{d.channel}</span> : null}
        <span className={`badge badge--status badge--${d.status}`}>{d.status}</span>
        <span className="decision-card__time">{formatRelativeTime(d.extracted_at)}</span>
      </div>

      {open ? (
        <div className="decision-card__body" id={panelId}>
          <DecisionScores
            importance_score={d.importance_score}
            trust_score={d.trust_score}
            extraction_confidence={d.extraction_confidence}
          />

          {d.made_by.length > 0 ? (
            <section className="decision-card__section">
              <h4>Who decided</h4>
              <ul className="chip-list">
                {d.made_by.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </section>
          ) : null}

          {d.affects.length > 0 ? (
            <section className="decision-card__section">
              <h4>Systems affected</h4>
              <ul className="chip-list chip-list--accent">
                {d.affects.map((s) => (
                  <li key={s}>
                    <button
                      type="button"
                      className="chip-link"
                      onClick={() => onSelect?.(`system:${s}`)}
                    >
                      {s}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {d.rationale.length > 0 ? (
            <section className="decision-card__section">
              <h4>Why this matters</h4>
              <ul className="rationale-list">
                {d.rationale.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </section>
          ) : null}

          <footer className="decision-card__footer">
            <button type="button" className="btn-text" onClick={() => void copyLink()}>
              <IconLink size={14} aria-hidden /> Copy link
            </button>
            <button type="button" className="btn-text" onClick={() => onSelect?.(d.event_id)}>
              View in memory map →
            </button>
          </footer>
        </div>
      ) : null}
    </article>
  );
}

export const DecisionCard = memo(DecisionCardInner, (prev, next) => {
  return (
    prev.decision === next.decision &&
    prev.selected === next.selected &&
    prev.defaultOpen === next.defaultOpen &&
    prev.onSelect === next.onSelect &&
    prev.onDetail === next.onDetail
  );
});
