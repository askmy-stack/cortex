"""API key authentication and server-side role resolution."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.deps import _load_api_keys, resolve_roles
from api.main import app


def test_open_mode_trusts_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORTEX_API_KEYS", raising=False)
    assert resolve_roles(None, None, "admin,authenticated") == ["admin", "authenticated"]
    assert resolve_roles(None, None, None) == ["authenticated"]


def test_keys_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_API_KEYS", "sk_a:admin;authenticated,sk_b:authenticated")
    assert _load_api_keys() == {
        "sk_a": ["admin", "authenticated"],
        "sk_b": ["authenticated"],
    }


def test_auth_required_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_API_KEYS", "sk_a:admin")
    with pytest.raises(HTTPException) as exc:
        resolve_roles(None, None, "admin")
    assert exc.value.status_code == 401


def test_valid_bearer_key_overrides_client_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_API_KEYS", "sk_a:admin;authenticated")
    # The spoofed X-Cortex-Roles header must be ignored when auth is enabled.
    assert resolve_roles("Bearer sk_a", None, "superadmin") == ["admin", "authenticated"]


def test_valid_x_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_API_KEYS", "sk_a:authenticated")
    assert resolve_roles(None, "sk_a", None) == ["authenticated"]


def test_invalid_key_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_API_KEYS", "sk_a:admin")
    with pytest.raises(HTTPException) as exc:
        resolve_roles("Bearer wrong", None, None)
    assert exc.value.status_code == 401


def test_route_rejects_missing_key_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_API_KEYS", "sk_a:admin")
    client = TestClient(app)
    response = client.get("/contradictions/pending", params={"workspace_id": "ws-1"})
    assert response.status_code == 401
