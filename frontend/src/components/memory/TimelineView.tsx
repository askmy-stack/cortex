import type { DecisionResult } from "../../types";
import { formatRelativeTime, formatSource } from "../../lib/format";
import { StateView } from "../ui/StateView";
import { IconEmpty } from "../ui/icons";

type Props = {
  decisions: DecisionResult[];
  onSelect?: (decisionId: string) => void;
};

export function TimelineView({ decisions, onSelect }: Props) {
  const sorted = [...decisions].sort(
    (a, b) => new Date(b.extracted_at).getTime() - new Date(a.extracted_at).getTime(),
  );

  if (sorted.length === 0) {
    return (
      <StateView icon={<IconEmpty size={28} />} title="Timeline is empty">
        Your organizational timeline will appear here after you search or load memories.
      </StateView>
    );
  }

  return (
    <ol className="timeline">
      {sorted.map((d, i) => (
        <li
          key={d.event_id}
          className="timeline__item fade-in"
          style={{ animationDelay: `${i * 60}ms` }}
        >
          <span className="timeline__dot" aria-hidden />
          <article
            className={`timeline__card ${onSelect ? "timeline__card--interactive" : ""}`}
            role={onSelect ? "button" : undefined}
            tabIndex={onSelect ? 0 : undefined}
            onClick={onSelect ? () => onSelect(d.event_id) : undefined}
            onKeyDown={
              onSelect
                ? (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(d.event_id);
                    }
                  }
                : undefined
            }
          >
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
            {onSelect ? (
              <p className="timeline__action muted">Click to focus in relationship map →</p>
            ) : null}
          </article>
        </li>
      ))}
    </ol>
  );
}
