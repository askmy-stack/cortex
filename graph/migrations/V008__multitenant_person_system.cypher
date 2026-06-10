// V008 — Multi-tenant Person/System identity
// graph/writer.py MERGEs Person and System on (id, workspace_id), but the V001
// single-property uniqueness constraints on `id` reject the same id across
// workspaces (e.g. two workspaces each with a person "alice"). Neo4j Community
// Edition has no composite NODE KEY, so we drop the single-id constraints and
// back the composite merge with composite indexes instead.
// Decision: D-018 — Person/System ids are unique per workspace, not globally.

DROP CONSTRAINT person_id_unique IF EXISTS;

DROP CONSTRAINT system_id_unique IF EXISTS;

CREATE INDEX person_id_workspace IF NOT EXISTS
  FOR (p:Person) ON (p.id, p.workspace_id);

CREATE INDEX system_id_workspace IF NOT EXISTS
  FOR (s:System) ON (s.id, s.workspace_id);

// Schema version recorded last so a failed migration does not mark this applied.
MERGE (v:SchemaVersion {version: 8})
SET v.applied_at = datetime(), v.description = "Multi-tenant Person/System identity";
