from gaps.detector import coverage_score, maybe_abstain, record_gap, get_gaps


def test_coverage_scales() -> None:
    assert coverage_score(claim_count=0) == 0.0
    assert coverage_score(claim_count=3) == 1.0


def test_abstain_when_thin() -> None:
    out = maybe_abstain(memory_confidence=0.2, coverage=0.1, missing=["rollback"])
    assert out is not None
    assert out["next_action"] == "ASK"


def test_gap_aggregates() -> None:
    record_gap(
        workspace_id="ws",
        domain="payments",
        gap_type="MISSING_KNOWLEDGE",
        description="no rollback",
        coverage=0.2,
    )
    record_gap(
        workspace_id="ws",
        domain="payments",
        gap_type="MISSING_KNOWLEDGE",
        description="still missing",
        coverage=0.2,
    )
    gaps = get_gaps("ws")
    assert len(gaps) == 1
    assert gaps[0].frequency == 2
