import type { DecisionResult } from "../../types";
import { formatSource, scorePercent } from "../../lib/format";

type Props = {
  decision: DecisionResult;
  onExplore?: () => void;
};

/**
 * Product storytelling frame: what / why / who / systems.
 */
export function StoryStrip({ decision, onExplore }: Props) {
  const who = decision.made_by.length
    ? decision.made_by.map((p) => p.split("@")[0]).join(", ")
    : "Not captured";
  const systems = decision.affects.length ? decision.affects.join(", ") : "None listed";
  const why = decision.rationale[0] ?? "Rationale not captured yet.";

  return (
    <section className="story-strip" aria-label="Decision summary">
      <header className="story-strip__head">
        <h2 className="story-strip__title">Top match</h2>
        <p className="story-strip__scores muted">
          Trust {scorePercent(decision.trust_score)}% · Impact{" "}
          {scorePercent(decision.importance_score)}%
        </p>
      </header>
      <div className="story-strip__grid">
        <article className="story-pill story-pill--what">
          <span className="story-pill__label">What happened</span>
          <p className="story-pill__value">{decision.content}</p>
        </article>
        <article className="story-pill story-pill--why">
          <span className="story-pill__label">Why</span>
          <p className="story-pill__value">{why}</p>
        </article>
        <article className="story-pill story-pill--who">
          <span className="story-pill__label">Who decided</span>
          <p className="story-pill__value">{who}</p>
        </article>
        <article className="story-pill story-pill--systems">
          <span className="story-pill__label">Systems affected</span>
          <p className="story-pill__value">{systems}</p>
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
