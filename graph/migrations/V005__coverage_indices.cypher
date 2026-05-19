// V005 — Performance indices for coverage scoring queries.
// Coverage scorer runs nightly — these indices prevent full graph scans.

// Composite index: per-domain coverage query pattern
CREATE INDEX system_workspace_type IF NOT EXISTS
  FOR (s:System) ON (s.workspace_id, s.type);

// Full-text search index on Decision content
CREATE FULLTEXT INDEX decision_content_fulltext IF NOT EXISTS
  FOR (d:Decision) ON EACH [d.content];

// Full-text search on System names — entity resolution queries
CREATE FULLTEXT INDEX system_name_fulltext IF NOT EXISTS
  FOR (s:System) ON EACH [s.name];

MERGE (v:SchemaVersion {version: 5})
SET v.applied_at = datetime(), v.description = "Coverage indices";
