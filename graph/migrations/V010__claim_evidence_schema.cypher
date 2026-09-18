// V010 — Claim + Evidence graph schema (Cortex V2 Phase 1 foundations)
// Feature flag CORTEX_EVIDENCE_GRAPH gates application writers; schema is safe to apply always.

CREATE CONSTRAINT claim_id_unique IF NOT EXISTS
  FOR (c:Claim) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS
  FOR (e:Evidence) REQUIRE e.id IS UNIQUE;

CREATE INDEX claim_workspace IF NOT EXISTS
  FOR (c:Claim) ON (c.workspace_id);

CREATE INDEX claim_status IF NOT EXISTS
  FOR (c:Claim) ON (c.status);

CREATE INDEX claim_subject IF NOT EXISTS
  FOR (c:Claim) ON (c.subject);

CREATE INDEX claim_decision_id IF NOT EXISTS
  FOR (c:Claim) ON (c.decision_id);

CREATE INDEX claim_valid_from IF NOT EXISTS
  FOR (c:Claim) ON (c.valid_from);

CREATE INDEX evidence_workspace IF NOT EXISTS
  FOR (e:Evidence) ON (e.workspace_id);

CREATE INDEX evidence_authority IF NOT EXISTS
  FOR (e:Evidence) ON (e.authority_class);

CREATE INDEX evidence_source IF NOT EXISTS
  FOR (e:Evidence) ON (e.source_type, e.source_id);

CREATE INDEX claim_access_policy IF NOT EXISTS
  FOR (c:Claim) ON (c.access_policy);

CREATE INDEX evidence_access_policy IF NOT EXISTS
  FOR (e:Evidence) ON (e.access_policy);

MERGE (v:SchemaVersion {version: 10})
SET v.applied_at = datetime(), v.description = "Claim + Evidence schema";
