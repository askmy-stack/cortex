// V001 — Initial Neo4j schema
// Core node types, uniqueness constraints, and property indices.
// Decision: D-002 — Neo4j as structural memory store.
// Run via: graph/migrate.py or manually via cypher-shell.
// Neo4j Community: no property-existence constraints (Enterprise-only).
// workspace_id is enforced in graph/writer.py.

// ─────────────────────────────────────────────────────────────────────────────
// DECISION — core memory unit
// ─────────────────────────────────────────────────────────────────────────────
CREATE CONSTRAINT decision_id_unique IF NOT EXISTS
  FOR (d:Decision) REQUIRE d.id IS UNIQUE;

CREATE INDEX decision_workspace_status IF NOT EXISTS
  FOR (d:Decision) ON (d.workspace_id, d.status);

CREATE INDEX decision_importance IF NOT EXISTS
  FOR (d:Decision) ON (d.importance_score);

CREATE INDEX decision_extracted_at IF NOT EXISTS
  FOR (d:Decision) ON (d.extracted_at);

// ─────────────────────────────────────────────────────────────────────────────
// PERSON — org member or AI agent
// ─────────────────────────────────────────────────────────────────────────────
CREATE CONSTRAINT person_id_unique IF NOT EXISTS
  FOR (p:Person) REQUIRE p.id IS UNIQUE;

CREATE INDEX person_workspace IF NOT EXISTS
  FOR (p:Person) ON (p.workspace_id);

// ─────────────────────────────────────────────────────────────────────────────
// SYSTEM — service, component, or infrastructure
// ─────────────────────────────────────────────────────────────────────────────
CREATE CONSTRAINT system_id_unique IF NOT EXISTS
  FOR (s:System) REQUIRE s.id IS UNIQUE;

CREATE INDEX system_workspace_name IF NOT EXISTS
  FOR (s:System) ON (s.workspace_id, s.name);

CREATE INDEX system_criticality IF NOT EXISTS
  FOR (s:System) ON (s.criticality);

// ─────────────────────────────────────────────────────────────────────────────
// EXCEPTION — known failure mode or edge case
// ─────────────────────────────────────────────────────────────────────────────
CREATE CONSTRAINT exception_id_unique IF NOT EXISTS
  FOR (e:Exception) REQUIRE e.id IS UNIQUE;

CREATE INDEX exception_workspace IF NOT EXISTS
  FOR (e:Exception) ON (e.workspace_id);

// ─────────────────────────────────────────────────────────────────────────────
// OUTCOME — measured result of a decision
// ─────────────────────────────────────────────────────────────────────────────
CREATE CONSTRAINT outcome_id_unique IF NOT EXISTS
  FOR (o:Outcome) REQUIRE o.id IS UNIQUE;

// ─────────────────────────────────────────────────────────────────────────────
// TEAM — organizational unit
// ─────────────────────────────────────────────────────────────────────────────
CREATE CONSTRAINT team_id_unique IF NOT EXISTS
  FOR (t:Team) REQUIRE t.id IS UNIQUE;

CREATE INDEX team_workspace IF NOT EXISTS
  FOR (t:Team) ON (t.workspace_id);

// Schema version recorded last so a failed migration does not mark this version applied.
MERGE (v:SchemaVersion {version: 1})
SET v.applied_at = datetime(), v.description = "Initial schema";
