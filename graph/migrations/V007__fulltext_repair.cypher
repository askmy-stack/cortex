// V007 — Ensure full-text indexes exist (repair for DBs that recorded V005 without indexes).
// Root cause was SchemaVersion MERGE matching on applied_at, so duplicate version nodes could
// confuse applied-set logic. Fulltext CREATE may not have run on older volumes.

CREATE FULLTEXT INDEX decision_content_fulltext IF NOT EXISTS
  FOR (d:Decision) ON EACH [d.content];

CREATE FULLTEXT INDEX system_name_fulltext IF NOT EXISTS
  FOR (s:System) ON EACH [s.name];

MERGE (v:SchemaVersion {version: 7})
SET v.applied_at = datetime(), v.description = "Fulltext index repair";
