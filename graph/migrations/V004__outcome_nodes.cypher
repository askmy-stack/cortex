// V004 — Outcome node type and decision-outcome linking indices.
// Phase 8 deliverable — added to schema now for completeness.
// Outcome nodes link decisions to real measured metrics.

MERGE (:SchemaVersion {version: 4, applied_at: datetime(), description: "Outcome nodes"});

CREATE INDEX outcome_decision_id IF NOT EXISTS
  FOR (o:Outcome) ON (o.decision_id);

CREATE INDEX outcome_measured_at IF NOT EXISTS
  FOR (o:Outcome) ON (o.measured_at);

CREATE INDEX outcome_target_met IF NOT EXISTS
  FOR (o:Outcome) ON (o.target_met);
