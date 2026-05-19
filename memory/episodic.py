"""Episodic store — append-only RawEvent rows in TimescaleDB."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from urllib.parse import quote_plus

import structlog

from shared.models import RawEvent

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
        CREATE TABLE IF NOT EXISTS cortex_raw_events (
            event_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            source TEXT NOT NULL,
            event_type TEXT NOT NULL,
            ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            payload JSONB NOT NULL
        );
        """
    )


async def _append_async(raw: RawEvent) -> None:
    import asyncpg

    dsn = _timescale_dsn()
    if dsn is None:
        return
    conn = await asyncpg.connect(dsn)
    try:
        await _ensure_table(conn)
        payload = json.dumps(raw.model_dump(mode="json"))
        await conn.execute(
            """
            INSERT INTO cortex_raw_events (event_id, workspace_id, source, event_type, payload)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            ON CONFLICT (event_id) DO NOTHING
            """,
            raw.event_id,
            raw.workspace_id,
            raw.source,
            raw.event_type,
            payload,
        )
        log.debug("episodic.append", event_id=raw.event_id, source=raw.source)
    finally:
        await conn.close()


def append_raw_event(raw: RawEvent) -> None:
    """Persist a RawEvent to Timescale when TIMESCALE_HOST is configured."""
    if _timescale_dsn() is None:
        return
    asyncio.run(_append_async(raw))
