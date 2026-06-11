"""Unit tests for scripts/import_github_org.py (no GitHub / Kafka)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts import import_github_org as igo


SAMPLE_PR = {
    "number": 123,
    "title": "RFC: migrate session cache to Redis",
    "body": "We decided to replace in-memory sessions.",
    "merged_at": "2026-01-15T12:00:00Z",
    "updated_at": "2026-01-15T12:00:00Z",
    "created_at": "2026-01-10T09:00:00Z",
    "user": {"login": "alice"},
    "head": {"ref": "feature/redis-cache"},
}


def test_is_decision_like_matches_keywords() -> None:
    assert igo.is_decision_like(SAMPLE_PR) is True
    assert igo.is_decision_like({"title": "Fix typo", "body": "n/a"}) is False


def test_pr_to_payload_includes_repo_and_number() -> None:
    payload = igo.pr_to_payload(SAMPLE_PR, "tiangolo/fastapi")
    assert payload["pull_request"]["number"] == 123
    assert payload["repository"]["full_name"] == "tiangolo/fastapi"
    assert payload["pull_request"]["user"]["login"] == "alice"


def test_main_dry_run_filters_decision_prs() -> None:
    prs = [
        SAMPLE_PR,
        {"number": 1, "title": "chore: bump deps", "body": "", "merged_at": "2026-01-01T00:00:00Z"},
    ]
    with (
        patch.object(igo, "fetch_merged_prs", return_value=prs),
        patch.object(sys, "argv", ["import_github_org.py", "--org", "o", "--repo", "r", "--dry-run"]),
    ):
        assert igo.main() == 0


def test_main_dry_run_all_merged() -> None:
    prs = [
        SAMPLE_PR,
        {
            "number": 2,
            "title": "chore: bump deps",
            "body": "",
            "merged_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "created_at": "2026-01-01T00:00:00Z",
            "user": {"login": "bot"},
            "head": {"ref": "chore"},
        },
    ]
    with (
        patch.object(igo, "fetch_merged_prs", return_value=prs),
        patch.object(
            sys,
            "argv",
            ["import_github_org.py", "--org", "o", "--repo", "r", "--all-merged", "--dry-run"],
        ),
    ):
        assert igo.main() == 0


def test_main_publish_calls_producer() -> None:
    producer = MagicMock()
    with (
        patch.object(igo, "fetch_merged_prs", return_value=[SAMPLE_PR]),
        patch.object(igo, "GitHubKafkaProducer", return_value=producer),
        patch.object(sys, "argv", ["import_github_org.py", "--org", "o", "--repo", "r"]),
    ):
        assert igo.main() == 0
    assert producer.publish.call_count == 1
    producer.flush.assert_called_once()
    producer.close.assert_called_once()
