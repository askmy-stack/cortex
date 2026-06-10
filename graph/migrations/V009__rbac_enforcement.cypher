// V009 — RBAC enforcement indices + GDPR audit log schema
// Decision: D-008 — Graph-level RBAC with DID agent identity.
// Extends V002 access_policy coverage to all memory node types and adds
// GdprAuditLog for Right-to-Erasure cascade deletes (graph/gdpr.py).

CREATE INDEX person_access_policy IF NOT EXISTS
  FOR (p:Person) ON (p.access_policy);

CREATE INDEX system_access_policy IF NOT EXISTS
  FOR (s:System) ON (s.access_policy);

CREATE INDEX rationale_access_policy IF NOT EXISTS
  FOR (r:Rationale) ON (r.access_policy);

CREATE INDEX exception_access_policy IF NOT EXISTS
  FOR (e:Exception) ON (e.access_policy);

CREATE INDEX team_access_policy IF NOT EXISTS
  FOR (t:Team) ON (t.access_policy);

CREATE INDEX outcome_access_policy IF NOT EXISTS
  FOR (o:Outcome) ON (o.access_policy);

CREATE INDEX contradiction_access_policy IF NOT EXISTS
  FOR (c:Contradiction) ON (c.access_policy);

CREATE CONSTRAINT gdpr_audit_id_unique IF NOT EXISTS
  FOR (a:GdprAuditLog) REQUIRE a.id IS UNIQUE;

CREATE INDEX gdpr_audit_workspace IF NOT EXISTS
  FOR (a:GdprAuditLog) ON (a.workspace_id, a.deleted_at);

MERGE (v:SchemaVersion {version: 9})
SET v.applied_at = datetime(), v.description = "RBAC enforcement + GDPR audit";
