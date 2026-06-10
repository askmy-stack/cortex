import type { DecisionResult } from "../../types";
import { formatSource, truncate } from "../../lib/format";

type Props = {
  decision: DecisionResult;
  onExplore?: () => void;
};

/**
 * Product storytelling frame: what / why / who / systems / next.
 * Surfaces decision narrative without exposing raw technical fields.
 */
export function StoryStrip({ decision, onExplore }: Props) {
  const who = decision.made_by.length
    ? decision.made_by.map((p) => p.split("@")[0]).join(", ")
    : "Unknown";
  const systems = decision.affects.length ? decision.affects.join(", ") : "None listed";
  const why = decision.rationale[0] ?? "Rationale not captured yet.";

  return (
    <section className="story-strip" aria-label="Decision summary">
      <div className="story-strip__grid">
        <article className="story-pill story-pill--what">
          <span className="story-pill__label">What happened</span>
          <p>{truncate(decision.content, 140)}</p>
        </article>
        <article className="story-pill story-pill--why">
          <span className="story-pill__label">Why</span>
          <p>{truncate(why, 120)}</p>
        </article>
        <article className="story-pill story-pill--who">
          <span className="story-pill__label">Who decided</span>
          <p>{who}</p>
        </article>
        <article className="story-pill story-pill--systems">
          <span className="story-pill__label">Systems affected</span>
          <p>{systems}</p>
        </article>
      </div>
      <footer className="story-strip__foot">
        <span className="muted">
          Source: {formatSource(decision.source)}
          {decision.channel ? ` · ${decision.channel}` : ""}
        </span>
        {onExplore ? (
          <button type="button" className="btn btn--ghost btn--sm" onClick={onExplore}>
            See connections →
          </button>
        ) : null}
      </footer>
    </section>
  );
}
