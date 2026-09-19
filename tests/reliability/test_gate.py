"""Tests for Memory Reliability Gate."""

from __future__ import annotations

from reliability.gate import ReliabilityGate


def test_same_memory_different_risk() -> None:
    gate = ReliabilityGate()
    claims = [{"confidence": 0.8, "status": "ACTIVE", "assertion_type": "ASSERTED"}]
    low = gate.evaluate(
        workspace_id="ws",
        query="status?",
        candidate_action={"type": "read"},
        claims=claims,
        caller_roles=["authenticated"],
        risk="READ_ONLY",
    )
    high = gate.evaluate(
        workspace_id="ws",
        query="restart?",
        candidate_action={"type": "restart_service", "target": "payments"},
        claims=claims,
        caller_roles=["authenticated"],
        risk="IRREVERSIBLE",
    )
    assert low.decision in {"ACT", "VERIFY"}
    assert high.decision != "ACT"
    assert high.action_confidence < low.action_confidence


def test_unauthorized_blocks_privileged() -> None:
    gate = ReliabilityGate()
    result = gate.evaluate(
        workspace_id="ws",
        query="restart payments",
        candidate_action={"type": "restart_service"},
        claims=[{"confidence": 0.99, "status": "ACTIVE"}],
        caller_roles=["authenticated"],
        risk="PRIVILEGED",
    )
    assert result.decision == "BLOCK"
    assert "ACTION_NOT_AUTHORIZED" in result.reason_codes


def test_signature_payments_restart_block() -> None:
    """Signature V2 scenario: high memory conf but BLOCK action."""
    gate = ReliabilityGate()
    claims = [
        {
            "confidence": 0.95,
            "status": "ACTIVE",
            "assertion_type": "ASSERTED",
            "conflict": True,
        },
        {"confidence": 0.9, "status": "SUPERSEDED", "assertion_type": "ASSERTED"},
    ]
    result = gate.evaluate(
        workspace_id="local-dev",
        query="Should I restart the payments service?",
        candidate_action={
            "type": "restart_service",
            "target": "payments-service",
            "stale_procedure": True,
            "active_migration": True,
        },
        claims=claims,
        caller_roles=["authenticated"],
        risk="HIGH_IMPACT_WRITE",
    )
    assert result.decision == "BLOCK"
    assert result.memory_confidence >= 0.9
    assert result.action_confidence < 0.5
    assert "ACTION_NOT_AUTHORIZED" in result.reason_codes or "ACTIVE_MIGRATION" in result.reason_codes


def test_insufficient_evidence_asks() -> None:
    gate = ReliabilityGate()
    result = gate.evaluate(
        workspace_id="ws",
        query="unknown domain",
        candidate_action={},
        claims=[],
        memories=[],
        caller_roles=["admin"],
        risk="READ_ONLY",
    )
    assert result.decision == "ASK"
    assert "INSUFFICIENT_EVIDENCE" in result.reason_codes
