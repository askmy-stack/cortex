"""Tests for scripts/inject_slack_message.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts import inject_slack_message as inject


def test_build_slack_payload_has_message_event() -> None:
    payload = inject.build_slack_payload(
        text="We decided on Kafka.",
        channel="C-eng",
        user="U1",
        team_id="T1",
    )
    assert payload["type"] == "event_callback"
    assert payload["event"]["text"] == "We decided on Kafka."


def test_main_dry_run() -> None:
    with patch.object(sys, "argv", ["inject_slack_message.py", "--dry-run"]):
        assert inject.main() == 0
