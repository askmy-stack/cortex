"""Unit tests for scripts/dual_workspace_smoke.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts import dual_workspace_smoke as dws


def test_post_query_parses_json() -> None:
    payload = {"results": [{"content": "CockroachDB migration"}], "total": 1}
    body = json.dumps(payload).encode("utf-8")

    class FakeResp:
        def read(self) -> bytes:
            return body

        def __enter__(self) -> FakeResp:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        out = dws.post_query("http://localhost:8000", query="test", workspace_id="local-dev", limit=3)
    assert out["total"] == 1


def test_main_ok() -> None:
    fake = {"results": [{"content": "hit"}], "total": 1}
    with (
        patch.object(dws, "post_query", return_value=fake),
        patch.object(
            sys,
            "argv",
            ["dual_workspace_smoke.py", "--workspaces", "local-dev", "--queries", "test"],
        ),
    ):
        assert dws.main() == 0
