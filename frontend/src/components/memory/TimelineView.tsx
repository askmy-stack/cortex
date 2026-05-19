import type { DecisionResult } from "../../types";
import { formatRelativeTime, formatSource } from "../../lib/format";

type Props = { decisions: DecisionResult[] };

export function TimelineView({ decisions }: Props) {
  const sorted = [...decisions].sort(
    (a, b) => new Date(b.extracted_at).getTime() - new Date(a.extracted_at).getTime(),
  );

  if (sorted.length === 0) {
    return (
      <section className="timeline-empty">
        <p>Your organizational timeline will appear here after you search or load memories.</p>
      </section>
    );
  }

  return (
    <ol className="timeline">
      {sorted.map((d, i) => (
        <li key={d.event_id} className="timeline__item fade-in" style={{ animationDelay: `${i * 60}ms` }}>
          <span className="timeline__dot" aria-hidden />
          <article className="timeline__card">
            <header className="timeline__header">
              <time dateTime={d.extracted_at}>{formatRelativeTime(d.extracted_at)}</time>
              <span className="badge badge--source">{formatSource(d.source)}</span>
            </header>
            <p className="timeline__content">{d.content}</p>
            {d.affects.length > 0 ? (
              <p className="timeline__meta">
                Affects <strong>{d.affects.join(", ")}</strong>
              </p>
            ) : null}
          </article>
        </li>
      ))}
    </ol>
  );
}
