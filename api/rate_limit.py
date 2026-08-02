"""Rate limiting for expensive Cortex graph endpoints."""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address


def _limit(env_name: str, default: str) -> str:
    return os.environ.get(env_name, default).strip() or default


def query_rate_limit(*_args, **_kwargs) -> str:
    """Per-IP limit for POST /query (override with CORTEX_RATE_LIMIT_QUERY)."""
    return _limit("CORTEX_RATE_LIMIT_QUERY", "30/minute")


def inject_rate_limit(*_args, **_kwargs) -> str:
    """Per-IP limit for POST /inject (override with CORTEX_RATE_LIMIT_INJECT)."""
    return _limit("CORTEX_RATE_LIMIT_INJECT", "60/minute")


limiter = Limiter(key_func=get_remote_address, headers_enabled=True)
