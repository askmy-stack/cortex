// V006 — Contradiction review queue nodes (Layer 4 intelligence).
// Linked to two or more Decision nodes for human resolution.

MERGE (:SchemaVersion {version: 6, applied_at: datetime(), description: "Contradiction nodes"});

CREATE CONSTRAINT contradiction_id_unique IF NOT EXISTS
  FOR (c:Contradiction) REQUIRE c.id IS UNIQUE;

CREATE INDEX contradiction_workspace_status IF NOT EXISTS
  FOR (c:Contradiction) ON (c.workspace_id, c.status);
