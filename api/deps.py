"""FastAPI dependencies shared across route modules."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from api.memory import MemoryService

_memory_service: MemoryService | None = None


def set_memory_service(service: MemoryService | None) -> None:
    """Set the process-wide memory service (called from app lifespan)."""
    global _memory_service
    _memory_service = service


def _load_api_keys() -> dict[str, list[str]]:
    """Parse CORTEX_API_KEYS into a ``{key: [roles]}`` map.

    Format: ``key1:admin;authenticated,key2:authenticated`` — comma-separated
    entries, each ``<key>:<role>;<role>``. Empty/unset disables auth.
    """
    raw = os.environ.get("CORTEX_API_KEYS", "").strip()
    keys: dict[str, list[str]] = {}
    if not raw:
        return keys
    for entry in raw.split(","):
        key, sep, roles_str = entry.strip().partition(":")
        if not sep:
            continue
        roles = [r.strip() for r in roles_str.split(";") if r.strip()]
        if key.strip() and roles:
            keys[key.strip()] = roles
    return keys


def caller_roles(x_cortex_roles: str | None) -> list[str]:
    """Parse the legacy X-Cortex-Roles header (trusted only when auth is off)."""
    if not x_cortex_roles:
        return ["authenticated"]
    return [role.strip() for role in x_cortex_roles.split(",") if role.strip()]


def resolve_roles(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_cortex_roles: str | None = Header(default=None, alias="X-Cortex-Roles"),
) -> list[str]:
    """Resolve caller roles for RBAC.

    When ``CORTEX_API_KEYS`` is configured, roles are derived server-side from a
    validated API key (``Authorization: Bearer <key>`` or ``X-API-Key``); the
    client-supplied ``X-Cortex-Roles`` header is ignored and an invalid/missing
    key yields HTTP 401. When no keys are configured the service runs in open
    (dev/demo) mode and trusts ``X-Cortex-Roles``.
    """
    api_keys = _load_api_keys()
    if not api_keys:
        return caller_roles(x_cortex_roles)

    token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_api_key:
        token = x_api_key.strip()

    roles = api_keys.get(token or "")
    if not roles:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
        )
    return roles


RolesDep = Annotated[list[str], Depends(resolve_roles)]


def memory() -> MemoryService:
    if _memory_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory service is not initialized",
        )
    return _memory_service
