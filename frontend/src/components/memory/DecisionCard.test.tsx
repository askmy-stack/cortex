import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DecisionCard } from "./DecisionCard";
import type { DecisionResult } from "../../types";
import { ToastProvider } from "../ui/Toast";

const decision: DecisionResult = {
  event_id: "card-1",
  event_type: "decision",
  content: "Use Redis for session cache at checkout.",
  made_by: ["alex@acme.example"],
  affects: ["checkout-service"],
  rationale: ["Sub-millisecond reads matter for cart state."],
  importance_score: 0.75,
  trust_score: 0.8,
  extraction_confidence: 0.9,
  source: "slack",
  channel: "eng",
  extracted_at: "2026-05-14T12:00:00Z",
  status: "active",
};

describe("DecisionCard", () => {
  it("expands to show rationale on header click", () => {
    const view = render(
      <ToastProvider>
        <DecisionCard decision={decision} />
      </ToastProvider>,
    );
    fireEvent.click(view.getByRole("button", { name: /use redis/i }));
    expect(view.getByText(/sub-millisecond reads/i)).toBeInTheDocument();
  });

  it("shows copy link action when expanded", () => {
    const view = render(
      <ToastProvider>
        <DecisionCard decision={decision} defaultOpen />
      </ToastProvider>,
    );
    expect(view.getAllByRole("button", { name: /copy link/i }).length).toBeGreaterThan(0);
  });
});
