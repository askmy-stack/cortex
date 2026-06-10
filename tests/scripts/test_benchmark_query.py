"""Unit tests for scripts/benchmark_query.py."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts import benchmark_query as bq


def test_percentile_empty() -> None:
    assert bq._percentile([], 95) == 0.0


def test_percentile_single_value() -> None:
    assert bq._percentile([42.0], 95) == 42.0


def test_percentile_ordered() -> None:
    assert bq._percentile([10.0, 20.0, 30.0, 40.0], 50) == 25.0
