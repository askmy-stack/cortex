"""FastAPI dependencies shared across route modules."""

from __future__ import annotations

from fastapi import HTTPException, status

from api.memory import MemoryService

_memory_service: MemoryService | None = None


def set_memory_service(service: MemoryService | None) -> None:
    """Set the process-wide memory service (called from app lifespan)."""
    global _memory_service
    _memory_service = service


def caller_roles(x_cortex_roles: str | None) -> list[str]:
    if not x_cortex_roles:
        return ["authenticated"]
    return [role.strip() for role in x_cortex_roles.split(",") if role.strip()]


def memory() -> MemoryService:
    if _memory_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory service is not initialized",
        )
    return _memory_service
