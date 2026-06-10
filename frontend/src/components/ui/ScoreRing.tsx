import { scoreLabel, scorePercent } from "../../lib/format";

type Props = {
  value: number;
  /** Shown below the ring — never inside, to avoid overlap with the score. */
  label?: string;
  size?: "sm" | "md";
};

export function ScoreRing({ value, label, size = "md" }: Props) {
  const pct = scorePercent(value);
  const radius = size === "sm" ? 28 : 36;
  const stroke = size === "sm" ? 4 : 5;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;
  const dim = (radius + stroke) * 2;
  const aria = label ? `${label}: ${scoreLabel(value)}, ${pct} percent` : `${scoreLabel(value)}, ${pct} percent`;

  return (
    <div className={`score-ring score-ring--${size}`} aria-label={aria}>
      <div className="score-ring__graphic" style={{ width: dim, height: dim }}>
        <svg
          className="score-ring__svg"
          width={dim}
          height={dim}
          viewBox={`0 0 ${dim} ${dim}`}
          role="img"
          aria-hidden
        >
          <circle
            className="score-ring-bg"
            cx={dim / 2}
            cy={dim / 2}
            r={radius}
            fill="none"
            strokeWidth={stroke}
          />
          <circle
            className="score-ring-fill"
            cx={dim / 2}
            cy={dim / 2}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            transform={`rotate(-90 ${dim / 2} ${dim / 2})`}
          />
        </svg>
        <span className="score-ring__value">{pct}</span>
      </div>
      {label ? <span className="score-ring__caption">{label}</span> : null}
    </div>
  );
}
