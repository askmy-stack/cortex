"""Workspace query-cache epoch — bump on memory mutations so Redis keys miss.

Used by MemoryService (GDPR erase) and GraphWriter (pipeline writes) so
query/inject caches do not serve stale decisions for up to TTL seconds.
"""

from __future__ import annotations

import os
from typing import Any

import structlog

log = structlog.get_logger(__name__)

WORKSPACE_CACHE_EPOCH_PREFIX = "cortex:ws:"


def workspace_cache_epoch_key(workspace_id: str) -> str:
    """Redis key for the per-workspace cache generation counter."""
    return f"{WORKSPACE_CACHE_EPOCH_PREFIX}{workspace_id}:cache_epoch"


def bump_workspace_cache_epoch(
    workspace_id: str,
    *,
    redis_client: Any | None = None,
) -> int | None:
    """Increment workspace cache epoch. Returns new epoch or None if Redis unavailable."""
    if not workspace_id:
        return None
    client = redis_client
    if client is None:
        client = _connect_redis()
    if client is None:
        return None
    key = workspace_cache_epoch_key(workspace_id)
    try:
        new_epoch = int(client.incr(key))
    except Exception as exc:
        log.warning(
            "memory.cache.invalidate_failed",
            workspace_id=workspace_id,
            error=str(exc),
        )
        return None
    log.info("memory.cache.invalidated", workspace_id=workspace_id, epoch=new_epoch)
    return new_epoch


def _connect_redis() -> Any | None:
    """Best-effort Redis client from env (same defaults as MemoryService)."""
    try:
        import redis
    except ImportError:
        return None
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    try:
        client = redis.Redis(
            host=host,
            port=port,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
        client.ping()
        return client
    except Exception:
        return None
