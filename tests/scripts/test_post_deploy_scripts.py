"""Tests for post-deploy seed/import scripts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[2]


def test_seed_oss_fastapi_dry_run() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(_REPO / "scripts" / "seed_oss_fastapi_demo.py"),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "oss-tiangolo-fastapi" in proc.stdout


def test_import_github_graph_dry_run() -> None:
    fake_prs = [
        {
            "number": 1,
            "title": "RFC: migrate architecture to async",
            "body": "We decided to switch dependency injection pattern.",
            "merged_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "created_at": "2024-01-01T00:00:00Z",
            "user": {"login": "tiangolo"},
            "head": {"ref": "feature/async"},
        }
    ]
    import scripts.import_github_graph as import_mod

    argv = [
        "import_github_graph.py",
        "--org",
        "tiangolo",
        "--repo",
        "fastapi",
        "--workspace",
        "oss-tiangolo-fastapi",
        "--limit",
        "3",
        "--dry-run",
    ]
    with patch.object(sys, "argv", argv):
        with patch.object(import_mod, "fetch_merged_prs", return_value=fake_prs):
            assert import_mod.main() == 0
