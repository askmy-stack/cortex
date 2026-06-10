"""Quarantine store — audit trail for rejected graph writes.

Architecture: Phase 4 — low-trust and CMVK-failed decisions are not written to
Neo4j but must be persisted for audit and human review instead of silent drop.
Uses TimescaleDB when TIMESCALE_HOST is configured (same pattern as episodic).
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from urllib.parse import quote_plus

import structlog

from scoring.write_pipeline import WriteRejectReason
from shared.models import DecisionEvent

log = structlog.get_logger(__name__)


def _timescale_dsn() -> str | None:
    host = os.environ.get("TIMESCALE_HOST")
    if not host:
        return None
    port = int(os.environ.get("TIMESCALE_PORT", "5433"))
    user = os.environ.get("TIMESCALE_USER", "cortex")
    password = os.environ.get("TIMESCALE_PASSWORD", "cortex_local")
    db = os.environ.get("TIMESCALE_DB", "cortex_events")
    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(db)}"
    )


async def _ensure_table(conn: Any) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cortex_quarantine_events (
            event_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            reject_reason TEXT NOT NULL,
            importance_score DOUBLE PRECISION,
            trust_score DOUBLE PRECISION,
            quarantined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            payload JSONB NOT NULL,
            PRIMARY KEY (event_id, reject_reason)
        );
        """
    )


async def _persist_async(decision: DecisionEvent, reason: WriteRejectReason) -> None:
    import asyncpg

    dsn = _timescale_dsn()
    if dsn is None:
        return
    conn = await asyncpg.connect(dsn)
    try:
        await _ensure_table(conn)
        payload = json.dumps(decision.model_dump(mode="json"))
        await conn.execute(
            """
            INSERT INTO cortex_quarantine_events (
                event_id, workspace_id, reject_reason,
                importance_score, trust_score, payload
            )
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            ON CONFLICT (event_id, reject_reason) DO NOTHING
            """,
            decision.event_id,
            decision.workspace_id,
            reason,
            decision.importance_score,
            decision.trust_score,
            payload,
        )
        log.info(
            "quarantine.persisted",
            event_id=decision.event_id,
            reject_reason=reason,
            importance_score=decision.importance_score,
            trust_score=decision.trust_score,
        )
    finally:
        await conn.close()


def persist_quarantine(decision: DecisionEvent, reason: WriteRejectReason) -> None:
    """Persist a rejected decision when Timescale is configured."""
    if _timescale_dsn() is None:
        log.debug(
            "quarantine.skipped_no_dsn",
            event_id=decision.event_id,
            reject_reason=reason,
        )
        return
    asyncio.run(_persist_async(decision, reason))
