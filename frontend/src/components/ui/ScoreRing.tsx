import { scoreLabel, scorePercent } from "../../lib/format";

type Props = {
  value: number;
  label: string;
  size?: "sm" | "md";
};

export function ScoreRing({ value, label, size = "md" }: Props) {
  const pct = scorePercent(value);
  const radius = size === "sm" ? 22 : 30;
  const stroke = size === "sm" ? 4 : 5;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;
  const dim = (radius + stroke) * 2;

  return (
    <div className={`score-ring score-ring--${size}`} aria-label={`${label}: ${scoreLabel(value)}`}>
      <svg width={dim} height={dim} viewBox={`0 0 ${dim} ${dim}`} role="img" aria-hidden>
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
      <div className="score-ring-center">
        <span className="score-ring-pct">{pct}</span>
        <span className="score-ring-label">{label}</span>
      </div>
    </div>
  );
}
