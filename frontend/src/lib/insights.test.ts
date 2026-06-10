import { describe, expect, it } from "vitest";
import { buildDashboardMetrics, trustHeadline } from "./insights";
import type { DecisionResult } from "../types";

const sampleDecision = (overrides: Partial<DecisionResult> = {}): DecisionResult => ({
  event_id: "id-1",
  event_type: "decision",
  content: "Sample",
  made_by: ["alice@acme.example"],
  affects: ["payments-service"],
  rationale: ["Because"],
  importance_score: 0.8,
  trust_score: 0.7,
  extraction_confidence: 0.9,
  source: "slack",
  channel: "C-arch",
  extracted_at: "2026-05-14T12:00:00Z",
  status: "active",
  ...overrides,
});

describe("buildDashboardMetrics", () => {
  it("aggregates systems and people from decisions", () => {
    const metrics = buildDashboardMetrics(
      [
        sampleDecision(),
        sampleDecision({
          event_id: "id-2",
          affects: ["payments-service", "billing-service"],
          made_by: ["bob@acme.example"],
        }),
      ],
      [],
    );
    expect(metrics.decisionCount).toBe(2);
    expect(metrics.trendingSystems[0]?.name).toBe("payments-service");
    expect(metrics.trendingSystems[0]?.count).toBe(2);
    expect(metrics.activePeople).toHaveLength(2);
  });

  it("counts pending contradictions", () => {
    const metrics = buildDashboardMetrics([], [
      {
        id: "c1",
        score: 0.9,
        explanation: "Conflict",
        new_decision_id: "a",
        prior_decision_id: "b",
        status: "pending",
      },
    ]);
    expect(metrics.pendingConflicts).toBe(1);
  });
});

describe("trustHeadline", () => {
  it("returns human labels for score bands", () => {
    expect(trustHeadline(0.85)).toBe("High confidence");
    expect(trustHeadline(0)).toBe("No data yet");
  });
});
