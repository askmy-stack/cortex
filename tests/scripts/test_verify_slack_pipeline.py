"""Tests for scripts/verify_slack_pipeline.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts import verify_slack_pipeline as verify


def test_check_ollama_model_found() -> None:
    payload = json.dumps({"models": [{"name": "llama3.1:8b"}]}).encode()

    class _Resp:
        def read(self) -> bytes:
            return payload

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    with patch("urllib.request.urlopen", return_value=_Resp()):
        ok, msg = verify.check_ollama(base_url="http://localhost:11434", model="llama3.1:8b")

    assert ok is True
    assert "llama3.1:8b" in msg


def test_check_ollama_unreachable() -> None:
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        ok, msg = verify.check_ollama(base_url="http://localhost:11434", model="llama3.1:8b")

    assert ok is False
    assert "unreachable" in msg.lower()


def test_main_dry_run() -> None:
    with (
        patch.object(verify, "check_ollama", return_value=(True, "ok")),
        patch.object(verify, "count_decisions", return_value=3),
        patch.object(sys, "argv", ["verify_slack_pipeline.py", "--dry-run"]),
    ):
        assert verify.main() == 0


def test_main_dry_run_github_source() -> None:
    with (
        patch.object(verify, "check_ollama", return_value=(True, "ok")),
        patch.object(verify, "count_decisions", return_value=3),
        patch.object(sys, "argv", ["verify_slack_pipeline.py", "--source", "github", "--dry-run"]),
    ):
        assert verify.main() == 0
