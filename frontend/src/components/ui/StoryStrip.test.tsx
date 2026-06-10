import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StoryStrip } from "./StoryStrip";
import type { DecisionResult } from "../../types";

const decision: DecisionResult = {
  event_id: "d1",
  event_type: "decision",
  content: "Migrate payments to CockroachDB for multi-region scale.",
  made_by: ["dan@acme.example"],
  affects: ["payments-service"],
  rationale: ["Postgres failover gaps in eu-west."],
  importance_score: 0.88,
  trust_score: 0.82,
  extraction_confidence: 0.92,
  source: "slack",
  channel: "C-architecture",
  extracted_at: "2026-05-14T12:00:00Z",
  status: "active",
};

describe("StoryStrip", () => {
  it("renders product storytelling pillars", () => {
    render(<StoryStrip decision={decision} />);
    expect(screen.getByText("What happened")).toBeInTheDocument();
    expect(screen.getByText("Why")).toBeInTheDocument();
    expect(screen.getByText("Who decided")).toBeInTheDocument();
    expect(screen.getByText("Systems affected")).toBeInTheDocument();
    expect(screen.getByText(/dan/)).toBeInTheDocument();
  });

  it("calls onExplore when action clicked", () => {
    const onExplore = vi.fn();
    render(<StoryStrip decision={decision} onExplore={onExplore} />);
    screen.getByRole("button", { name: /see connections/i }).click();
    expect(onExplore).toHaveBeenCalledOnce();
  });
});
