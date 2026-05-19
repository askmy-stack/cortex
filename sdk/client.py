"""HTTP client for the Cortex Context API."""

from __future__ import annotations

from typing import Any

import httpx


class CortexClient:
    """Thin wrapper around Cortex REST endpoints.

    Usage:
        client = CortexClient("http://localhost:8000")
        hits = client.query("why CockroachDB?", workspace_id="acme-demo")
        client.remember("We chose Redis for session cache.", workspace_id="acme-demo")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        *,
        roles: str = "authenticated",
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"X-Cortex-Roles": roles, "Content-Type": "application/json"}
        self._timeout = timeout

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as client:
            response = client.post(path, json=body, headers=self._headers)
            response.raise_for_status()
            return response.json()

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as client:
            response = client.get(path, params=params, headers=self._headers)
            response.raise_for_status()
            return response.json()

    def query(
        self,
        query: str,
        *,
        workspace_id: str,
        limit: int = 10,
        min_importance: float = 0.0,
        min_trust: float = 0.0,
        event_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Search organizational memory (POST /query)."""
        return self._post(
            "/query",
            {
                "query": query,
                "workspace_id": workspace_id,
                "limit": limit,
                "min_importance": min_importance,
                "min_trust": min_trust,
                "event_types": event_types or [],
            },
        )

    def inject(
        self,
        context: str,
        *,
        workspace_id: str,
        agent_id: str,
        max_tokens: int = 4000,
    ) -> dict[str, Any]:
        """Active context injection (POST /inject)."""
        return self._post(
            "/inject",
            {
                "context": context,
                "workspace_id": workspace_id,
                "agent_id": agent_id,
                "max_tokens": max_tokens,
            },
        )

    def remember(
        self,
        content: str,
        *,
        workspace_id: str,
        author: str = "sdk-user",
        channel: str = "sdk",
        affects: list[str] | None = None,
    ) -> dict[str, Any]:
        """Submit explicit memory into the pipeline (POST /remember)."""
        return self._post(
            "/remember",
            {
                "content": content,
                "workspace_id": workspace_id,
                "author": author,
                "channel": channel,
                "affects": affects or [],
            },
        )

    def decisions_by_system(
        self,
        system_id: str,
        *,
        workspace_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """GET /decisions/by-system/{system_id}."""
        return self._get(
            f"/decisions/by-system/{system_id}",
            {"workspace_id": workspace_id, "limit": limit},
        )

    def causal_chain(
        self,
        decision_id: str,
        *,
        workspace_id: str,
        max_depth: int = 4,
    ) -> dict[str, Any]:
        """GET /decisions/{id}/chain."""
        return self._get(
            f"/decisions/{decision_id}/chain",
            {"workspace_id": workspace_id, "max_depth": max_depth},
        )

    def health(self) -> dict[str, Any]:
        """GET /health."""
        return self._get("/health", {})
