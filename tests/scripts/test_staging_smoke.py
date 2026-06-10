"""Unit tests for scripts/staging_smoke.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts import staging_smoke as smoke


def test_check_health_ok() -> None:
    payload = {"status": "ok", "dependencies": {"neo4j": "ok", "redis": "ok"}}
    with patch.object(smoke, "fetch_json", return_value=payload):
        ok, data = smoke.check_health("http://localhost:8000")
    assert ok is True
    assert data["status"] == "ok"


def test_check_health_degraded() -> None:
    payload = {"status": "ok", "dependencies": {"neo4j": "ok", "redis": "unreachable"}}
    with patch.object(smoke, "fetch_json", return_value=payload):
        ok, _ = smoke.check_health("http://localhost:8000")
    assert ok is False


def test_check_query_ok() -> None:
    with patch.object(smoke, "fetch_json", return_value={"results": [], "total": 0}):
        ok, _ = smoke.check_query("http://localhost:8000", workspace="local-dev", query="test")
    assert ok is True


def test_main_dry_run() -> None:
    with patch.object(sys, "argv", ["staging_smoke.py", "--dry-run"]):
        assert smoke.main() == 0
