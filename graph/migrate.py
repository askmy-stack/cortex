"""Neo4j schema migration runner.

Applies Cypher migration scripts in `graph/migrations/` in version order.
Idempotent — tracks applied versions in SchemaVersion nodes.

Usage:
    python -m graph.migrate
    python -m graph.migrate --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import structlog
from neo4j import Driver, GraphDatabase

log = structlog.get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
VERSION_PATTERN = re.compile(r"V(\d+)__(.+)\.cypher")


def get_driver() -> Driver:
    """Create a Neo4j driver from environment variables."""
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "cortex_local")
    return GraphDatabase.driver(uri, auth=(user, password))


def get_applied_versions(driver: Driver) -> set[int]:
    """Return set of already-applied schema version numbers."""
    with driver.session() as session:
        result = session.run(
            "MATCH (v:SchemaVersion) RETURN v.version AS version"
        )
        return {record["version"] for record in result}


def get_migration_files() -> list[tuple[int, str, Path]]:
    """Return sorted list of (version, description, path) tuples."""
    migrations: list[tuple[int, str, Path]] = []
    for path in MIGRATIONS_DIR.glob("V*.cypher"):
        match = VERSION_PATTERN.match(path.name)
        if match:
            version = int(match.group(1))
            description = match.group(2).replace("_", " ")
            migrations.append((version, description, path))
    return sorted(migrations, key=lambda x: x[0])


def apply_migration(driver: Driver, version: int, description: str, path: Path) -> None:
    """Apply a single migration file to Neo4j."""
    cypher = path.read_text(encoding="utf-8")

    # Split on semicolons and execute each statement individually
    statements = [s.strip() for s in cypher.split(";") if s.strip()]

    with driver.session() as session:
        for statement in statements:
            if statement.startswith("//"):
                continue
            try:
                session.run(statement)
            except Exception as exc:
                log.error(
                    "migration.statement_failed",
                    version=version,
                    statement=statement[:100],
                    error=str(exc),
                )
                raise

    log.info(
        "migration.applied",
        version=version,
        description=description,
        path=str(path.name),
    )


def run_migrations(dry_run: bool = False) -> None:
    """Run all pending migrations."""
    driver = get_driver()
    applied = get_applied_versions(driver)
    migrations = get_migration_files()

    pending = [(v, d, p) for v, d, p in migrations if v not in applied]

    if not pending:
        log.info("migrations.up_to_date", applied_count=len(applied))
        driver.close()
        return

    log.info(
        "migrations.pending",
        pending_count=len(pending),
        dry_run=dry_run,
    )

    for version, description, path in pending:
        log.info(
            "migration.starting",
            version=version,
            description=description,
            dry_run=dry_run,
        )
        if not dry_run:
            apply_migration(driver, version, description, path)

    driver.close()
    log.info("migrations.complete", applied_count=len(pending))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cortex Neo4j migration runner")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show pending migrations without applying them",
    )
    args = parser.parse_args()

    try:
        run_migrations(dry_run=args.dry_run)
    except Exception as exc:
        log.error("migrations.failed", error=str(exc))
        sys.exit(1)
