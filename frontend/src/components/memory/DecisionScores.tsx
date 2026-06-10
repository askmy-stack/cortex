import type { DecisionResult } from "../../types";
import { scoreLabel } from "../../lib/format";
import { ScoreRing } from "../ui/ScoreRing";

type Metric = {
  key: string;
  label: string;
  value: number;
  hint: string;
};

type Props = Pick<DecisionResult, "importance_score" | "trust_score" | "extraction_confidence">;

/** Responsive confidence metrics — impact, trust, and extraction clarity. */
export function DecisionScores({ importance_score, trust_score, extraction_confidence }: Props) {
  const metrics: Metric[] = [
    {
      key: "impact",
      label: "Impact",
      value: importance_score,
      hint: scoreLabel(importance_score),
    },
    {
      key: "trust",
      label: "Trust",
      value: trust_score,
      hint: scoreLabel(trust_score),
    },
    {
      key: "clarity",
      label: "Clarity",
      value: extraction_confidence,
      hint: scoreLabel(extraction_confidence),
    },
  ];

  return (
    <section className="decision-scores" aria-label="Confidence signals">
      <header className="decision-scores__head">
        <h4 className="decision-scores__title">Confidence signals</h4>
        <p className="decision-scores__subtitle">How strongly this memory is scored for retrieval</p>
      </header>
      <ul className="decision-scores__grid">
        {metrics.map((m) => (
          <li key={m.key} className="score-metric">
            <ScoreRing value={m.value} size="sm" />
            <div className="score-metric__copy">
              <span className="score-metric__label">{m.label}</span>
              <span className="score-metric__qualifier">{m.hint}</span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
