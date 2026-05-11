// V003 — Temporal edge validity (Zep/Graphiti pattern).
// All edges carry valid_at and invalid_at (null = still active).
// This enables: "what did we believe about this system on 2025-12-01?"
// Research: Zep/Graphiti (arXiv:2501.13956) — 90% latency reduction via temporal edges.

MERGE (:SchemaVersion {version: 3, applied_at: datetime(), description: "Temporal edge validity"});

// Index for active relationship queries (most common access pattern)
CREATE INDEX decision_valid_at IF NOT EXISTS
  FOR (d:Decision) ON (d.valid_at);

CREATE INDEX decision_invalid_at IF NOT EXISTS
  FOR (d:Decision) ON (d.invalid_at);

// Note: Neo4j Community does not support relationship property indices.
// valid_at / invalid_at on edges enforced and queried at application layer.
// Pattern: WHERE r.invalid_at IS NULL = relationship is currently active.
