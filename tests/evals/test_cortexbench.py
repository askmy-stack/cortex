"""CortexBench reliability baseline tests."""

from __future__ import annotations

from evals.run_reliability import run_scenarios


def test_cortexbench_reliability_baseline_passes() -> None:
    report = run_scenarios()
    assert report["failed"] == 0, report
    assert report["passed"] == report["total"]
