import type { ContradictionItem, DecisionResult } from "../types";

export type DashboardMetrics = {
  decisionCount: number;
  avgTrust: number;
  avgImpact: number;
  pendingConflicts: number;
  activePeople: string[];
  trendingSystems: { name: string; count: number }[];
  recentDecisions: DecisionResult[];
};

/** Derive human-readable dashboard metrics from raw memory results. */
export function buildDashboardMetrics(
  decisions: DecisionResult[],
  contradictions: ContradictionItem[],
): DashboardMetrics {
  const systemCounts = new Map<string, number>();
  const people = new Set<string>();

  for (const d of decisions) {
    d.affects.forEach((s) => systemCounts.set(s, (systemCounts.get(s) ?? 0) + 1));
    d.made_by.forEach((p) => people.add(p));
  }

  const trendingSystems = [...systemCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([name, count]) => ({ name, count }));

  const trustSum = decisions.reduce((n, d) => n + d.trust_score, 0);
  const impactSum = decisions.reduce((n, d) => n + d.importance_score, 0);
  const n = decisions.length || 1;

  const sorted = [...decisions].sort(
    (a, b) => new Date(b.extracted_at).getTime() - new Date(a.extracted_at).getTime(),
  );

  return {
    decisionCount: decisions.length,
    avgTrust: decisions.length ? trustSum / n : 0,
    avgImpact: decisions.length ? impactSum / n : 0,
    pendingConflicts: contradictions.length,
    activePeople: [...people].slice(0, 6),
    trendingSystems,
    recentDecisions: sorted.slice(0, 5),
  };
}

/** Plain-language trust label for executives. */
export function trustHeadline(score: number): string {
  if (score >= 0.8) return "High confidence";
  if (score >= 0.6) return "Moderate confidence";
  if (score > 0) return "Building confidence";
  return "No data yet";
}
