type Props = {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "accent" | "warn" | "ok";
  icon?: string;
};

/** Executive summary metric — readable at a glance, no raw IDs. */
export function MetricCard({ label, value, hint, tone = "default", icon }: Props) {
  return (
    <article className={`metric-card metric-card--${tone}`}>
      {icon ? (
        <span className="metric-card__icon" aria-hidden>
          {icon}
        </span>
      ) : null}
      <p className="metric-card__label">{label}</p>
      <p className="metric-card__value">{value}</p>
      {hint ? <p className="metric-card__hint">{hint}</p> : null}
    </article>
  );
}
