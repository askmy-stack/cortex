# CortexBench — Evaluation Methodology (V2 P0 baseline)

**Status:** Baseline scaffold  
**Date:** 2026-09-18

## Goal

Prove Cortex improves **reliable agent action**, not only retrieval.

## Baseline suite (this PR)

| Scenario | Expected |
|---|---|
| Signature payments restart + migration | `BLOCK` |
| Insufficient evidence | `ASK` |
| High-confidence read | `ACT` |
| Stale procedure write | `VERIFY` / `ESCALATE` / `BLOCK` |

Run:

```bash
python -m evals.run_reliability
# or
pytest tests/evals/test_cortexbench.py
```

Report written to `evals/reports/reliability_baseline.json`.

## Planned baselines (later)

- A keyword / BM25
- B vector-only
- C graph + vector
- D + temporal
- E Cortex without Reliability Gate
- F full Cortex vNext

## Ablations

Minus Reliability Gate · Evidence Graph · Temporal · Firewall · Outcome feedback.

## Known limitations

- P0 suite exercises the **Reliability Gate** only (fixture claims, not live Neo4j).
- Retrieval Precision@K / Brier calibration land in later eval PRs.
