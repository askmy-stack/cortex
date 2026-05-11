// V002 — RBAC access_policy property on all node types.
// Decision: D-008 — Graph-level RBAC with DID agent identity.
// MUST be applied before any real data enters the system.
// access_policy structure: {roles, deny, classification, gdpr_subject}

MERGE (:SchemaVersion {version: 2, applied_at: datetime(), description: "RBAC access_policy"});

// Index for RBAC policy lookups across all node types
CREATE INDEX decision_access_policy IF NOT EXISTS
  FOR (d:Decision) ON (d.access_policy);

// Enforce access_policy is present on every Decision write
// (enforced at application layer in graph/writer.py — not a DB constraint
//  because Map type constraints aren't supported in Neo4j Community)

// Default access policy applied to all new nodes if not specified:
// {
//   "roles": ["authenticated"],
//   "deny": [],
//   "classification": "internal",
//   "gdpr_subject": false
// }
