"""CortexBench runner — evaluate Reliability Gate scenarios."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from evals.scenarios.reliability import SCENARIOS
from reliability.gate import ReliabilityGate


def run_scenarios() -> dict:
    """Run built-in reliability scenarios; return report dict."""
    gate = ReliabilityGate()
    results = []
    passed = 0
    for sc in SCENARIOS:
        out = gate.evaluate(
            workspace_id="bench",
            query=sc["query"],
            candidate_action=sc["candidate_action"],
            claims=sc["claims"],
            caller_roles=sc["roles"],
            risk=sc["risk"],
        )
        expected = sc["expected_decision"]
        ok = out.decision in expected if isinstance(expected, list) else out.decision == expected
        if ok:
            passed += 1
        results.append(
            {
                "id": sc["id"],
                "name": sc["name"],
                "expected": expected,
                "actual": out.decision,
                "memory_confidence": out.memory_confidence,
                "action_confidence": out.action_confidence,
                "reason_codes": out.reason_codes,
                "passed": ok,
            }
        )
    report = {
        "suite": "cortexbench_reliability_baseline",
        "total": len(SCENARIOS),
        "passed": passed,
        "failed": len(SCENARIOS) - passed,
        "results": results,
    }
    return report


def main() -> None:
    report = run_scenarios()
    out_path = Path("evals/reports/reliability_baseline.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
