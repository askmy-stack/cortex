import { useMemo } from "react";
import type { DecisionResult } from "../../types";
import { truncate } from "../../lib/format";

type GraphNode = {
  id: string;
  label: string;
  kind: "decision" | "person" | "system";
  x: number;
  y: number;
};

type GraphEdge = { from: string; to: string };

type Props = {
  decisions: DecisionResult[];
  focusId?: string | null;
  onFocus?: (id: string) => void;
};

function graphDimensions(decisionCount: number): { w: number; h: number } {
  const w = Math.max(640, Math.min(980, 520 + decisionCount * 28));
  const h = Math.max(360, Math.min(560, 300 + decisionCount * 22));
  return { w, h };
}

export function MemoryGraph({ decisions, focusId, onFocus }: Props) {
  const { w, h } = graphDimensions(decisions.length);
  const { nodes, edges } = useMemo(
    () => buildGraph(decisions, focusId, w, h),
    [decisions, focusId, w, h],
  );

  if (decisions.length === 0) {
    return (
      <div className="graph-empty">
        <p>Search for decisions to see how people, systems, and choices connect.</p>
      </div>
    );
  }

  return (
    <div className="memory-graph">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="memory-graph__svg"
        role="img"
        aria-label="Memory relationship map"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <linearGradient id="edgeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.15" />
            <stop offset="100%" stopColor="var(--accent-violet)" stopOpacity="0.5" />
          </linearGradient>
        </defs>
        {edges.map((e) => {
          const a = nodes.find((n) => n.id === e.from);
          const b = nodes.find((n) => n.id === e.to);
          if (!a || !b) return null;
          return (
            <line
              key={`${e.from}-${e.to}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              className="memory-graph__edge"
              stroke="url(#edgeGrad)"
            />
          );
        })}
        {nodes.map((n) => (
          <g
            key={n.id}
            className={`memory-graph__node memory-graph__node--${n.kind} ${
              focusId === n.id ? "memory-graph__node--focus" : ""
            }`}
            transform={`translate(${n.x}, ${n.y})`}
            onClick={() => onFocus?.(n.id)}
            style={{ cursor: onFocus ? "pointer" : "default" }}
            role="button"
            tabIndex={0}
            aria-label={`${n.kind}: ${n.label}`}
            aria-pressed={focusId === n.id}
            onKeyDown={(ev) => {
              if (ev.key === "Enter" || ev.key === " ") {
                ev.preventDefault();
                onFocus?.(n.id);
              }
            }}
          >
            <circle r={n.kind === "decision" ? 28 : 18} className="memory-graph__circle" />
            <text className="memory-graph__label" textAnchor="middle" dy={n.kind === "decision" ? 44 : 32}>
              {truncate(n.label, n.kind === "decision" ? 28 : 14)}
            </text>
          </g>
        ))}
      </svg>
      <div className="memory-graph__legend">
        <span>
          <i className="dot dot--decision" /> Decision
        </span>
        <span>
          <i className="dot dot--person" /> Person
        </span>
        <span>
          <i className="dot dot--system" /> System
        </span>
        <span className="memory-graph__count muted">
          {decisions.length} decision{decisions.length === 1 ? "" : "s"}
        </span>
      </div>
    </div>
  );
}

function buildGraph(
  decisions: DecisionResult[],
  focusId: string | null | undefined,
  w: number,
  h: number,
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  const cx = w / 2;
  const cy = h / 2 - 20;

  const primary = focusId
    ? decisions.find((d) => d.event_id === focusId) ?? decisions[0]
    : decisions[0];
  if (!primary) return { nodes, edges };

  nodes.push({
    id: primary.event_id,
    label: primary.content,
    kind: "decision",
    x: cx,
    y: cy,
  });

  const people = [...new Set(decisions.flatMap((d) => d.made_by))].slice(0, 8);
  const systems = [...new Set(decisions.flatMap((d) => d.affects))].slice(0, 10);

  people.forEach((p, i) => {
    const angle = Math.PI + (i / Math.max(people.length, 1)) * Math.PI;
    const id = `person:${p}`;
    nodes.push({
      id,
      label: p,
      kind: "person",
      x: cx + Math.cos(angle) * (w * 0.22),
      y: cy + Math.sin(angle) * (h * 0.28),
    });
    edges.push({ from: id, to: primary.event_id });
  });

  systems.forEach((s, i) => {
    const angle = (i / Math.max(systems.length, 1)) * Math.PI;
    const id = `system:${s}`;
    nodes.push({
      id,
      label: s,
      kind: "system",
      x: cx + Math.cos(angle) * (w * 0.25),
      y: cy + Math.sin(angle) * (h * 0.25) - 30,
    });
    edges.push({ from: primary.event_id, to: id });
  });

  const others = decisions.filter((d) => d.event_id !== primary.event_id);
  others.forEach((d, i) => {
    const angle = (i / Math.max(others.length, 1)) * Math.PI * 1.6 + Math.PI * 0.2;
    const radius = Math.min(w, h) * 0.32;
    nodes.push({
      id: d.event_id,
      label: d.content,
      kind: "decision",
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius + h * 0.12,
    });
    if (d.affects[0]) {
      edges.push({ from: d.event_id, to: `system:${d.affects[0]}` });
    } else if (primary.affects[0]) {
      edges.push({ from: d.event_id, to: `system:${primary.affects[0]}` });
    }
  });

  return { nodes, edges };
}
